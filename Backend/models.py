"""
PoseGuide – Pydantic Data Models
Typed schemas for sensor data, posture classification, and API responses.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class PostureCondition(str, Enum):
    """Enumeration of detectable posture conditions."""
    GOOD = "good"
    SLOUCHING = "slouching"
    FORWARD_HEAD = "forward_head"
    LATERAL_LEAN = "lateral_lean"
    MULTIPLE_ISSUES = "multiple_issues"


class IMUData(BaseModel):
    """Orientation angles from a single MPU-6050 sensor."""
    pitch: float = Field(..., description="Forward/backward tilt in degrees")
    roll: float = Field(..., description="Side-to-side tilt in degrees")
    yaw: float = Field(..., description="Rotational orientation in degrees")


class SensorPacket(BaseModel):
    """
    Complete data packet received from the ESP32.
    Contains readings from both IMU sensors and the flex sensor.
    """
    torso: IMUData = Field(..., description="MPU #1 – T4 upper back")
    neck: IMUData = Field(..., description="MPU #2 – C7 neck base")
    flex_value: float = Field(0.0, description="Flex sensor curvature reading")
    timestamp: Optional[float] = Field(None, description="ESP32 millis() timestamp")


class PostureClassification(BaseModel):
    """Result of posture analysis."""
    condition: PostureCondition
    slouch_angle: float = Field(0.0, description="Torso pitch deviation")
    forward_head_angle: float = Field(0.0, description="Relative neck pitch deviation")
    lateral_lean_angle: float = Field(0.0, description="Torso roll deviation")
    flex_curvature: float = Field(0.0, description="Spinal curvature from flex sensor")
    score: int = Field(100, ge=0, le=100, description="Posture score 0–100")
    warnings: list[str] = Field(default_factory=list)


class PostureResponse(BaseModel):
    """
    Combined response broadcast to the React dashboard via WebSocket.
    Includes raw sensor data and classification results.
    """
    sensor_data: SensorPacket
    classification: PostureClassification
