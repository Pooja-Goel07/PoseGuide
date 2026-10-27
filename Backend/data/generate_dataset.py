"""
PoseGuide - Synthetic dataset generator
=======================================

Produces `poseguide_dataset.csv` using the SAME posture-state parameters
(ml.constants.POSTURE_STATES) that the ESP32 firmware and the live backend use,
so the offline dataset, the live demo, and the firmware all behave consistently.

Columns:
    torso_pitch, torso_roll, neck_pitch, neck_relative_pitch,
    baseline_condition, baseline_score, state

Usage:
    python -m data.generate_dataset            # 2000 rows -> data/poseguide_dataset.csv
    python -m data.generate_dataset 5000 out.csv
"""

from __future__ import annotations

import csv
import os
import random
import sys

# Allow running both as a module and as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.features import extract_features, sample_reading  # noqa: E402
from ml.baseline import classify_baseline  # noqa: E402

DEFAULT_ROWS = 2000
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poseguide_dataset.csv")


def generate(rows: int, out_path: str, seed: int = 42) -> str:
    rng = random.Random(seed)
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "torso_pitch",
                "torso_roll",
                "neck_pitch",
                "neck_relative_pitch",
                "baseline_condition",
                "baseline_score",
                "state",
            ]
        )
        for _ in range(rows):
            r = sample_reading(rng)
            feats = extract_features(r["torso_pitch"], r["torso_roll"], r["neck_pitch"])
            result = classify_baseline(feats)
            writer.writerow(
                [
                    r["torso_pitch"],
                    r["torso_roll"],
                    r["neck_pitch"],
                    round(float(feats[2]), 2),
                    result["condition"],
                    result["score"],
                    r["state"],
                ]
            )
    return out_path


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ROWS
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    path = generate(n, out)
    print(f"Wrote {n} rows -> {path}")
