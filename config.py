# Simular Gateway вЂ” minimal local proxy (Variant C)
# Exposes Simular Pro's cloud models to OpenCode via 127.0.0.1.
# Reads the app's stored Firebase refresh token, auto-refreshes the idToken,
# and transparently proxies Anthropic + Google generation paths.
#
# Security: binds 127.0.0.1 only. NEVER logs tokens / Authorization headers.

import os

# ---- Configuration (env-overridable) ---------------------------------------
HOST = os.environ.get("SIMULAR_HOST", "127.0.0.1")
PORT = int(os.environ.get("SIMULAR_PORT", "8799"))

# Firebase Web API key (from the Simular app bundle; public client key, not a secret).
FIREBASE_API_KEY = os.environ.get(
    "SIMULAR_FIREBASE_API_KEY", "AIzaSyA2PBi9b1fyxYnFXPiHl0Bl31ZHyBnhGpA"
)

# Simular cloud proxy base.
CLOUD_API_URL = os.environ.get(
    "SIMULAR_CLOUD_API_URL",
    "https://simular-cloud-api-ziuwwju2va-uc.a.run.app",
)

SECURETOKEN_URL = "https://securetoken.googleapis.com/v1/token"

# Where the Simular app persists the signed-in Firebase user (refresh token).
CREDENTIALS_PATH = os.environ.get(
    "SIMULAR_CREDENTIALS_PATH",
    os.path.join(os.path.expanduser("~"), ".simulang", "credentials.json"),
)

# Refresh the idToken when fewer than this many seconds remain.
REFRESH_SKEW_SECONDS = 300

# X-Goal header the app sends on chat generations.
X_GOAL = os.environ.get("SIMULAR_X_GOAL", "simular-cloud-chat-agent")

# Allowed upstream path prefixes (only model generation paths).
ALLOWED_PREFIXES = (
    "/v1/anthropic/",
    "/v1/google/",
)

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "gateway.log")

