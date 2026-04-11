"""
PoseGuide – FastAPI Backend Server

Architecture (simplified):
  ESP32   ──ws──▶  /ws/esp32        (hardware sends at 50Hz)
  Browser ──POST▶  /api/sensor-data  (Swagger UI testing)
  Frontend ──GET▶  /api/latest       (polling every 200ms)
"""

import json
import logging
from datetime import datetime
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


from config import HOST, PORT, ALLOWED_ORIGINS
from models import SensorPacket, PostureResponse
from posture_classifier import classify_posture
import database as db

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("poseguide")

# ── FastAPI App ─────────────────────────────────────────
app = FastAPI(
    title="PoseGuide API",
    description=(
        "Real-Time Posture Detection & Feedback System.\n\n"
        "**Swagger testing flow:**\n"
        "1. POST sensor data to `/api/sensor-data`\n"
        "2. The frontend polls `/api/latest` every 200ms and displays results automatically."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared State ────────────────────────────────────────
latest_response: dict | None = None
dashboard_clients: Set[WebSocket] = set()  # kept for ESP32 live-streaming path


@app.on_event("startup")
async def startup():
    db.init()
    logger.info("💾 SQLite database ready")


# ── Helper ──────────────────────────────────────────────
def process_sensor_packet(packet: SensorPacket) -> dict:
    """Classify posture, cache result, save to DB."""
    global latest_response
    classification = classify_posture(packet)
    response = PostureResponse(sensor_data=packet, classification=classification)
    result = json.loads(response.model_dump_json())
    latest_response = result

    # Persist to SQLite for analytics
    try:
        db.insert_reading(
            score=classification.score,
            condition=classification.condition.value,
            torso_pitch=abs(packet.torso.pitch),
            torso_roll=abs(packet.torso.roll),
            neck_pitch=abs(packet.neck.pitch),
            neck_roll=abs(packet.neck.roll),
            flex_value=packet.flex_value,
        )
    except Exception as e:
        logger.warning(f"DB insert failed: {e}")

    return result


# ── REST Endpoints ──────────────────────────────────────

@app.get("/", tags=["General"])
async def root():
    return {
        "service": "PoseGuide API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "swagger_ui":   "http://localhost:8000/docs",
            "latest_data":  "GET  /api/latest",
            "test_input":   "POST /api/sensor-data",
            "esp32_ws":     "ws://localhost:8000/ws/esp32",
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    return {"status": "healthy"}


@app.get("/api/latest", tags=["Data"])
async def get_latest():
    """
    **Frontend polls this every 200ms.**

    Returns the most recently received and classified posture data.
    Returns 204 No Content when no data has been received yet.
    """
    if latest_response is None:
        return {"data": None, "message": "No sensor data received yet. POST to /api/sensor-data to test."}
    return latest_response


@app.post("/api/sensor-data", tags=["Data"])
async def post_sensor_data(packet: SensorPacket):
    """
    **Use this in Swagger UI to simulate sensor data without hardware.**

    Accepts raw sensor readings, classifies posture, caches the result.
    The frontend will pick it up on its next poll of `/api/latest`.

    Example body:
    ```json
    {
      "torso": {"pitch": 30.0, "roll": 5.0, "yaw": 0.0},
      "neck":  {"pitch": 20.0, "roll": 3.0, "yaw": 0.0},
      "flex_value": 45.0,
      "timestamp": 1712760000000
    }
    ```
    """
    result = process_sensor_packet(packet)
    logger.info(
        f"📥 REST sensor data → condition={result['classification']['condition']}  "
        f"score={result['classification']['score']}"
    )
    return result

# ── Analytics Endpoints ─────────────────────────────────

@app.get("/api/analytics/hourly", tags=["Analytics"])
async def analytics_hourly(hours: int = 8):
    """Average posture score per hour for the last N hours (bar chart data)."""
    return db.get_hourly_averages(hours)


@app.get("/api/analytics/stats", tags=["Analytics"])
async def analytics_stats():
    """Session summary: total readings, good %, average score, duration."""
    return db.get_session_stats()


@app.get("/api/analytics/distribution", tags=["Analytics"])
async def analytics_distribution():
    """Posture condition counts for pie chart."""
    return db.get_condition_distribution()


# ── WebSocket: ESP32 Hardware ───────────────────────────
@app.websocket("/ws/esp32")
async def esp32_websocket(websocket: WebSocket):
    """
    ESP32 hardware connects here and streams JSON at ~50Hz.
    Data is classified and cached in `latest_response` for the frontend to poll.
    """
    await websocket.accept()
    logger.info("🔌 ESP32 connected")
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                packet = SensorPacket(**data)
                process_sensor_packet(packet)
            except Exception as e:
                logger.warning(f"Invalid ESP32 packet: {e}")
    except WebSocketDisconnect:
        logger.info("🔌 ESP32 disconnected")
    except Exception as e:
        logger.error(f"ESP32 WebSocket error: {e}")


# ── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import logging as _logging
    # Init SQLite
    db.init()
    logger.info("💾 SQLite database ready")
    # Silence the noisy per-request access logs (polling every 200ms = 5 lines/sec)
    _logging.getLogger("uvicorn.access").setLevel(_logging.WARNING)
    logger.info("🚀 Starting PoseGuide Backend Server")
    logger.info("📖 Swagger UI  → http://localhost:8000/docs")
    logger.info("📡 Latest data → GET  http://localhost:8000/api/latest")
    logger.info("🧪 Test input  → POST http://localhost:8000/api/sensor-data")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True,
                log_config=None)  # use our own logging config above
