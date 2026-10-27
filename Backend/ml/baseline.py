"""
PoseGuide - Baseline fixed-threshold classifier
================================================

Ported directly from the original on-device / Wokwi logic and the previous
FastAPI classifier, adapted to the 3-feature vector (flex sensor removed).

Pure function: numpy array (or list) in, dict out. No FastAPI dependency.
"""

from __future__ import annotations

import numpy as np

from .constants import (
    GOOD_POSTURE_TOLERANCE,
    SLOUCH_PITCH_THRESHOLD,
    FORWARD_HEAD_THRESHOLD,
    LATERAL_LEAN_THRESHOLD,
    CRITICAL_PITCH_THRESHOLD,
    CRITICAL_NECK_THRESHOLD,
    MAX_POSTURE_SCORE,
    PENALTY_PER_DEGREE_PITCH,
    PENALTY_PER_DEGREE_ROLL,
    PENALTY_PER_DEGREE_NECK,
)
from .features import IDX_TORSO_PITCH, IDX_TORSO_ROLL, IDX_NECK_RELATIVE


def is_critical(features) -> bool:
    """
    Safety override, checked IDENTICALLY by baseline and personalized layers.

    |torso_pitch| > 40  OR  neck_relative_pitch > 35  ->  Critical.
    """
    x = np.asarray(features, dtype=float)
    torso_pitch = x[IDX_TORSO_PITCH]
    neck_rel = x[IDX_NECK_RELATIVE]
    return abs(torso_pitch) > CRITICAL_PITCH_THRESHOLD or neck_rel > CRITICAL_NECK_THRESHOLD


def posture_score(features) -> int:
    """Continuous 0-100 posture score using the original penalty weights."""
    x = np.asarray(features, dtype=float)
    torso_pitch = abs(x[IDX_TORSO_PITCH])
    torso_roll = abs(x[IDX_TORSO_ROLL])
    neck_rel = x[IDX_NECK_RELATIVE]

    pitch_pen = max(0.0, torso_pitch - GOOD_POSTURE_TOLERANCE) * PENALTY_PER_DEGREE_PITCH
    roll_pen = max(0.0, torso_roll - GOOD_POSTURE_TOLERANCE) * PENALTY_PER_DEGREE_ROLL
    neck_pen = max(0.0, neck_rel - GOOD_POSTURE_TOLERANCE) * PENALTY_PER_DEGREE_NECK

    return int(max(0, round(MAX_POSTURE_SCORE - (pitch_pen + roll_pen + neck_pen))))


def classify_baseline(features) -> dict:
    """
    Fixed-threshold posture classification.

    Returns:
        {
          "model": "baseline",
          "condition": "good" | "slouching" | "forward_head" |
                       "lateral_lean" | "multiple_issues" | "critical",
          "score": int,
          "warnings": [str, ...],
          "angles": {"torso_pitch", "torso_roll", "neck_relative_pitch"},
        }
    """
    x = np.asarray(features, dtype=float)
    torso_pitch = x[IDX_TORSO_PITCH]
    torso_roll = x[IDX_TORSO_ROLL]
    neck_rel = x[IDX_NECK_RELATIVE]

    abs_pitch = abs(torso_pitch)
    abs_roll = abs(torso_roll)

    warnings: list[str] = []
    detected: list[str] = []

    if abs_pitch > SLOUCH_PITCH_THRESHOLD:
        detected.append("slouching")
        warnings.append(
            f"Slouching - torso pitch {abs_pitch:.1f}deg (>{SLOUCH_PITCH_THRESHOLD:.0f}deg)"
        )
    if neck_rel > FORWARD_HEAD_THRESHOLD:
        detected.append("forward_head")
        warnings.append(
            f"Forward head - neck deviation {neck_rel:.1f}deg (>{FORWARD_HEAD_THRESHOLD:.0f}deg)"
        )
    if abs_roll > LATERAL_LEAN_THRESHOLD:
        detected.append("lateral_lean")
        warnings.append(
            f"Lateral lean - torso roll {abs_roll:.1f}deg (>{LATERAL_LEAN_THRESHOLD:.0f}deg)"
        )

    # Critical overrides everything else.
    if is_critical(x):
        condition = "critical"
        warnings.insert(0, "CRITICAL posture - immediate correction required")
    elif len(detected) == 0:
        condition = "good"
    elif len(detected) == 1:
        condition = detected[0]
    else:
        condition = "multiple_issues"

    return {
        "model": "baseline",
        "condition": condition,
        "score": posture_score(x),
        "warnings": warnings,
        "angles": {
            "torso_pitch": round(float(torso_pitch), 2),
            "torso_roll": round(float(torso_roll), 2),
            "neck_relative_pitch": round(float(neck_rel), 2),
        },
    }
