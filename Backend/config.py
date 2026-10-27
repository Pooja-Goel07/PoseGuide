"""
PoseGuide - Server configuration
================================

Posture thresholds now live in ml/constants.py (single source of truth shared
with the ML layer, the dataset generator and the firmware). This file holds
only server/transport settings.
"""

# ── Server ──────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000

# ── CORS ────────────────────────────────────────────────
# Dashboard dev server runs on port 3000 (see frontend/vite.config.ts).
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",   # Vite default, in case the port is changed
    "http://127.0.0.1:5173",
]
