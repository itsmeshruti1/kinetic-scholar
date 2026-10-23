"""SQLite storage for one local workspace, outside the public asset directory."""

import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT NOT NULL DEFAULT '',
    weekly_goal_minutes INTEGER NOT NULL DEFAULT 600, timezone TEXT NOT NULL DEFAULT 'UTC'
);
INSERT OR IGNORE INTO profile (id) VALUES (1);
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    importance INTEGER NOT NULL CHECK (importance BETWEEN 1 AND 10),
    target_percent INTEGER NOT NULL DEFAULT 0 CHECK (target_percent BETWEEN 0 AND 100),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, subject_id INTEGER NOT NULL REFERENCES subjects(id),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds BETWEEN 60 AND 14400),
    focus_rating INTEGER NOT NULL CHECK (focus_rating BETWEEN 1 AND 5),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('Easy', 'Medium', 'Hard')),
    completed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_completed_at ON sessions(completed_at);
CREATE INDEX IF NOT EXISTS sessions_subject_id ON sessions(subject_id);
CREATE TABLE IF NOT EXISTS daily_plan (
    id INTEGER PRIMARY KEY CHECK (id = 1), study_date TEXT NOT NULL, payload TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if (tables and version != 1) or version > 1:
        raise RuntimeError("Unsupported database. Choose a new KINETIC_DATABASE path; keep the original backup.")
    db.executescript(SCHEMA)
    db.commit()


def active_subjects():
    return [
        dict(row)
        for row in get_db().execute(
            "SELECT * FROM subjects WHERE archived=0 ORDER BY importance DESC, name COLLATE NOCASE"
        )
    ]
