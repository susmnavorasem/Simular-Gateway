# Token manager: reads Simular's stored Firebase refresh token and keeps a fresh
# idToken available. Single-flight refresh. Never logs token values.

import asyncio
import json
import time

import httpx

import config


class TokenError(Exception):
    pass


class TokenManager:
    def __init__(self) -> None:
        self._id_token: str | None = None
        self._expires_at: float = 0.0
        self._refresh_token: str | None = None
        self._uid: str | None = None
        self._lock = asyncio.Lock()

    def _load_refresh_token(self) -> tuple[str, str]:
        """Read refreshToken + uid from the Simular credentials file.

        The file shape is {"firebase:authUser:<apiKey>:[DEFAULT]": { ...user... }}.
        Returns (refresh_token, uid). Raises TokenError on any problem.
        """
        try:
            with open(config.CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise TokenError(
                f"Simular credentials not found at {config.CREDENTIALS_PATH}. "
                "Sign in to the Simular app first."
            )
        except (OSError, json.JSONDecodeError) as e:
            raise TokenError(f"Cannot read Simular credentials: {type(e).__name__}")

        if not isinstance(data, dict) or not data:
            raise TokenError("Simular credentials file is empty or malformed.")

        # Prefer a firebase:authUser:* entry; fall back to the first object value.
        user = None
        for key, value in data.items():
            if key.startswith("firebase:authUser:") and isinstance(value, dict):
                user = value
                break
        if user is None:
            first = next(iter(data.values()))
            user = first if isinstance(first, dict) else None
        if not isinstance(user, dict):
            raise TokenError("No Firebase user object in credentials file.")

        sts = user.get("stsTokenManager") or {}
        rt = sts.get("refreshToken")
        uid = user.get("uid", "")
        if not isinstance(rt, str) or not rt:
            raise TokenError("No refreshToken in Simular credentials.")
        return rt, uid

    async def _refresh(self) -> None:
        """Exchange the refresh token for a fresh idToken via securetoken."""
        rt, uid = self._load_refresh_token()
        self._refresh_token = rt
        self._uid = uid
        body = {"grant_type": "refresh_token", "refresh_token": rt}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{config.SECURETOKEN_URL}?key={config.FIREBASE_API_KEY}",
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            raise TokenError(f"Token refresh failed: HTTP {resp.status_code}")
        payload = resp.json()
        id_token = payload.get("id_token") or payload.get("access_token")
        expires_in = int(payload.get("expires_in", "3600"))
        if not id_token:
            raise TokenError("Token refresh response missing id_token.")
        self._id_token = id_token
        self._expires_at = time.time() + expires_in

    async def get_id_token(self) -> str:
        """Return a valid idToken, refreshing if needed. Single-flight."""
        now = time.time()
        if self._id_token and now < (self._expires_at - config.REFRESH_SKEW_SECONDS):
            return self._id_token
        async with self._lock:
            now = time.time()
            if self._id_token and now < (self._expires_at - config.REFRESH_SKEW_SECONDS):
                return self._id_token
            await self._refresh()
            assert self._id_token is not None
            return self._id_token

    @property
    def uid(self) -> str | None:
        return self._uid
