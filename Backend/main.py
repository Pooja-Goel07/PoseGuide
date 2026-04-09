"""
PoseGuide – FastAPI Backend Server
Handles WebSocket connections from ESP32 hardware and React dashboard clients.

Architecture:
  ESP32  ──ws──▶  /ws/esp32      (hardware sends sensor data)
                     │
                     ▼
              posture_classifier   (analyse & score)
                     │
                     ▼
  React  ◀──ws──  /ws/dashboard   (broadcast to all dashboard clients)
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import HOST, PORT, ALLOWED_ORIGINS
from models import SensorPacket, PostureResponse
from posture_classifier import classify_posture

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
    description="Real-Time Posture Detection & Feedback System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── State ───────────────────────────────────────────────
dashboard_clients: Set[WebSocket] = set()
latest_response: dict | None = None


# ── REST Endpoints ──────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "PoseGuide API",
        "version": "1.0.0",
        "status": "running",
        "dashboard_clients": len(dashboard_clients),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/latest")
async def get_latest():
    """Return the most recent posture data (for polling fallback)."""
    if latest_response is None:
        return {"message": "No data received yet"}
    return latest_response


# ── WebSocket: ESP32 Hardware ───────────────────────────
@app.websocket("/ws/esp32")
async def esp32_websocket(websocket: WebSocket):
    """
    Receives sensor data from ESP32 hardware.
    Classifies posture and broadcasts to all dashboard clients.
    """
    await websocket.accept()
    logger.info("🔌 ESP32 connected")

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                packet = SensorPacket(**data)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Invalid packet from ESP32: {e}")
                continue

            # Classify posture
            classification = classify_posture(packet)

            # Build response
            response = PostureResponse(
                sensor_data=packet,
                classification=classification,
            )
            response_json = response.model_dump_json()

            # Cache latest
            global latest_response
            latest_response = json.loads(response_json)

            # Broadcast to all dashboard clients
            disconnected: list[WebSocket] = []
            for client in dashboard_clients:
                try:
                    await client.send_text(response_json)
                except Exception:
                    disconnected.append(client)

            for client in disconnected:
                dashboard_clients.discard(client)

    except WebSocketDisconnect:
        logger.info("🔌 ESP32 disconnected")
    except Exception as e:
        logger.error(f"ESP32 WebSocket error: {e}")


# ── WebSocket: React Dashboard ──────────────────────────
@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """
    Dashboard clients connect here to receive real-time posture updates.
    """
    await websocket.accept()
    dashboard_clients.add(websocket)
    logger.info(f"📊 Dashboard client connected (total: {len(dashboard_clients)})")

    # Send latest data immediately if available
    if latest_response is not None:
        try:
            await websocket.send_json(latest_response)
        except Exception:
            pass

    try:
        while True:
            # Keep connection alive; dashboard is read-only
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_clients.discard(websocket)
        logger.info(f"📊 Dashboard client disconnected (total: {len(dashboard_clients)})")
    except Exception:
        dashboard_clients.discard(websocket)


# ── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting PoseGuide Backend Server")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
