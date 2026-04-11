"""
PoseGuide – SQLite Database Layer
Stores posture readings for analytics (hourly scores, session stats, condition distribution).
"""

import sqlite3
import os
import time
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "poseguide.db")

_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")  # better concurrent reads
    return _conn


def init():
    """Create the posture_log table if it doesn't exist."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posture_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            score       INTEGER NOT NULL,
            condition   TEXT    NOT NULL,
            torso_pitch REAL    NOT NULL DEFAULT 0,
            torso_roll  REAL    NOT NULL DEFAULT 0,
            neck_pitch  REAL    NOT NULL DEFAULT 0,
            neck_roll   REAL    NOT NULL DEFAULT 0,
            flex_value  REAL    NOT NULL DEFAULT 0
        )
    """)
    conn.commit()


def insert_reading(
    score: int,
    condition: str,
    torso_pitch: float,
    torso_roll: float,
    neck_pitch: float,
    neck_roll: float,
    flex_value: float,
):
    """Insert a single posture reading into the database."""
    conn = get_conn()
    conn.execute(
        """INSERT INTO posture_log
           (score, condition, torso_pitch, torso_roll, neck_pitch, neck_roll, flex_value)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (score, condition, torso_pitch, torso_roll, neck_pitch, neck_roll, flex_value),
    )
    conn.commit()


def get_hourly_averages(hours: int = 8) -> list[dict]:
    """
    Average posture score per hour for the last N hours.
    Returns: [{"hour": "14:00", "score": 78}, ...]
    """
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """SELECT strftime('%H:00', timestamp) AS hour,
                  CAST(AVG(score) AS INTEGER) AS score,
                  COUNT(*) AS samples
           FROM posture_log
           WHERE timestamp >= ?
           GROUP BY hour
           ORDER BY hour""",
        (cutoff,),
    ).fetchall()
    return [{"hour": r["hour"], "score": r["score"], "samples": r["samples"]} for r in rows]


def get_session_stats() -> dict:
    """
    Overall session statistics from all stored data.
    Returns: {total, good_count, good_pct, avg_score, first_reading, last_reading}
    """
    conn = get_conn()
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN condition = 'good' THEN 1 ELSE 0 END) AS good_count,
                  CAST(AVG(score) AS INTEGER) AS avg_score,
                  MIN(timestamp) AS first_reading,
                  MAX(timestamp) AS last_reading
           FROM posture_log"""
    ).fetchone()

    total = row["total"] or 0
    good = row["good_count"] or 0
    return {
        "total": total,
        "good_count": good,
        "good_pct": round(good / total * 100) if total > 0 else 0,
        "avg_score": row["avg_score"] or 0,
        "first_reading": row["first_reading"],
        "last_reading": row["last_reading"],
    }


def get_condition_distribution() -> list[dict]:
    """
    Count of each posture condition.
    Returns: [{"name": "Good", "value": 120}, {"name": "Slouching", "value": 30}, ...]
    """
    conn = get_conn()
    rows = conn.execute(
        """SELECT condition, COUNT(*) AS cnt
           FROM posture_log
           GROUP BY condition
           ORDER BY cnt DESC"""
    ).fetchall()

    label_map = {
        "good": "Good",
        "slouching": "Slouching",
        "forward_head": "Forward Head",
        "lateral_lean": "Lateral Lean",
        "multiple_issues": "Multiple Issues",
    }
    return [{"name": label_map.get(r["condition"], r["condition"]), "value": r["cnt"]} for r in rows]
