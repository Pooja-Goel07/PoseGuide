"""
PoseGuide - ML Constants (single source of truth)
==================================================

Every threshold, penalty weight, and synthetic-generation parameter used by the
ML layer lives here so the baseline classifier, the personalized model, the
synthetic dataset generator, and the ESP32 firmware all agree on the same
numbers.

Feature vector (3D, this iteration -- NO flex sensor):

    x = [torso_pitch, torso_roll, neck_relative_pitch]

  * torso_pitch  : signed forward/backward tilt of the T4 torso IMU (deg)
  * torso_roll   : signed left/right tilt of the T4 torso IMU (deg)
  * neck_relative_pitch : |neck.pitch - torso.pitch| (deg), derived server-side

The baseline classifier applies abs() to pitch/roll internally where its
thresholds require it; the feature vector itself keeps torso pitch/roll signed
so the personalized (Mahalanobis) model can learn a *directional* baseline
(e.g. a user who habitually leans slightly left).
"""

# ── Baseline posture thresholds (degrees) ───────────────────────────────
# Ported unchanged from the original fixed-threshold classifier.
GOOD_POSTURE_TOLERANCE = 10.0   # |angle| within this counts as neutral
SLOUCH_PITCH_THRESHOLD = 25.0   # |torso_pitch| >  25 -> slouching
FORWARD_HEAD_THRESHOLD = 20.0   # neck_relative_pitch > 20 -> forward head
LATERAL_LEAN_THRESHOLD = 15.0   # |torso_roll| > 15 -> lateral lean

# ── Safety override (non-negotiable, identical for both classifiers) ─────
CRITICAL_PITCH_THRESHOLD = 40.0  # |torso_pitch| > 40 -> Critical
CRITICAL_NECK_THRESHOLD = 35.0   # neck_relative_pitch > 35 -> Critical

# ── Scoring ─────────────────────────────────────────────────────────────
MAX_POSTURE_SCORE = 100
PENALTY_PER_DEGREE_PITCH = 1.5
PENALTY_PER_DEGREE_ROLL = 1.2
PENALTY_PER_DEGREE_NECK = 1.8

# ── Physical validity limits (used by backend validation) ───────────────
# A single MPU-6050 orientation angle physically cannot exceed +/-180 deg.
ANGLE_ABS_LIMIT = 180.0

# ── Personalized model ──────────────────────────────────────────────────
# Minimum calibration samples before a covariance matrix is trustworthy.
# Below this we refuse to build a personalized model and fall back to baseline.
MIN_CALIBRATION_SAMPLES = 30
# Percentile of in-calibration Mahalanobis distances used as the personal
# deviation threshold tau_personal.
PERSONAL_PERCENTILE = 95.0
# Ridge term added to the covariance diagonal to keep Sigma invertible when a
# feature has near-zero variance (guards against a singular matrix).
COVARIANCE_RIDGE = 1e-6

# ── Fault detection ─────────────────────────────────────────────────────
# If no valid reading arrives within this many seconds, the sensor is "offline".
SENSOR_TIMEOUT_SECONDS = 8.0

# ── Synthetic posture generator ─────────────────────────────────────────
# Shared by data/generate_dataset.py AND mirrored in the ESP32 firmware so the
# live demo, the offline dataset, and the firmware all produce the same kind of
# posture behaviour. Each state defines Gaussian (mean, std) for the three RAW
# quantities the hardware reports: torso.pitch, torso.roll, neck.pitch.
#
# neck.pitch is expressed as an OFFSET added to torso.pitch, because the neck
# IMU sits on top of the torso; neck_relative_pitch = |neck.pitch - torso.pitch|
# then recovers the intended relative angle.
POSTURE_STATES = {
    #                torso_pitch     torso_roll      neck_offset
    "normal":       {"pitch": (3.0, 3.0),  "roll": (0.0, 3.0),  "neck": (5.0, 3.0)},
    "slouch":       {"pitch": (32.0, 4.0), "roll": (2.0, 4.0),  "neck": (8.0, 3.0)},
    "forward_head": {"pitch": (8.0, 3.0),  "roll": (1.0, 3.0),  "neck": (26.0, 4.0)},
    "lateral_lean": {"pitch": (5.0, 3.0),  "roll": (20.0, 4.0), "neck": (6.0, 3.0)},
    "critical":     {"pitch": (46.0, 4.0), "roll": (3.0, 4.0),  "neck": (10.0, 3.0)},
}

# Relative frequency each state is visited by the generator / firmware.
# Heavily weighted toward "normal" so the baseline looks like real sitting.
STATE_WEIGHTS = {
    "normal": 0.55,
    "slouch": 0.15,
    "forward_head": 0.13,
    "lateral_lean": 0.12,
    "critical": 0.05,
}
