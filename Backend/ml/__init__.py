"""
PoseGuide ML package
====================

Isolated, FastAPI-free posture-classification logic so it is directly unit
testable and could later be moved back on-device.

  * constants     - all thresholds / generation params (single source of truth)
  * features      - feature extraction + synthetic posture generation
  * baseline      - fixed-threshold classifier (3-feature)
  * personalized  - Mahalanobis-distance personalized model + calibration
"""

from .features import (
    extract_features,
    neck_relative_pitch,
    is_finite_reading,
    sample_reading,
    sample_state,
    choose_state,
    FEATURE_NAMES,
)
from .baseline import classify_baseline, is_critical, posture_score
from .personalized import (
    PersonalModel,
    fit_personal_model,
    classify_personalized,
    mahalanobis,
)

__all__ = [
    "extract_features",
    "neck_relative_pitch",
    "is_finite_reading",
    "sample_reading",
    "sample_state",
    "choose_state",
    "FEATURE_NAMES",
    "classify_baseline",
    "is_critical",
    "posture_score",
    "PersonalModel",
    "fit_personal_model",
    "classify_personalized",
    "mahalanobis",
]
