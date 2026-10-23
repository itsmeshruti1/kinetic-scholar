# Architecture and product rules

## Boundaries

`create_app()` initializes the schema before serving, including WSGI startup. Database paths are absolute. An existing unrelated database is rejected rather than rewritten. The old Supabase/SQLite prototype is not imported automatically.

Only `static/` is publicly served. Jinja autoescapes template values; user content is not interpolated into `innerHTML`. Assets are local. Content Security Policy restricts resources to this origin and forbids inline scripts, framing, and external connections.

SQLite connections are per-request, enable foreign keys, use a ten-second busy timeout, and close at teardown. Mutations are transactional. Session UUIDs make retries idempotent: an identical retry succeeds; conflicting data under the same UUID returns 409. Subject and distribution changes use `BEGIN IMMEDIATE` to serialize their read/check/write steps.

Loopback binding, trusted hosts, JSON input, an application-specific request header, and origin checks reduce accidental network exposure and cross-site browser writes. They do not replace authentication for a shared server. No CORS policy opens the API to other origins.

## Data model

- `profile`: one row for name, weekly goal, and IANA time zone.
- `subjects`: stable IDs, case-insensitive unique names, importance, targets, and archived flag.
- `sessions`: saved records referencing subject IDs, duration in seconds, focus rating, difficulty, UTC completion time.
- `daily_plan`: one plan, shown only on its local study date. Subject changes invalidate it.

Renaming a subject also changes its display name in history because sessions reference a stable ID. Archive/restore never deletes history. Changing active subjects or importance resets targets by priority; the UI explains this. Manual target percentages do not change planning rules.

## Planning

Balanced blocks are at most 25 minutes; exam blocks are at most 40. A finite block count reserves five-minute breaks between blocks and divides the remaining study minutes exactly. The full sequence equals the requested budget.

Weighted credits guide subject selection, avoiding adjacent repeats when alternatives exist. Exam mode squares importance weights. With two subjects, the no-repeat rule forces alternation; importance primarily determines the first subject. A plan is a suggested sequence, not a calendar reservation or completion checklist. Breaks are guidance and do not start a timer automatically.

Percentage suggestions use the largest-remainder method: floor weighted shares, then distribute remaining integer points by fractional remainder. Values stay nonnegative and total exactly 100. A low-priority subject may receive 0%, a valid editable allocation.

## Metrics

Saved study sessions count; breaks do not. Archived subjects remain in totals.

- **Today/week:** UTC completion timestamps converted to the profile time zone. Weeks start Monday; sessions crossing midnight belong to their completion day.
- **Weekly goal:** this week's seconds divided by the goal. Percentages may exceed 100; the visual bar is capped.
- **Average focus:** arithmetic mean of saved 1–5 ratings. No inferred productivity claim.
- **Streak:** consecutive study days ending today or yesterday. It becomes zero after a full missed day.
- **Points:** per session, `floor(duration_seconds / 120) + focus_rating * 2`. A motivational rule, not a learning measure.
- **Actual allocation:** this week's subject time divided by this week's time across active subjects. Rounded display values may not total exactly 100.

Changing time zones re-buckets history. IANA rules and packaged timezone data handle daylight-saving changes. Exports retain UTC timestamps.

## Timer

`idle → running ↔ paused → complete → saved`.

Running timers store deadlines, not interval tick counts. Pausing stores remaining time. Early finishes save elapsed seconds only. Local storage preserves drafts across navigation; Web Locks allow one controlling Focus tab per origin.

Completion needs feedback and an explicit save. The submitted payload/UUID is retained for retry. Storage failures are displayed; an in-memory timer still works while its page stays open. A timer belonging to an archived subject remains preserved until that subject is restored. Manual submissions retain an uncertain save in session storage across reloads in the same tab; inputs stay fixed until the response is confirmed, so retries cannot create a second record.
