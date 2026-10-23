"""Kinetic Scholar: a local, single-user study workspace."""

import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, jsonify, redirect, render_template, request
from werkzeug.exceptions import HTTPException, SecurityError

from analytics import snapshot
from database import active_subjects, close_db, get_db, init_db
from planning import build_plan, suggest_distribution


class InvalidInput(ValueError):
    pass


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidInput(f"{label} must be a whole number from {minimum} to {maximum}.")
    return value


def text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise InvalidInput(f"{label} is required and must be at most {maximum} characters.")
    if any(ord(c) < 32 for c in value):
        raise InvalidInput(f"{label} cannot contain control characters.")
    return value.strip()


def body():
    if not request.is_json:
        raise InvalidInput("Send a JSON object with Content-Type: application/json.")
    data = request.get_json()
    if not isinstance(data, dict):
        raise InvalidInput("The request body must be a JSON object.")
    return data


def rebalance(db):
    subjects = active_subjects()
    db.execute("UPDATE subjects SET target_percent=0")
    db.executemany(
        "UPDATE subjects SET target_percent=? WHERE id=?",
        [(s["percent"], s["subject_id"]) for s in suggest_distribution(subjects)],
    )
    db.execute("DELETE FROM daily_plan")


def create_app(test_config=None):
    root = Path(__file__).resolve().parent
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_mapping(
        DATABASE=str(Path(os.getenv("KINETIC_DATABASE", str(root / "instance" / "kinetic.sqlite3"))).resolve()),
        MAX_CONTENT_LENGTH=32 * 1024,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
    )
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.before_request
    def protect_mutations():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if (
                request.headers.get("X-Kinetic-Request") != "1"
                or request.headers.get("Sec-Fetch-Site") == "cross-site"
                or request.headers.get("Origin", request.host_url.rstrip("/")) != request.host_url.rstrip("/")
            ):
                return jsonify(error="This action must come from your local workspace."), 403

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(InvalidInput)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        if isinstance(error, SecurityError):
            return "Untrusted host.", 400
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return render_template("error.html", code=error.code, message=error.description), error.code

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.error("Database operation failed: %s", type(error).__name__)
        return jsonify(error="Unable to save or read your workspace. Please retry; your saved data is preserved."), 503

    @app.template_filter("duration")
    def duration(seconds):
        minutes = int(seconds) // 60
        return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", page="dashboard", state=snapshot())

    @app.get("/subjects")
    def subjects_page():
        return render_template("subjects.html", page="subjects", state=snapshot())

    @app.get("/focus")
    def focus_page():
        return render_template("focus.html", page="focus", state=snapshot())

    @app.get("/data")
    def data_page():
        return render_template("data.html", page="data", state=snapshot())

    for old, new in {
        "/index.html": "/",
        "/Dash.html": "/",
        "/planner": "/",
        "/Subjects.html": "/subjects",
        "/Timer.html": "/focus",
        "/Data.html": "/data",
    }.items():
        app.add_url_rule(old, endpoint=old, view_func=lambda target=new: redirect(target, code=308))

    @app.get("/api/state")
    def state_api():
        return jsonify(snapshot())

    @app.put("/api/profile")
    def save_profile():
        data = body()
        name = text(data.get("name"), "Name", 60)
        goal = integer(data.get("weekly_goal_minutes"), "Weekly goal", 30, 6000)
        zone = text(data.get("timezone"), "Time zone", 64)
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise InvalidInput("Use an IANA time zone, such as Asia/Kolkata or Europe/London.") from None
        db = get_db()
        with db:
            db.execute("UPDATE profile SET name=?, weekly_goal_minutes=?, timezone=? WHERE id=1", (name, goal, zone))
        return jsonify(message="Profile saved. Your sessions are unchanged.")

    @app.post("/api/subjects")
    def add_subject():
        data = body()
        name = text(data.get("name"), "Subject", 60)
        importance = integer(data.get("importance"), "Importance", 1, 10)
        db = get_db()
        with db:
            db.execute("BEGIN IMMEDIATE")
            if len(active_subjects()) >= 20:
                raise InvalidInput("You can keep up to 20 active subjects. Archive one first.")
            if db.execute("SELECT 1 FROM subjects WHERE name=? COLLATE NOCASE", (name,)).fetchone():
                raise InvalidInput("That subject already exists. You can restore it if archived.")
            cursor = db.execute("INSERT INTO subjects (name, importance) VALUES (?, ?)", (name, importance))
            rebalance(db)
        return jsonify(id=cursor.lastrowid, message="Subject added. Targets rebalanced by importance."), 201

    @app.patch("/api/subjects/<int:subject_id>")
    def update_subject(subject_id):
        data = body()
        db = get_db()
        with db:
            db.execute("BEGIN IMMEDIATE")
            subject = db.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
            if subject is None:
                return jsonify(error="Subject not found."), 404
            name = text(data.get("name", subject["name"]), "Subject", 60)
            importance = integer(data.get("importance", subject["importance"]), "Importance", 1, 10)
            archived = data.get("archived", bool(subject["archived"]))
            if type(archived) is not bool:
                raise InvalidInput("Archived must be true or false.")
            if subject["archived"] and not archived and len(active_subjects()) >= 20:
                raise InvalidInput("Archive another subject before restoring this one.")
            if db.execute(
                "SELECT 1 FROM subjects WHERE name=? COLLATE NOCASE AND id!=?", (name, subject_id)
            ).fetchone():
                raise InvalidInput("Another subject already uses that name.")
            db.execute(
                "UPDATE subjects SET name=?, importance=?, archived=? WHERE id=?",
                (name, importance, int(archived), subject_id),
            )
            if importance != subject["importance"] or archived != bool(subject["archived"]):
                rebalance(db)
            else:
                db.execute("DELETE FROM daily_plan")
        return jsonify(message="Subject updated. Study history is preserved.")

    @app.put("/api/distribution")
    def save_distribution():
        data = body().get("distribution")
        if not isinstance(data, list) or not data or len(data) > 20:
            raise InvalidInput("Provide a distribution for your active subjects.")
        cleaned = {}
        for item in data:
            if not isinstance(item, dict):
                raise InvalidInput("Each allocation must be an object.")
            subject_id = integer(item.get("subject_id"), "Subject ID", 1, 2147483647)
            if subject_id in cleaned:
                raise InvalidInput("Each subject must appear exactly once.")
            cleaned[subject_id] = integer(item.get("percent"), "Percentage", 0, 100)
        if sum(cleaned.values()) != 100:
            raise InvalidInput("Target percentages must add up to exactly 100%.")
        db = get_db()
        with db:
            db.execute("BEGIN IMMEDIATE")
            if set(cleaned) != {s["id"] for s in active_subjects()}:
                raise InvalidInput("Include every active subject exactly once. Refresh if subjects changed.")
            db.executemany("UPDATE subjects SET target_percent=? WHERE id=?", [(v, k) for k, v in cleaned.items()])
        return jsonify(message="Target allocation saved.")

    @app.get("/api/distribution/suggestion")
    def distribution_suggestion():
        return jsonify(distribution=suggest_distribution(active_subjects()))

    @app.post("/api/plan")
    def generate_plan():
        data = body()
        minutes = integer(data.get("total_minutes"), "Time budget", 30, 600)
        mode = data.get("mode", "balanced")
        if mode not in ("balanced", "exam"):
            raise InvalidInput("Choose balanced or exam mode.")
        db = get_db()
        with db:
            db.execute("BEGIN IMMEDIATE")
            subjects = active_subjects()
            if not subjects:
                raise InvalidInput("Add an active subject before creating a plan.")
            plan = build_plan(subjects, minutes, mode)
            today = snapshot()["today"]
            db.execute("INSERT OR REPLACE INTO daily_plan VALUES (1, ?, ?)", (today, json.dumps(plan)))
        return jsonify(plan)

    @app.post("/api/sessions")
    def add_session():
        data = body()
        try:
            session_id = str(UUID(data.get("id", "")))
        except (ValueError, TypeError, AttributeError):
            raise InvalidInput("A valid session ID is required.") from None
        subject_id = integer(data.get("subject_id"), "Subject ID", 1, 2147483647)
        seconds = integer(data.get("duration_seconds"), "Duration in seconds", 60, 14400)
        focus = integer(data.get("focus_rating"), "Focus rating", 1, 5)
        difficulty = data.get("difficulty")
        if difficulty not in ("Easy", "Medium", "Hard"):
            raise InvalidInput("Difficulty must be Easy, Medium, or Hard.")
        raw_stamp = data.get("completed_at")
        try:
            stamp = datetime.fromisoformat(raw_stamp.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError()
            stamp = stamp.astimezone(timezone.utc)
        except (AttributeError, TypeError, ValueError, OverflowError):
            raise InvalidInput("Completion time must include a time zone.") from None
        values = (subject_id, seconds, focus, difficulty, stamp.isoformat())
        db = get_db()
        with db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT subject_id, duration_seconds, focus_rating, difficulty, completed_at FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
            if existing:
                if tuple(existing) != values:
                    return jsonify(error="This session ID was already used for different data."), 409
                return jsonify(message="Session already saved.", id=session_id), 200
            now = datetime.now(timezone.utc)
            if not now - timedelta(days=7) <= stamp <= now + timedelta(minutes=5):
                raise InvalidInput("Completion time must be within the last seven days and not in the future.")
            if not db.execute("SELECT 1 FROM subjects WHERE id=? AND archived=0", (subject_id,)).fetchone():
                raise InvalidInput("Choose an active subject. Restore an archived subject before saving its session.")
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)", (session_id, *values))
        return jsonify(message="Session saved.", id=session_id), 201

    @app.get("/api/export")
    def export_sessions():
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["subject", "duration_minutes", "focus_rating", "difficulty", "completed_at_utc"])
        rows = get_db().execute(
            "SELECT subjects.name, duration_seconds, focus_rating, difficulty, completed_at FROM sessions JOIN subjects ON subjects.id=subject_id ORDER BY completed_at DESC"
        )
        for row in rows:
            name = row[0]
            if name.lstrip().startswith(("=", "+", "-", "@")):
                name = "'" + name
            writer.writerow([name, round(row[1] / 60, 2), *row[2:]])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=kinetic-scholar-sessions.csv"},
        )

    return app


if __name__ == "__main__":
    from waitress import serve

    port = int(os.getenv("KINETIC_PORT", "5000"))
    print(f"Kinetic Scholar is ready at http://127.0.0.1:{port}", flush=True)
    serve(create_app(), host="127.0.0.1", port=port)
