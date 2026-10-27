"""
PoseGuide - Pydantic data models (3-feature iteration)
======================================================

Flex sensor removed this iteration -> feature vector is 3-D:
    [torso_pitch, torso_roll, neck_relative_pitch]

The inbound sensor payload matches the data contract:

    {
      "torso": { "pitch": -2.3, "roll": 1.1 },
      "neck":  { "pitch": 5.6 },
      "timestamp": 1234567
    }

Note: raw payload validation (NaN / out-of-range / missing fields) is handled
explicitly in the API layer so a bad reading is *flagged* as a distinct fault
rather than raising an opaque 422 -- see main.py:validate_reading().
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class TorsoIMU(BaseModel):
    pitch: float = Field(..., description="Torso forward/backward tilt (deg)")
    roll: float = Field(..., description="Torso side-to-side tilt (deg)")


class NeckIMU(BaseModel):
    pitch: float = Field(..., description="Neck forward/backward tilt (deg)")


class SensorPacket(BaseModel):
    """Inbound hardware reading (documentation / Swagger schema)."""
    torso: TorsoIMU
    neck: NeckIMU
    timestamp: Optional[float] = Field(None, description="Firmware millis() timestamp")


class ClassificationResult(BaseModel):
    """One classifier's verdict (baseline or personalized)."""
    model: str
    condition: str
    score: int
    warnings: list[str] = Field(default_factory=list)
    angles: dict = Field(default_factory=dict)
    # personalized-only extras
    mahalanobis: Optional[float] = None
    tau: Optional[float] = None
    n_calibration_samples: Optional[int] = None
    fallback: Optional[bool] = None
    reason: Optional[str] = None


class SensorResult(BaseModel):
    """Full response for a processed reading: both classifiers side by side."""
    status: str = "ok"
    timestamp: float
    torso_pitch: float
    torso_roll: float
    neck_relative_pitch: float
    baseline: ClassificationResult
    personalized: ClassificationResult


class RejectedReading(BaseModel):
    """Returned (HTTP 400) when a reading fails physical validation."""
    status: str = "rejected"
    reason: str
    detail: str
