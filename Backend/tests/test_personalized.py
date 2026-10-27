"""
Personalized (Mahalanobis) model tests: calibration fitting, too-few-samples
fallback, the value-add over baseline (flagging a deviation the fixed
thresholds miss), and the non-negotiable safety override.
"""

import random

import numpy as np

from ml import extract_features, classify_personalized, sample_state
from ml.personalized import fit_personal_model


def _calibration_samples(state="normal", n=200, seed=1):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        r = sample_state(state, rng)
        out.append(extract_features(r["torso_pitch"], r["torso_roll"], r["neck_pitch"]))
    return np.array(out)


# ── Fitting ─────────────────────────────────────────────────────────────
def test_fit_returns_model_with_enough_samples():
    model = fit_personal_model(_calibration_samples(n=200))
    assert model is not None
    assert model.tau > 0
    assert model.n_samples == 200


def test_fit_returns_none_with_too_few_samples():
    # Below MIN_CALIBRATION_SAMPLES -> refuse to build a model.
    assert fit_personal_model(_calibration_samples(n=5)) is None


# ── Fallback ────────────────────────────────────────────────────────────
def test_fallback_to_baseline_when_uncalibrated():
    res = classify_personalized(extract_features(2.0, 1.0, 7.0), None)
    assert res["model"] == "baseline"
    assert res["fallback"] is True
    assert res["reason"] == "not_calibrated"


# ── Value-add over baseline ─────────────────────────────────────────────
def test_personalized_flags_deviation_missed_by_baseline():
    """
    A reading UNDER every fixed threshold (pitch<25, roll<15, neck<20) but far
    from a tight personal baseline must be flagged 'personalized_deviation'
    even though the baseline classifier calls it 'good'. This is the whole
    point of personalization.
    """
    from ml import classify_baseline

    model = fit_personal_model(_calibration_samples(state="normal", n=200))
    x = extract_features(18.0, 10.0, 18.0)  # sub-threshold for baseline

    assert classify_baseline(x)["condition"] == "good"
    res = classify_personalized(x, model)
    assert res["model"] == "personalized"
    assert res["condition"] == "personalized_deviation"
    assert res["mahalanobis"] > res["tau"]


def test_personalized_accepts_normal_reading():
    model = fit_personal_model(_calibration_samples(state="normal", n=200))
    res = classify_personalized(extract_features(3.0, 0.0, 5.0), model)
    assert res["condition"] == "good"


# ── Safety override is non-negotiable ───────────────────────────────────
def test_safety_override_forces_critical():
    """Even with a wide/loose calibration, a critical angle must read critical."""
    model = fit_personal_model(_calibration_samples(state="critical", n=200))
    # pitch 46 > 40 -> critical regardless of Mahalanobis distance
    res = classify_personalized(extract_features(46.0, 0.0, 56.0), model)
    assert res["condition"] == "critical"


def test_safety_override_matches_baseline_check():
    """Personalized critical threshold identical to the baseline's."""
    from ml.baseline import is_critical

    model = fit_personal_model(_calibration_samples(n=200))
    x = extract_features(41.0, 0.0, 46.0)
    assert is_critical(x)
    assert classify_personalized(x, model)["condition"] == "critical"
