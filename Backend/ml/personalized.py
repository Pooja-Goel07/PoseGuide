"""
PoseGuide - Personalized (unsupervised) posture model
=====================================================

This is the novel contribution of the prototype. Instead of one-size-fits-all
fixed thresholds, it learns each user's *own* neutral sitting posture during a
short calibration window and flags statistically unusual deviations from it.

Method
------
1. Calibration collects feature vectors  x = [torso_pitch, torso_roll,
   neck_relative_pitch]  while the user sits normally.
2. Fit a Gaussian baseline: mean vector mu and covariance Sigma (numpy).
3. Score a new reading with the Mahalanobis distance
       D_M(x) = sqrt( (x-mu)^T Sigma^-1 (x-mu) )
4. Personal threshold tau_personal = 95th percentile of the D_M values over the
   calibration set itself.
5. Flag "personalized_deviation" when  D_M > tau_personal.
6. Safety override is non-negotiable: |torso_pitch| > 40 or
   neck_relative_pitch > 35 -> "critical", regardless of D_M.
7. Before calibration (or with too few / degenerate samples) fall back cleanly
   to the baseline classifier and report model == "baseline".

Design note (intentional scope reduction): in the original research design this
personalization ran fully on-device (ESP32/edge) for privacy. This prototype
iteration deliberately hosts it in the backend to make it buildable and testable
in the available time. Moving it back on-device is a listed Future Enhancement.

Pure functions / a plain dataclass -- no FastAPI or DB dependency here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .constants import (
    MIN_CALIBRATION_SAMPLES,
    PERSONAL_PERCENTILE,
    COVARIANCE_RIDGE,
)
from .baseline import classify_baseline, is_critical


@dataclass
class PersonalModel:
    """A fitted per-user posture baseline. Serializable for DB persistence."""

    mu: np.ndarray            # shape (3,)
    inv_cov: np.ndarray       # shape (3, 3)
    tau: float                # personalized deviation threshold
    n_samples: int            # calibration sample count

    # ── Persistence helpers ─────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "mu": self.mu.tolist(),
            "inv_cov": self.inv_cov.tolist(),
            "tau": float(self.tau),
            "n_samples": int(self.n_samples),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PersonalModel":
        return cls(
            mu=np.asarray(d["mu"], dtype=float),
            inv_cov=np.asarray(d["inv_cov"], dtype=float),
            tau=float(d["tau"]),
            n_samples=int(d["n_samples"]),
        )


def mahalanobis(x, mu: np.ndarray, inv_cov: np.ndarray) -> float:
    """Mahalanobis distance of x from a distribution (mu, inv_cov)."""
    diff = np.asarray(x, dtype=float) - mu
    d2 = float(diff @ inv_cov @ diff)
    # Numerical guard: tiny negatives from round-off become 0.
    return float(np.sqrt(max(d2, 0.0)))


def fit_personal_model(samples) -> Optional[PersonalModel]:
    """
    Fit mu, Sigma^-1 and tau from calibration samples.

    Args:
        samples: array-like of shape (n, 3).

    Returns:
        A PersonalModel, or None if there are too few samples or Sigma is
        singular/degenerate (caller must then fall back to baseline).
    """
    X = np.asarray(samples, dtype=float)
    if X.ndim != 2 or X.shape[0] < MIN_CALIBRATION_SAMPLES or X.shape[1] != 3:
        return None

    mu = X.mean(axis=0)

    # Covariance + ridge on the diagonal so a near-constant feature during
    # calibration cannot make Sigma singular.
    cov = np.cov(X, rowvar=False)
    cov = cov + COVARIANCE_RIDGE * np.eye(cov.shape[0])

    try:
        inv_cov = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(inv_cov)):
        return None

    # tau = 95th percentile of in-calibration Mahalanobis distances.
    diffs = X - mu
    d2 = np.einsum("ij,jk,ik->i", diffs, inv_cov, diffs)
    dists = np.sqrt(np.clip(d2, 0.0, None))
    tau = float(np.percentile(dists, PERSONAL_PERCENTILE))

    return PersonalModel(mu=mu, inv_cov=inv_cov, tau=tau, n_samples=int(X.shape[0]))


def classify_personalized(features, model: Optional[PersonalModel]) -> dict:
    """
    Personalized classification with baseline fallback + safety override.

    Returns a dict shaped like the baseline result but with model ==
    "personalized" and extra "mahalanobis" / "tau" fields when a model exists.
    When no usable model exists it returns the baseline result verbatim
    (model == "baseline") so the caller/UI can honestly show which ran.
    """
    x = np.asarray(features, dtype=float)

    # No calibration yet -> honest baseline fallback.
    if model is None:
        result = classify_baseline(x)
        result["fallback"] = True
        result["reason"] = "not_calibrated"
        return result

    d_m = mahalanobis(x, model.mu, model.inv_cov)

    # Safety override is checked identically to the baseline's critical check
    # and can never be suppressed by the personalized layer.
    if is_critical(x):
        condition = "critical"
        warnings = ["CRITICAL posture - immediate correction required"]
    elif d_m > model.tau:
        condition = "personalized_deviation"
        warnings = [
            f"Personalized deviation - D_M {d_m:.2f} exceeds tau {model.tau:.2f}"
        ]
    else:
        condition = "good"
        warnings = []

    # Reuse the baseline score so both cards show a comparable 0-100 number.
    base = classify_baseline(x)

    return {
        "model": "personalized",
        "condition": condition,
        "score": base["score"],
        "warnings": warnings,
        "mahalanobis": round(d_m, 3),
        "tau": round(model.tau, 3),
        "n_calibration_samples": model.n_samples,
        "angles": base["angles"],
        "fallback": False,
    }
