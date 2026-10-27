"""
PoseGuide - Feature extraction & synthetic posture generation
=============================================================

Pure functions only. No FastAPI / HTTP / DB dependencies so this is directly
unit-testable and reusable by the offline dataset generator.
"""

from __future__ import annotations

import math
import random
from typing import Optional

import numpy as np

from .constants import POSTURE_STATES, STATE_WEIGHTS

# Feature vector index convention -- import these instead of hard-coding 0/1/2.
IDX_TORSO_PITCH = 0
IDX_TORSO_ROLL = 1
IDX_NECK_RELATIVE = 2
FEATURE_NAMES = ("torso_pitch", "torso_roll", "neck_relative_pitch")


def neck_relative_pitch(torso_pitch: float, neck_pitch: float) -> float:
    """Derived server-side per the data contract: |neck.pitch - torso.pitch|."""
    return abs(neck_pitch - torso_pitch)


def extract_features(torso_pitch: float, torso_roll: float, neck_pitch: float) -> np.ndarray:
    """
    Build the 3-D feature vector from raw sensor angles.

        x = [torso_pitch (signed), torso_roll (signed), neck_relative_pitch (abs)]
    """
    return np.array(
        [
            float(torso_pitch),
            float(torso_roll),
            neck_relative_pitch(torso_pitch, neck_pitch),
        ],
        dtype=float,
    )


def is_finite_reading(torso_pitch: float, torso_roll: float, neck_pitch: float) -> bool:
    """True only if every raw angle is a finite number (rejects NaN / inf)."""
    return all(math.isfinite(v) for v in (torso_pitch, torso_roll, neck_pitch))


# ── Synthetic posture generator ─────────────────────────────────────────
# Mirrors the ESP32 firmware. Given a state name it returns plausible raw
# sensor angles (torso.pitch, torso.roll, neck.pitch). The firmware uses the
# exact same POSTURE_STATES parameters so live and offline data match.

def sample_state(state: str, rng: Optional[random.Random] = None) -> dict:
    """Return one raw reading {'torso_pitch','torso_roll','neck_pitch'} for a state."""
    rng = rng or random
    params = POSTURE_STATES[state]
    torso_pitch = rng.gauss(*params["pitch"])
    torso_roll = rng.gauss(*params["roll"])
    neck_offset = rng.gauss(*params["neck"])
    # 50% chance a lateral lean tips to the opposite side, so roll is bidirectional.
    if state == "lateral_lean" and rng.random() < 0.5:
        torso_roll = -torso_roll
    neck_pitch = torso_pitch + neck_offset
    return {
        "torso_pitch": round(torso_pitch, 2),
        "torso_roll": round(torso_roll, 2),
        "neck_pitch": round(neck_pitch, 2),
        "state": state,
    }


def choose_state(rng: Optional[random.Random] = None) -> str:
    """Pick a posture state according to STATE_WEIGHTS."""
    rng = rng or random
    states = list(STATE_WEIGHTS.keys())
    weights = list(STATE_WEIGHTS.values())
    return rng.choices(states, weights=weights, k=1)[0]


def sample_reading(rng: Optional[random.Random] = None) -> dict:
    """Pick a weighted-random state and return one raw reading for it."""
    return sample_state(choose_state(rng), rng)
