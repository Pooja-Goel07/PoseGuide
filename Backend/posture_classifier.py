"""
PoseGuide – Posture Classification Engine
Analyses sensor data against clinical thresholds and computes a posture score.
"""

from models import SensorPacket, PostureClassification, PostureCondition
from config import (
    SLOUCH_PITCH_THRESHOLD,
    FORWARD_HEAD_THRESHOLD,
    LATERAL_LEAN_THRESHOLD,
    GOOD_POSTURE_TOLERANCE,
    FLEX_CURVATURE_WARN,
    MAX_POSTURE_SCORE,
    PENALTY_PER_DEGREE_PITCH,
    PENALTY_PER_DEGREE_ROLL,
    PENALTY_PER_DEGREE_NECK,
)


def classify_posture(packet: SensorPacket) -> PostureClassification:
    """
    Evaluate incoming sensor data and return a posture classification
    with score and human-readable warnings.
    """
    warnings: list[str] = []
    conditions_detected: list[PostureCondition] = []

    # ── Extract key angles ──────────────────────────────
    torso_pitch = abs(packet.torso.pitch)
    torso_roll = abs(packet.torso.roll)

    # Relative neck pitch = difference between neck and torso pitch
    # Positive value means the head is pitched forward relative to the torso
    relative_neck_pitch = abs(packet.neck.pitch - packet.torso.pitch)

    flex_value = packet.flex_value

    # ── Slouching detection ─────────────────────────────
    if torso_pitch > SLOUCH_PITCH_THRESHOLD:
        conditions_detected.append(PostureCondition.SLOUCHING)
        warnings.append(
            f"Slouching detected — torso pitch {torso_pitch:.1f}° "
            f"(threshold: {SLOUCH_PITCH_THRESHOLD}°)"
        )

    # ── Forward head posture ────────────────────────────
    if relative_neck_pitch > FORWARD_HEAD_THRESHOLD:
        conditions_detected.append(PostureCondition.FORWARD_HEAD)
        warnings.append(
            f"Forward head posture — neck deviation {relative_neck_pitch:.1f}° "
            f"(threshold: {FORWARD_HEAD_THRESHOLD}°)"
        )

    # ── Lateral lean ────────────────────────────────────
    if torso_roll > LATERAL_LEAN_THRESHOLD:
        conditions_detected.append(PostureCondition.LATERAL_LEAN)
        warnings.append(
            f"Lateral lean detected — torso roll {torso_roll:.1f}° "
            f"(threshold: {LATERAL_LEAN_THRESHOLD}°)"
        )

    # ── Flex sensor curvature ───────────────────────────
    if flex_value > FLEX_CURVATURE_WARN:
        warnings.append(
            f"High spinal curvature — flex reading {flex_value:.1f} "
            f"(threshold: {FLEX_CURVATURE_WARN})"
        )

    # ── Determine overall condition ─────────────────────
    if len(conditions_detected) == 0:
        condition = PostureCondition.GOOD
    elif len(conditions_detected) == 1:
        condition = conditions_detected[0]
    else:
        condition = PostureCondition.MULTIPLE_ISSUES

    # ── Compute posture score ───────────────────────────
    pitch_penalty = max(0, torso_pitch - GOOD_POSTURE_TOLERANCE) * PENALTY_PER_DEGREE_PITCH
    roll_penalty = max(0, torso_roll - GOOD_POSTURE_TOLERANCE) * PENALTY_PER_DEGREE_ROLL
    neck_penalty = max(0, relative_neck_pitch - GOOD_POSTURE_TOLERANCE) * PENALTY_PER_DEGREE_NECK

    total_penalty = pitch_penalty + roll_penalty + neck_penalty
    score = max(0, int(MAX_POSTURE_SCORE - total_penalty))

    return PostureClassification(
        condition=condition,
        slouch_angle=round(torso_pitch, 2),
        forward_head_angle=round(relative_neck_pitch, 2),
        lateral_lean_angle=round(torso_roll, 2),
        flex_curvature=round(flex_value, 2),
        score=score,
        warnings=warnings,
    )
