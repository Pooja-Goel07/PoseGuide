"""
PoseGuide – Configuration Constants
Posture thresholds and server settings.
"""

# ── Server ──────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000

# ── CORS ────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ── Posture Thresholds (degrees) ────────────────────────
# Based on clinical reference values for upper-body posture
SLOUCH_PITCH_THRESHOLD = 25.0        # Torso forward pitch > 25° → slouching
FORWARD_HEAD_THRESHOLD = 20.0        # Relative neck pitch > 20° → forward head
LATERAL_LEAN_THRESHOLD = 15.0        # Torso roll > 15° → lateral lean
GOOD_POSTURE_TOLERANCE = 10.0        # All angles within ±10° → good posture

# ── Flex Sensor ─────────────────────────────────────────
FLEX_CURVATURE_WARN = 40.0           # Flex value above which curvature is concerning

# ── Scoring ─────────────────────────────────────────────
MAX_POSTURE_SCORE = 100
PENALTY_PER_DEGREE_PITCH = 1.5       # Score penalty per degree of slouch
PENALTY_PER_DEGREE_ROLL = 1.2        # Score penalty per degree of lean
PENALTY_PER_DEGREE_NECK = 1.8        # Score penalty per degree of forward head
