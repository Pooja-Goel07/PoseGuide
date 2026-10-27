"""
PoseGuide - FastAPI Backend (Assessment-6 prototype)
====================================================

Pipeline:

    ESP32 firmware ──HTTP POST JSON──▶  /api/sensor-data
                                          │  validate (fault handling)
                                          │  extract 3-D features
                                          │  classify (baseline + personalized)
                                          │  persist + cache
    React dashboard ──GET poll──▶  /api/latest, /api/status, /api/history

Two *different* kinds of "bad" are handled distinctly:
  * a broken sensor READING  -> rejected by validate_reading() (HTTP 400)
  * a real posture DEVIATION -> classified by the ML layer (HTTP 200)

Fault handling exposed to the dashboard:
  * invalid-reading rejection (count + last error)
  * sensor online/offline via staleness timeout (SENSOR_TIMEOUT_SECONDS)
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime
from typing import Any, Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import HOST, PORT, ALLOWED_ORIGINS
import database as db
from ml import extract_features, classify_baseline, classify_personalized
from ml.personalized import PersonalModel, fit_personal_model
from ml.constants import ANGLE_ABS_LIMIT, SENSOR_TIMEOUT_SECONDS, MIN_CALIBRATION_SAMPLES

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("poseguide")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB and restore any persisted calibration.
    db.init()
    saved = db.load_calibration()
    if saved is not None:
        try:
            STATE["personal_model"] = PersonalModel.from_dict(saved)
            logger.info("Loaded persisted calibration (tau=%.2f, n=%d)",
                        STATE["personal_model"].tau, STATE["personal_model"].n_samples)
        except Exception as e:
            logger.warning(f"Could not load calibration: {e}")
    logger.info("SQLite ready")
    yield


app = FastAPI(
    title="PoseGuide API",
    description="Real-time posture detection with baseline + personalized (Mahalanobis) classifiers.",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Runtime state (module-level so tests can inspect/reset it) ───────────
STATE: dict[str, Any] = {}


def reset_state():
    STATE.clear()
    STATE.update(
        {
            "latest_result": None,      # last valid SensorResult dict
            "last_valid_monotonic": None,  # time.monotonic() of last valid reading
            "last_valid_wall": None,    # ISO string for display
            "total_count": 0,           # total accepted readings
            "invalid_count": 0,         # total rejected readings
            "last_error": None,         # last rejection reason/detail
            "calibrating": False,
            "calib_samples": [],        # list[list[float]] collected while calibrating
            "personal_model": None,     # PersonalModel | None
        }
    )


reset_state()


# ── Validation (fault handling #1: invalid readings) ────────────────────
def validate_reading(data: Any) -> tuple[bool, Optional[str], Optional[str], Optional[tuple]]:
    """
    Validate a raw inbound payload.

    Returns (ok, reason, detail, angles). On success angles is
    (torso_pitch, torso_roll, neck_pitch). On failure the first three describe
    the fault and angles is None.
    """
    if not isinstance(data, dict):
        return False, "malformed_payload", "body is not a JSON object", None

    torso = data.get("torso")
    neck = data.get("neck")
    if not isinstance(torso, dict) or not isinstance(neck, dict):
        return False, "missing_field", "missing 'torso' or 'neck' object", None

    try:
        tp = float(torso["pitch"])
        tr = float(torso["roll"])
        np_ = float(neck["pitch"])
    except (KeyError, TypeError, ValueError):
        return False, "missing_field", "missing/invalid torso.pitch, torso.roll or neck.pitch", None

    for name, v in (("torso.pitch", tp), ("torso.roll", tr), ("neck.pitch", np_)):
        if not math.isfinite(v):
            return False, "non_finite", f"{name} is NaN/inf", None
    for name, v in (("torso.pitch", tp), ("torso.roll", tr), ("neck.pitch", np_)):
        if abs(v) > ANGLE_ABS_LIMIT:
            return False, "out_of_range", f"{name}={v} exceeds +/-{ANGLE_ABS_LIMIT:.0f} deg", None

    return True, None, None, (tp, tr, np_)


# ── Processing ──────────────────────────────────────────────────────────
def process_valid_reading(tp: float, tr: float, np_pitch: float) -> dict:
    """Classify a validated reading, update state + DB, return the full result."""
    features = extract_features(tp, tr, np_pitch)

    # Collect for calibration if a session is active.
    if STATE["calibrating"]:
        STATE["calib_samples"].append([float(features[0]), float(features[1]), float(features[2])])

    baseline = classify_baseline(features)
    personalized = classify_personalized(features, STATE["personal_model"])

    result = {
        "status": "ok",
        "timestamp": time.time(),
        "torso_pitch": round(float(features[0]), 2),
        "torso_roll": round(float(features[1]), 2),
        "neck_relative_pitch": round(float(features[2]), 2),
        "baseline": baseline,
        "personalized": personalized,
    }

    STATE["latest_result"] = result
    STATE["last_valid_monotonic"] = time.monotonic()
    STATE["last_valid_wall"] = datetime.now().isoformat(timespec="seconds")
    STATE["total_count"] += 1

    try:
        db.insert_reading(
            torso_pitch=result["torso_pitch"],
            torso_roll=result["torso_roll"],
            neck_relative_pitch=result["neck_relative_pitch"],
            baseline_condition=baseline["condition"],
            baseline_score=baseline["score"],
            personalized_condition=personalized["condition"],
            personalized_model=personalized["model"],
            mahalanobis=personalized.get("mahalanobis"),
        )
    except Exception as e:  # persistence must never break the live path
        logger.warning(f"DB insert failed: {e}")

    return result


def sensor_online() -> bool:
    ts = STATE["last_valid_monotonic"]
    if ts is None:
        return False
    return (time.monotonic() - ts) < SENSOR_TIMEOUT_SECONDS


# ── General ─────────────────────────────────────────────────────────────
@app.get("/", tags=["General"])
async def root():
    return {
        "service": "PoseGuide API",
        "version": app.version,
        "docs": "/docs",
        "endpoints": [
            "POST /api/sensor-data",
            "GET  /api/latest",
            "GET  /api/status",
            "GET  /api/history",
            "POST /api/calibrate/start",
            "POST /api/calibrate/stop",
            "GET  /api/calibrate/status",
        ],
    }


@app.get("/health", tags=["General"])
async def health():
    return {"status": "healthy"}


# ── Data ingest ─────────────────────────────────────────────────────────
@app.post("/api/sensor-data", tags=["Data"])
async def post_sensor_data(request: Request):
    """
    Receive a hardware reading, validate it, run both classifiers, persist,
    and return the result. Invalid readings are rejected with HTTP 400 and
    recorded as a fault WITHOUT corrupting the last-good state.
    """
    try:
        data = await request.json()
    except Exception:
        STATE["invalid_count"] += 1
        STATE["last_error"] = "malformed_payload: body is not valid JSON"
        return JSONResponse(
            status_code=400,
            content={"status": "rejected", "reason": "malformed_payload",
                     "detail": "body is not valid JSON"},
        )

    ok, reason, detail, angles = validate_reading(data)
    if not ok:
        STATE["invalid_count"] += 1
        STATE["last_error"] = f"{reason}: {detail}"
        logger.warning(f"Rejected reading -> {reason}: {detail}")
        return JSONResponse(
            status_code=400,
            content={"status": "rejected", "reason": reason, "detail": detail},
        )

    tp, tr, np_pitch = angles
    result = process_valid_reading(tp, tr, np_pitch)
    logger.info(
        "reading ok | baseline=%s personalized=%s",
        result["baseline"]["condition"], result["personalized"]["condition"],
    )
    return result


@app.get("/api/latest", tags=["Data"])
async def get_latest():
    if STATE["latest_result"] is None:
        return {"data": None, "message": "No sensor data received yet."}
    return STATE["latest_result"]


@app.get("/api/status", tags=["Data"])
async def get_status():
    """Device/actuator + fault status for the dashboard."""
    online = sensor_online()
    last_ts = STATE["last_valid_monotonic"]
    seconds_since = (time.monotonic() - last_ts) if last_ts is not None else None
    model: Optional[PersonalModel] = STATE["personal_model"]
    return {
        "sensor_online": online,
        "last_seen": STATE["last_valid_wall"],
        "seconds_since_last": round(seconds_since, 2) if seconds_since is not None else None,
        "timeout_seconds": SENSOR_TIMEOUT_SECONDS,
        "total_readings": STATE["total_count"],
        "invalid_readings": STATE["invalid_count"],
        "last_error": STATE["last_error"],
        "calibrated": model is not None,
        "calibrating": STATE["calibrating"],
        "tau": round(model.tau, 3) if model else None,
        "calibration_samples": model.n_samples if model else 0,
    }


@app.get("/api/history", tags=["Data"])
async def get_history(limit: int = 100):
    return db.get_history(limit)


# ── Calibration ─────────────────────────────────────────────────────────
@app.post("/api/calibrate/start", tags=["Calibration"])
async def calibrate_start():
    STATE["calibrating"] = True
    STATE["calib_samples"] = []
    logger.info("Calibration started - collecting samples")
    return {"status": "calibrating", "samples_collected": 0,
            "min_required": MIN_CALIBRATION_SAMPLES}


@app.post("/api/calibrate/stop", tags=["Calibration"])
async def calibrate_stop():
    STATE["calibrating"] = False
    samples = STATE["calib_samples"]
    model = fit_personal_model(samples)
    if model is None:
        reason = (f"need >= {MIN_CALIBRATION_SAMPLES} valid samples "
                  f"(got {len(samples)}) or covariance was singular")
        logger.warning(f"Calibration failed: {reason}")
        return {"calibrated": False, "reason": reason,
                "samples_collected": len(samples)}

    STATE["personal_model"] = model
    db.save_calibration(model.to_dict())
    logger.info("Calibration complete: tau=%.2f n=%d", model.tau, model.n_samples)
    return {
        "calibrated": True,
        "tau": round(model.tau, 3),
        "n_samples": model.n_samples,
        "mu": [round(v, 3) for v in model.mu.tolist()],
    }


@app.get("/api/calibrate/status", tags=["Calibration"])
async def calibrate_status():
    model: Optional[PersonalModel] = STATE["personal_model"]
    return {
        "calibrating": STATE["calibrating"],
        "samples_collected": len(STATE["calib_samples"]),
        "min_required": MIN_CALIBRATION_SAMPLES,
        "calibrated": model is not None,
        "tau": round(model.tau, 3) if model else None,
        "n_samples": model.n_samples if model else 0,
    }


@app.post("/api/calibrate/reset", tags=["Calibration"])
async def calibrate_reset():
    STATE["personal_model"] = None
    STATE["calib_samples"] = []
    STATE["calibrating"] = False
    db.clear_calibration()
    return {"status": "reset", "calibrated": False}


# ── Analytics ───────────────────────────────────────────────────────────
@app.get("/api/analytics/hourly", tags=["Analytics"])
async def analytics_hourly(hours: int = 8):
    return db.get_hourly_averages(hours)


@app.get("/api/analytics/stats", tags=["Analytics"])
async def analytics_stats():
    return db.get_session_stats()


@app.get("/api/analytics/distribution", tags=["Analytics"])
async def analytics_distribution():
    return db.get_condition_distribution()


# ── Entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import logging as _logging

    db.init()
    _logging.getLogger("uvicorn.access").setLevel(_logging.WARNING)
    logger.info("Starting PoseGuide backend on http://localhost:%d", PORT)
    logger.info("Swagger UI -> http://localhost:%d/docs", PORT)
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True, log_config=None)
