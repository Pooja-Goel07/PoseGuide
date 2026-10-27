"""
PoseGuide - SQLite persistence layer (3-feature iteration)
==========================================================

Stores:
  * posture_log  - every classified reading (both classifiers, side by side)
  * calibration  - the fitted personalized model (single row), so calibration
                   survives a backend restart.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "poseguide.db")

_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init():
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posture_log (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp              TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            torso_pitch            REAL    NOT NULL DEFAULT 0,
            torso_roll             REAL    NOT NULL DEFAULT 0,
            neck_relative_pitch    REAL    NOT NULL DEFAULT 0,
            baseline_condition     TEXT    NOT NULL,
            baseline_score         INTEGER NOT NULL,
            personalized_condition TEXT    NOT NULL,
            personalized_model     TEXT    NOT NULL,
            mahalanobis            REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            model_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )
    conn.commit()


def insert_reading(
    torso_pitch: float,
    torso_roll: float,
    neck_relative_pitch: float,
    baseline_condition: str,
    baseline_score: int,
    personalized_condition: str,
    personalized_model: str,
    mahalanobis: Optional[float],
):
    conn = get_conn()
    conn.execute(
        """INSERT INTO posture_log
           (torso_pitch, torso_roll, neck_relative_pitch,
            baseline_condition, baseline_score,
            personalized_condition, personalized_model, mahalanobis)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            torso_pitch,
            torso_roll,
            neck_relative_pitch,
            baseline_condition,
            baseline_score,
            personalized_condition,
            personalized_model,
            mahalanobis,
        ),
    )
    conn.commit()


def get_history(limit: int = 100) -> list[dict]:
    """Most recent `limit` readings, oldest-first (for time-series charts)."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM (
               SELECT id, timestamp, torso_pitch, torso_roll, neck_relative_pitch,
                      baseline_condition, baseline_score,
                      personalized_condition, personalized_model, mahalanobis
               FROM posture_log ORDER BY id DESC LIMIT ?
           ) ORDER BY id ASC""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_hourly_averages(hours: int = 8) -> list[dict]:
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """SELECT strftime('%H:00', timestamp) AS hour,
                  CAST(AVG(baseline_score) AS INTEGER) AS score,
                  COUNT(*) AS samples
           FROM posture_log
           WHERE timestamp >= ?
           GROUP BY hour ORDER BY hour""",
        (cutoff,),
    ).fetchall()
    return [{"hour": r["hour"], "score": r["score"], "samples": r["samples"]} for r in rows]


def get_session_stats() -> dict:
    conn = get_conn()
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN baseline_condition = 'good' THEN 1 ELSE 0 END) AS good_count,
                  SUM(CASE WHEN personalized_condition = 'personalized_deviation'
                           THEN 1 ELSE 0 END) AS personal_dev_count,
                  CAST(AVG(baseline_score) AS INTEGER) AS avg_score,
                  MIN(timestamp) AS first_reading,
                  MAX(timestamp) AS last_reading
           FROM posture_log"""
    ).fetchone()

    total = row["total"] or 0
    good = row["good_count"] or 0
    return {
        "total": total,
        "good_count": good,
        "good_pct": round(good / total * 100) if total else 0,
        "personal_deviation_count": row["personal_dev_count"] or 0,
        "avg_score": row["avg_score"] or 0,
        "first_reading": row["first_reading"],
        "last_reading": row["last_reading"],
    }


def get_condition_distribution() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT baseline_condition AS condition, COUNT(*) AS cnt
           FROM posture_log GROUP BY baseline_condition ORDER BY cnt DESC"""
    ).fetchall()
    label = {
        "good": "Good",
        "slouching": "Slouching",
        "forward_head": "Forward Head",
        "lateral_lean": "Lateral Lean",
        "multiple_issues": "Multiple Issues",
        "critical": "Critical",
    }
    return [{"name": label.get(r["condition"], r["condition"]), "value": r["cnt"]} for r in rows]


# ── Calibration persistence ─────────────────────────────────────────────
def save_calibration(model_dict: dict):
    """Upsert the single fitted personalized model."""
    conn = get_conn()
    conn.execute(
        """INSERT INTO calibration (id, model_json, created_at)
           VALUES (1, ?, datetime('now','localtime'))
           ON CONFLICT(id) DO UPDATE SET
               model_json = excluded.model_json,
               created_at = excluded.created_at""",
        (json.dumps(model_dict),),
    )
    conn.commit()


def load_calibration() -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT model_json FROM calibration WHERE id = 1").fetchone()
    if row is None:
        return None
    return json.loads(row["model_json"])


def clear_calibration():
    conn = get_conn()
    conn.execute("DELETE FROM calibration WHERE id = 1")
    conn.commit()
