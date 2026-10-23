import csv
import io
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from analytics import snapshot
from app import create_app
from database import get_db
from planning import allocate, build_plan, suggest_distribution


class PlanningTests(unittest.TestCase):
    def test_distribution_invariants_including_old_negative_case(self):
        for count in (1, 2, 3, 20, 21, 60, 101):
            for weights in ([5] * count, [i % 10 + 1 for i in range(count)]):
                values = allocate(100, weights)
                self.assertEqual(sum(values), 100)
                self.assertTrue(all(0 <= x <= 100 for x in values))
                self.assertEqual(values, allocate(100, weights))

    def test_plan_budget_and_block_bounds(self):
        for count in (1, 2, 5, 20):
            subjects = [{"id": i + 1, "name": f"Subject {i}", "importance": i % 10 + 1} for i in range(count)]
            for minutes in (30, 31, 60, 61, 120, 599, 600):
                for mode, maximum in (("balanced", 25), ("exam", 40)):
                    plan = build_plan(subjects, minutes, mode)
                    blocks = plan["blocks"]
                    self.assertEqual(sum(b["minutes"] for b in blocks), minutes)
                    self.assertEqual(plan["study_minutes"] + plan["break_minutes"], minutes)
                    self.assertEqual(blocks[-1]["type"], "study")
                    self.assertTrue(all(0 < b["minutes"] <= maximum for b in blocks))
                    offset = 0
                    for b in blocks:
                        self.assertEqual(b["offset_minutes"], offset)
                        offset += b["minutes"]
                    studies = [b for b in blocks if b["type"] == "study"]
                    if count > 1:
                        self.assertTrue(all(a["subject_id"] != b["subject_id"] for a, b in zip(studies, studies[1:])))

    def test_empty_subjects_and_single_subject_termination(self):
        with self.assertRaises(ValueError):
            build_plan([], 60)
        self.assertEqual(suggest_distribution([]), [])
        plan = build_plan([{"id": 1, "name": "Hard subject", "importance": 10}], 600)
        self.assertLess(len(plan["blocks"]), 50)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "test.sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": self.path})
        self.client = self.app.test_client()
        self.headers = {"X-Kinetic-Request": "1"}

    def send(self, path, data, method="POST", headers=None):
        return self.client.open(path, method=method, json=data, headers=headers or self.headers)

    def subject(self, name="Mathematics", importance=7):
        response = self.send("/api/subjects", {"name": name, "importance": importance})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["id"]

    def session(self, sid, **updates):
        data = {
            "id": str(uuid4()),
            "subject_id": sid,
            "duration_seconds": 1500,
            "focus_rating": 4,
            "difficulty": "Hard",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        data.update(updates)
        return data

    def state(self):
        return self.client.get("/api/state").json

    def test_pages_empty_state_headers_and_old_links(self):
        for path in ("/", "/subjects", "/focus", "/data"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertNotIn(b"cdn.tailwindcss", response.data)
        for path in ("/Dash.html", "/Timer.html", "/index.html", "/planner"):
            self.assertEqual(self.client.get(path).status_code, 308)

    def test_private_files_are_not_public(self):
        for path in (
            "/app.py",
            "/database.py",
            "/study_planner.db",
            "/instance/kinetic.sqlite3",
            "/.env",
            "/.review-backup/original-project.zip",
            "/static/../app.py",
        ):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_cross_origin_and_host_protection(self):
        data = {"name": "Math", "importance": 5}
        self.assertEqual(self.client.post("/api/subjects", json=data).status_code, 403)
        for headers in (
            {**self.headers, "Origin": "https://other.example"},
            {**self.headers, "Sec-Fetch-Site": "cross-site"},
        ):
            self.assertEqual(self.send("/api/subjects", data, headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/", headers={"Host": "attacker.example"}).status_code, 400)

    def test_malformed_input_returns_json_errors(self):
        for path in ("/api/subjects", "/api/plan", "/api/sessions"):
            for data in ([], 1, "text", None):
                response = self.client.post(
                    path, data=json.dumps(data), content_type="application/json", headers=self.headers
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
        response = self.client.post("/api/subjects", data="{", content_type="application/json", headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/api/subjects", data="hello", headers=self.headers).status_code, 400)

    def test_request_size_limit(self):
        response = self.send("/api/subjects", {"name": "a" * 40000, "importance": 5})
        self.assertEqual(response.status_code, 413)

    def test_subject_validation_and_uniqueness(self):
        for name, importance in (("", 5), ("a" * 61, 5), ("Math", True), ("Math", "5"), ("Math", 11)):
            self.assertEqual(self.send("/api/subjects", {"name": name, "importance": importance}).status_code, 400)
        self.subject()
        self.assertEqual(self.send("/api/subjects", {"name": "mathematics", "importance": 2}).status_code, 400)

    def test_subject_limit(self):
        for i in range(20):
            self.subject(f"Subject {i}")
        self.assertEqual(self.send("/api/subjects", {"name": "Overflow", "importance": 5}).status_code, 400)

    def test_session_to_analytics_and_idempotent_retry(self):
        sid = self.subject()
        data = self.session(sid)
        self.assertEqual(self.send("/api/sessions", data).status_code, 201)
        self.assertEqual(self.send("/api/sessions", data).status_code, 200)
        state = self.state()
        self.assertEqual(state["stats"]["session_count"], 1)
        self.assertEqual(state["stats"]["total_seconds"], 1500)
        self.assertEqual(state["stats"]["week_seconds"], 1500)
        self.assertEqual(state["stats"]["average_focus"], 4)
        self.assertEqual(state["stats"]["points"], 20)
        self.assertEqual(state["stats"]["streak"], 1)
        self.assertEqual(state["active_subjects"][0]["actual_percent"], 100)
        data["duration_seconds"] = 1200
        self.assertEqual(self.send("/api/sessions", data).status_code, 409)

    def test_concurrent_retries_save_once(self):
        data = self.session(self.subject())

        def write(_):
            with self.app.test_client() as client:
                return client.post("/api/sessions", json=data, headers=self.headers).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(write, range(4)))
        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(200), 3)
        self.assertEqual(self.state()["stats"]["session_count"], 1)

    def test_invalid_sessions_never_write(self):
        sid = self.subject()
        for change in (
            {"duration_seconds": -1},
            {"duration_seconds": 0},
            {"duration_seconds": 14401},
            {"duration_seconds": "60"},
            {"duration_seconds": True},
            {"focus_rating": 6},
            {"focus_rating": None},
            {"subject_id": 999},
            {"difficulty": "Other"},
            {"id": "not-a-uuid"},
            {"completed_at": "2026-01-01"},
            {"completed_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
            {"completed_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()},
        ):
            self.assertEqual(self.send("/api/sessions", self.session(sid, **change)).status_code, 400, change)
        self.assertEqual(self.state()["stats"]["session_count"], 0)

    def test_archiving_keeps_history_and_prevents_new_sessions(self):
        sid = self.subject()
        self.send("/api/sessions", self.session(sid))
        self.assertEqual(self.send(f"/api/subjects/{sid}", {"archived": True}, "PATCH").status_code, 200)
        self.assertEqual(self.state()["stats"]["total_seconds"], 1500)
        self.assertEqual(self.state()["active_subjects"], [])
        self.assertEqual(self.send("/api/sessions", self.session(sid)).status_code, 400)
        self.send(f"/api/subjects/{sid}", {"archived": False}, "PATCH")
        self.assertEqual(len(self.state()["active_subjects"]), 1)

    def test_profile_edits_preserve_sessions(self):
        self.send("/api/sessions", self.session(self.subject()))
        data = {"name": "Alex", "weekly_goal_minutes": 300, "timezone": "Asia/Kolkata"}
        self.assertEqual(self.send("/api/profile", data, "PUT").status_code, 200)
        self.assertEqual(self.state()["stats"]["session_count"], 1)
        self.assertEqual(self.state()["profile"]["name"], "Alex")
        data["timezone"] = "Not/AZone"
        self.assertEqual(self.send("/api/profile", data, "PUT").status_code, 400)

    def test_distribution_validation_is_atomic(self):
        a, b = self.subject("A"), self.subject("B")
        before = [s["target_percent"] for s in self.state()["active_subjects"]]
        invalid = [
            [],
            [{"subject_id": a, "percent": 100}],
            [{"subject_id": a, "percent": 50}, {"subject_id": a, "percent": 50}],
            [{"subject_id": a, "percent": -1}, {"subject_id": b, "percent": 101}],
            [{"subject_id": a, "percent": 40}, {"subject_id": b, "percent": 40}],
        ]
        for values in invalid:
            self.assertEqual(self.send("/api/distribution", {"distribution": values}, "PUT").status_code, 400)
        self.assertEqual([s["target_percent"] for s in self.state()["active_subjects"]], before)
        values = [{"subject_id": a, "percent": 70}, {"subject_id": b, "percent": 30}]
        self.assertEqual(self.send("/api/distribution", {"distribution": values}, "PUT").status_code, 200)

    def test_plan_persistence_invalidation_and_bounds(self):
        self.assertEqual(self.send("/api/plan", {"total_minutes": 60}).status_code, 400)
        sid = self.subject()
        response = self.send("/api/plan", {"total_minutes": 60})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum(b["minutes"] for b in response.json["blocks"]), 60)
        self.assertIsNotNone(self.state()["plan"])
        for minutes in (0, 601, True, "60"):
            self.assertEqual(self.send("/api/plan", {"total_minutes": minutes}).status_code, 400)
        self.send(f"/api/subjects/{sid}", {"importance": 4}, "PATCH")
        self.assertIsNone(self.state()["plan"])

    def test_html_escaping_and_csv_formula_safety(self):
        dangerous = "<img src=x onerror=alert(1)>"
        self.subject(dangerous)
        html = self.client.get("/subjects").get_data(as_text=True)
        self.assertNotIn(dangerous, html)
        self.assertIn("&lt;img", html)
        sid = self.subject("=SUM(1,2)")
        self.send("/api/sessions", self.session(sid))
        response = self.client.get("/api/export")
        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(rows[1][0], "'=SUM(1,2)")
        self.assertIn("attachment", response.headers["Content-Disposition"])

    def test_timezone_week_and_expired_streak(self):
        sid = self.subject()
        with self.app.app_context():
            db = get_db()
            with db:
                db.execute("UPDATE profile SET timezone='Asia/Kolkata'")
                db.execute(
                    "INSERT INTO sessions VALUES (?, ?, 1500, 5, 'Easy', ?)",
                    (str(uuid4()), sid, "2026-10-18T19:00:00+00:00"),
                )
            state = snapshot(datetime(2026, 10, 19, 5, tzinfo=timezone.utc))
            self.assertEqual(state["weekly"][0]["seconds"], 1500)
            self.assertEqual(state["stats"]["streak"], 1)
            state = snapshot(datetime(2026, 10, 22, 5, tzinfo=timezone.utc))
            self.assertEqual(state["stats"]["streak"], 0)

    def test_database_survives_app_restart(self):
        self.subject()
        other = create_app({"TESTING": True, "DATABASE": self.path})
        self.assertEqual(len(other.test_client().get("/api/state").json["active_subjects"]), 1)

    def test_legacy_database_is_not_overwritten(self):
        path = Path(self.temp.name) / "legacy.db"
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE old_data (value TEXT)")
            db.execute("INSERT INTO old_data VALUES ('preserve me')")
            db.commit()
        with self.assertRaises(RuntimeError):
            create_app({"TESTING": True, "DATABASE": str(path)})
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT value FROM old_data").fetchone()[0], "preserve me")


if __name__ == "__main__":
    unittest.main()
