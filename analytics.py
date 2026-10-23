"""Every visible metric is derived from the same saved study sessions."""

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from database import get_db


def snapshot(now=None):
    db = get_db()
    profile = dict(db.execute("SELECT * FROM profile WHERE id=1").fetchone())
    zone = ZoneInfo(profile["timezone"])
    today = (now or datetime.now(timezone.utc)).astimezone(zone).date()
    start = today - timedelta(days=today.weekday())
    subjects = [
        dict(row)
        for row in db.execute("SELECT * FROM subjects ORDER BY archived, importance DESC, name COLLATE NOCASE")
    ]
    by_id = {s["id"]: s for s in subjects}
    for s in subjects:
        s.update(seconds=0, sessions=0, last_studied=None, week_seconds=0)
    weekly = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "label": (start + timedelta(days=i)).strftime("%a"),
            "seconds": 0,
        }
        for i in range(7)
    ]
    rows = db.execute(
        "SELECT sessions.*, subjects.name AS subject FROM sessions JOIN subjects ON subjects.id=subject_id ORDER BY completed_at DESC"
    ).fetchall()
    total_seconds = today_seconds = week_seconds = points = focus_sum = 0
    studied_dates = set()
    recent = []
    for row in rows:
        item = dict(row)
        stamp = datetime.fromisoformat(item["completed_at"]).astimezone(zone)
        day, seconds = stamp.date(), item["duration_seconds"]
        subject = by_id[item["subject_id"]]
        subject["seconds"] += seconds
        subject["sessions"] += 1
        subject["last_studied"] = max(subject["last_studied"] or "", day.isoformat())
        total_seconds += seconds
        focus_sum += item["focus_rating"]
        points += seconds // 120 + item["focus_rating"] * 2
        studied_dates.add(day)
        if day == today:
            today_seconds += seconds
        if start <= day < start + timedelta(days=7):
            weekly[(day - start).days]["seconds"] += seconds
            week_seconds += seconds
            subject["week_seconds"] += seconds
        if len(recent) < 30:
            item["display_date"] = stamp.strftime("%d %b, %H:%M")
            recent.append(item)
    streak = 0
    cursor = today if today in studied_dates else today - timedelta(days=1)
    while cursor in studied_dates:
        streak += 1
        cursor -= timedelta(days=1)
    active = [s for s in subjects if not s["archived"]]
    active_week = sum(s["week_seconds"] for s in active)
    for s in subjects:
        s["actual_percent"] = (
            round(s["week_seconds"] * 100 / active_week, 1) if active_week and not s["archived"] else 0
        )
    plan_row = db.execute("SELECT * FROM daily_plan WHERE id=1").fetchone()
    plan = json.loads(plan_row["payload"]) if plan_row and plan_row["study_date"] == today.isoformat() else None
    goal = profile["weekly_goal_minutes"] * 60
    return {
        "profile": profile,
        "today": today.isoformat(),
        "week_start": start.isoformat(),
        "subjects": subjects,
        "active_subjects": active,
        "recent_sessions": recent,
        "weekly": weekly,
        "plan": plan,
        "stats": {
            "total_seconds": total_seconds,
            "today_seconds": today_seconds,
            "week_seconds": week_seconds,
            "session_count": len(rows),
            "streak": streak,
            "points": points,
            "average_focus": round(focus_sum / len(rows), 1) if rows else None,
            "goal_percent": round(week_seconds * 100 / goal),
            "goal_remaining_minutes": max(0, (goal - week_seconds + 59) // 60),
        },
    }
