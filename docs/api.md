# Local API

Write requests require `Content-Type: application/json` and `X-Kinetic-Request: 1`. Other browser origins are rejected. These safeguards are not user authentication. Responses are JSON except CSV export.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/state` | Profile, subjects, plan, metrics, weekly totals, latest 30 sessions |
| PUT | `/api/profile` | Save profile without clearing history |
| POST | `/api/subjects` | Create subject; rebalance targets |
| PATCH | `/api/subjects/<id>` | Rename, prioritize, archive/restore |
| GET | `/api/distribution/suggestion` | Suggest percentages without saving |
| PUT | `/api/distribution` | Save one allocation per active subject, totaling 100 |
| POST | `/api/plan` | Generate and save today's bounded plan |
| POST | `/api/sessions` | Save a completed session idempotently |
| GET | `/api/export` | Export all sessions as CSV |

Example bodies:

```json
{"name":"Alex","weekly_goal_minutes":600,"timezone":"Asia/Kolkata"}
```

```json
{"name":"Algorithms","importance":8}
```

```json
{"distribution":[{"subject_id":1,"percent":60},{"subject_id":2,"percent":40}]}
```

```json
{"total_minutes":120,"mode":"balanced"}
```

```json
{
  "id":"12345678-1234-1234-1234-123456789abc",
  "subject_id":1,
  "duration_seconds":1500,
  "focus_rating":4,
  "difficulty":"Medium",
  "completed_at":"2026-10-23T08:00:00+00:00"
}
```

Use a fresh UUID and the actual completion time for each new session. Exact retries return 200; first saves return 201; conflicting UUID reuse returns 409.

Limits: names 1–60 characters; 20 active subjects; importance 1–10; weekly goal 30–6,000 minutes; plan 30–600 minutes; session 60–14,400 seconds; focus 1–5; difficulty `Easy`, `Medium`, or `Hard`; completion within seven days, allowing five minutes of future clock skew. Numeric inputs must be JSON integers, not strings, floats, or booleans. Request bodies are capped at 32 KiB.

Validation errors return 400 with `{"error":"..."}`. Invalid origins return 403, missing records 404, oversized bodies 413, and database availability errors 503. Internal database details are not exposed.
