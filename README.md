# Simular Gateway - Unofficial Bridge to Simular Pro (Sai) Cloud Models

A minimal local proxy that exposes Simular Pro (Sai) cloud models as an Anthropic/Google-compatible API for use with OpenCode or similar agent clients.

> **Unofficial project.** This is a reverse-engineered bridge built by observing the Simular desktop app's own network calls (v1.12.1). It is not affiliated with, endorsed by, or supported by Simular. It may break without notice if Simular changes their API.

## How it works

1. You sign in to the official **Simular desktop app** at least once - this stores a Firebase refresh token at `~/.simulang/credentials.json` on your machine.
2. This gateway reads that existing credentials file (it does **not** implement its own login flow) and auto-refreshes the short-lived Firebase idToken (~1h) via Google's `securetoken` endpoint.
3. It proxies incoming requests to Simular's cloud API, injecting `Authorization: Bearer <idToken>` and the required `X-Goal` header, listening on `127.0.0.1` only.

## Models exposed

| Model ID | Underlying model |
|---|---|
| `simular-claude/claude-opus-4-8` | Claude 4.8 Opus |
| `simular-gemini/gemini-3.1-pro-preview` | Gemini 3.1 Pro |

Both support full tool-calling, so they work as complete coding agents in OpenCode (edit/bash/read/etc.), same as any other model.

## Quick Start

### Prerequisites

- Python 3.10+ with `pythonw` on PATH (or edit `start.ps1` to point at your Python install)
- The official Simular desktop app, installed and signed in at least once (populates `~/.simulang/credentials.json`)

### Setup

```bash
git clone https://github.com/susmnavorasem/Simular-Gateway.git
cd Simular-Gateway
pip install -r requirements.txt
```

### Start

Headless (Windows, no console window):
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```
Idempotent - if already running on port 8799, it does nothing.

Or run directly (any OS):
```bash
python server.py
```

### Health check

```bash
curl http://127.0.0.1:8799/health
# {"status":"ok","signed_in":true}
```

### Stop (Windows)

```powershell
Get-NetTCPConnection -LocalPort 8799 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## Configuration

| File | Role |
|---|---|
| `server.py` | FastAPI passthrough proxy (Anthropic + Google paths only) |
| `token_manager.py` | Reads `credentials.json`, refreshes the idToken, single-flight (no duplicate refresh races) |
| `config.py` | Host/port/URLs/paths, all environment-variable overridable |
| `logs/gateway.log` | Runtime log - verified to never contain tokens |

Port, host, and upstream URLs can be overridden via environment variables - see `config.py` for the exact variable names and defaults.

## Security note: the Firebase API key

`config.py` contains a `FIREBASE_API_KEY` value (`AIzaSy...`). This is **not a secret** - it is Google Firebase's standard "Web API key," a public client identifier extracted from the Simular app bundle. Firebase Web API keys are meant to be embedded in client applications; the actual security boundary is Firebase's server-side security rules and the user's own refresh token (which never leaves your machine and is never logged). This is the same key the official Simular app itself ships with.

## Limitations

- No account manager, no UI - this is intentionally minimal (Variant C). The token comes entirely from the Simular app's own login session.
- If you sign out of the Simular app, delete `credentials.json`, or the refresh token expires, the gateway returns HTTP 503 until you sign back into the app.
- Port 8799 was chosen to avoid common Windows-reserved dynamic port ranges.
- Endpoint paths are derived from reverse-engineering Simular app v1.12.1's `createModel()` call - a future Simular app update could break this without warning.

## License

Source code: [CC BY-NC 4.0](LICENSE) - free for non-commercial use. Commercial use requires a separate license - see [COMMERCIAL-LICENSING.md](COMMERCIAL-LICENSING.md).

Copyright (c) 2026 susmnavorasem.

---

**Keywords:** Simular Gateway, Simular Pro proxy, Sai cloud models, unofficial Simular bridge, Claude Opus proxy, Gemini proxy, OpenCode agent gateway, reverse-engineered API bridge
