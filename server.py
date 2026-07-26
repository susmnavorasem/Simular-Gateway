# --- pythonw headless guard: ensure std streams exist (None under pythonw) ---
import os as _os, sys as _sys
_logdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "logs")
_os.makedirs(_logdir, exist_ok=True)
if _sys.stdout is None or _sys.stderr is None:
    _f = open(_os.path.join(_logdir, "pythonw.out"), "a", encoding="utf-8", buffering=1)
    if _sys.stdout is None:
        _sys.stdout = _f
    if _sys.stderr is None:
        _sys.stderr = _f
# -----------------------------------------------------------------------------
# Simular Gateway вЂ” FastAPI passthrough proxy.
#
# Forwards OpenCode's requests to Simular's cloud, injecting a fresh Firebase
# Bearer token + X-Goal, and stripping any client-supplied auth. Supports both
# streaming and non-streaming responses. Binds 127.0.0.1 only.
#
# Security: never logs token values or Authorization headers.

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

import config
from token_manager import TokenError, TokenManager

# ---- Logging (no secrets) ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_PATH, encoding="utf-8")],
)
log = logging.getLogger("simular-gateway")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

tokens = TokenManager()


# --- Strongest-mode thinking injection -------------------------------------
# This Simular-proxied Claude uses the NEW thinking syntax
# (thinking.type=adaptive + output_config.effort), not the legacy
# thinking.type=enabled + budget_tokens. We force max thinking by default and
# translate any legacy thinking the client sends so it never 400s.
import json as _json

_ANTHROPIC_EFFORT = "high"

def _inject_thinking(path: str, body: bytes) -> bytes:
    if not body or not path.startswith("/v1/anthropic/"):
        return body
    try:
        obj = _json.loads(body)
    except Exception:
        return body
    if not isinstance(obj, dict) or "messages" not in obj:
        return body
    tc = obj.get("tool_choice")
    forced = isinstance(tc, dict) and tc.get("type") in ("any", "tool")
    th = obj.get("thinking")
    changed = False
    # Translate legacy thinking -> new syntax (always safe, avoids 400).
    if isinstance(th, dict) and th.get("type") == "enabled":
        obj["thinking"] = {"type": "adaptive"}
        oc = obj.get("output_config")
        if not isinstance(oc, dict):
            oc = {}
        oc.setdefault("effort", _ANTHROPIC_EFFORT)
        obj["output_config"] = oc
        changed = True
    # No thinking requested + not a forced tool call -> enable strongest thinking.
    elif th is None and not forced:
        obj["thinking"] = {"type": "adaptive"}
        oc = obj.get("output_config")
        if not isinstance(oc, dict):
            oc = {}
        oc.setdefault("effort", _ANTHROPIC_EFFORT)
        obj["output_config"] = oc
        changed = True
    if changed:
        return _json.dumps(obj).encode()
    return body
# ---------------------------------------------------------------------------


# Hop-by-hop and client headers we must NOT forward upstream.
_STRIP_REQUEST_HEADERS = {
    "host", "authorization", "x-api-key", "x-goal", "content-length",
    "connection", "keep-alive", "proxy-authorization", "te", "trailer",
    "transfer-encoding", "upgrade", "accept-encoding",
}
# Response headers we must not copy back (httpx already decoded the body).
_STRIP_RESPONSE_HEADERS = {
    "content-encoding", "content-length", "transfer-encoding", "connection",
    "keep-alive",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the token on startup so the first request is fast and we fail loudly
    # if the user is not signed in.
    try:
        await tokens.get_id_token()
        log.info("Startup: Simular idToken acquired (uid set=%s).", bool(tokens.uid))
    except TokenError as e:
        log.warning("Startup: could not acquire token yet: %s", e)
    app.state.client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0))
    try:
        yield
    finally:
        await app.state.client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> Response:
    try:
        await tokens.get_id_token()
        return JSONResponse({"status": "ok", "signed_in": True})
    except TokenError as e:
        return JSONResponse({"status": "degraded", "signed_in": False, "error": str(e)},
                            status_code=503)


def _is_allowed(path: str) -> bool:
    return any(path.startswith(p) for p in config.ALLOWED_PREFIXES)


def _build_upstream_headers(req: Request, id_token: str) -> dict:
    headers = {
        k: v for k, v in req.headers.items()
        if k.lower() not in _STRIP_REQUEST_HEADERS
    }
    headers["Authorization"] = f"Bearer {id_token}"
    headers["X-Goal"] = config.X_GOAL

    # Force identity so streamed raw bytes are never compressed (we strip content-encoding).

    headers["Accept-Encoding"] = "identity"
    # The Anthropic SDK path also expects x-api-key; the proxy ignores its value.
    if req.url.path.startswith("/v1/anthropic/"):
        headers["x-api-key"] = "dummy-key-for-proxy"
    return headers


@app.api_route("/{full_path:path}",
               methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(full_path: str, request: Request) -> Response:
    path = "/" + full_path
    if not _is_allowed(path):
        return JSONResponse({"error": f"path not allowed: {path}"}, status_code=404)

    try:
        id_token = await tokens.get_id_token()
    except TokenError as e:
        log.error("Token unavailable: %s", e)
        return JSONResponse({"error": f"auth unavailable: {e}"}, status_code=503)

    body = await request.body()
    body = _inject_thinking(path, body)
    upstream_url = config.CLOUD_API_URL + path
    if request.url.query:
        upstream_url += "?" + request.url.query
    headers = _build_upstream_headers(request, id_token)

    client: httpx.AsyncClient = request.app.state.client
    is_stream = b'"stream":true' in body or b'"stream": true' in body

    log.info("-> %s %s (stream=%s, %d bytes)", request.method, path, is_stream, len(body))

    upstream_req = client.build_request(
        request.method, upstream_url, headers=headers, content=body or None,
    )

    if is_stream:
        upstream_resp = await client.send(upstream_req, stream=True)
        resp_headers = {
            k: v for k, v in upstream_resp.headers.items()
            if k.lower() not in _STRIP_RESPONSE_HEADERS
        }
        log.info("<- %s %s -> %d (stream)", request.method, path, upstream_resp.status_code)

        async def body_iter():
            try:
                async for chunk in upstream_resp.aiter_raw():
                    yield chunk
            finally:
                await upstream_resp.aclose()

        return StreamingResponse(
            body_iter(),
            status_code=upstream_resp.status_code,
            headers=resp_headers,
            media_type=upstream_resp.headers.get("content-type"),
        )

    upstream_resp = await client.send(upstream_req)
    resp_headers = {
        k: v for k, v in upstream_resp.headers.items()
        if k.lower() not in _STRIP_RESPONSE_HEADERS
    }
    log.info("<- %s %s -> %d (%d bytes)", request.method, path,
             upstream_resp.status_code, len(upstream_resp.content))
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_config=None, log_level="warning")



