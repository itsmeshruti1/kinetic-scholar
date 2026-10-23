"""Create a separate synthetic review workspace; never replace existing data."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app  # noqa: E402
from database import active_subjects, get_db  # noqa: E402
from planning import build_plan, suggest_distribution  # noqa: E402


def seed(path):
    path = Path(path).resolve()
    if path.exists():
        raise SystemExit(f"Refusing to replace existing data: {path}")
    app = create_app({"DATABASE": str(path)})
    with app.app_context():
        db = get_db()
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        with db:
            db.execute("UPDATE profile SET name='Alex', weekly_goal_minutes=600, timezone='Asia/Kolkata'")
            db.executemany(
                "INSERT INTO subjects (name, importance) VALUES (?, ?)",
                [("Algorithms", 9), ("Linear Algebra", 7), ("Systems Design", 8), ("Computer Networks", 5)],
            )
            subjects = active_subjects()
            db.executemany(
                "UPDATE subjects SET target_percent=? WHERE id=?",
                [(s["percent"], s["subject_id"]) for s in suggest_distribution(subjects)],
            )
            for index, (days_ago, minutes) in enumerate(
                [(6, 40), (5, 25), (4, 50), (3, 25), (2, 40), (2, 30), (1, 25), (1, 40), (0, 25), (0, 40)]
            ):
                stamp = now - timedelta(days=days_ago, minutes=15 + index * 2)
                db.execute(
                    "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid4()),
                        subjects[index % len(subjects)]["id"],
                        minutes * 60,
                        3 + index % 3,
                        ["Easy", "Medium", "Hard"][index % 3],
                        stamp.astimezone(timezone.utc).isoformat(),
                    ),
                )
            plan = build_plan(subjects, 120)
            db.execute("INSERT INTO daily_plan VALUES (1, ?, ?)", (now.date().isoformat(), json.dumps(plan)))
    print(f"Synthetic demo created: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "instance" / "demo.sqlite3")
    seed(parser.parse_args().database)
