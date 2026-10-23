# Review this project before publishing

The completed scope is a local, single-user study app with SQLite and the MIT license. Publishing the source on GitHub does not deploy a publicly hosted application.

## What changed

- Replaced split Supabase/SQLite state with one local SQLite database. No cloud credentials remain in the release.
- Replaced the redirected legacy UI with four connected, server-rendered pages and shared styles.
- Connected timer completion and manual entries to persistent session history, dashboard statistics, subject totals, and analytics.
- Repaired planner termination and exact-budget allocation; replaced AI claims with transparent rule descriptions.
- Added subject search/edit/archive/restore, profile editing, real target allocations, CSV export, responsive layouts, and keyboard-accessible dialogs.
- Restricted static serving, disabled debugging, bound to loopback, added trusted-host/origin protections, safe rendering, bounded validation, and transaction/idempotency checks.
- Added regression tests, CI, safe synthetic demo data, pinned runtime dependencies, documentation, license, and release packaging.

The original files and database are preserved in `.review-backup/` in the working folder. That directory is private and excluded from the release. The old reference artwork and incomplete experiments are preserved there rather than presented as functioning product features.

## Five-minute review

1. Follow the README quick start. Confirm a fresh workspace contains no seeded personal activity.
2. Edit the profile; check your name, weekly goal, and time zone.
3. Add two subjects with different priorities. Search, edit, archive, and restore one.
4. On the dashboard, generate a 60-minute plan. Confirm the displayed study and break minutes total 60.
5. On Focus, choose a one-minute session. Start, pause, reload, resume, then save feedback when it finishes.
6. On Insights, confirm the session appears and study totals increase. Change target percentages to total 100 and save.
7. Log an offline session and download CSV. Check both records in the export.
8. Review mobile and dark mode, and navigate dialogs with Tab/Escape.

To see the populated presentation without entering data, use the separate synthetic demo described in the README.

## Verification performed

Checked locally on Windows on 23 October 2026, using Python 3.15, Node 24, and headless Microsoft Edge:

| Check | Result |
| --- | --- |
| Backend regression suite | 21 tests passed: API validation, persistence, concurrency, security boundaries, analytics, and planning |
| Pure JavaScript timer suite | 6 tests passed |
| Browser walkthrough | Passed profile, subjects/search/archive/restore, planning, timer pause/reload/save, tab ownership, manual logging, targets, CSV, and theme persistence |
| Interrupted save recovery | Timer and manual submissions survived a lost server response and page reload; retry produced no duplicate sessions |
| Responsive layout | No horizontal overflow on all four pages at 375, 768, and 1440 pixels |
| Visual review | Six screenshots inspected, including mobile and dark mode |
| Code and dependency consistency | Ruff lint/format and `pip check` passed |
| Runtime dependency audit | `pip-audit` found no known vulnerabilities in the pinned runtime dependencies at check time |
| Public source inventory | Passed file-type, credential-pattern, legacy-file, and local documentation-link checks |

GitHub Actions has been configured but cannot run until you upload the source. Other browsers, operating systems, screen readers, and large datasets were not exercised locally. These checks support the documented local use; they are not a guarantee of universal compatibility or a formal security audit.

## Screenshots

All screenshots were captured from the application with synthetic data:

- [Dashboard](images/dashboard.png)
- [Subjects](images/subjects.png)
- [Focus](images/focus.png)
- [Insights](images/insights.png)
- [Dark focus mode](images/focus-dark.png)
- [Mobile dashboard](images/dashboard-mobile.png)

Regenerate using `python scripts/capture_screenshots.py --channel msedge`, or omit the channel after installing Playwright Chromium. The capture command creates a temporary database and does not use your personal workspace.

## Release package

Run `python scripts/package_release.py` to create `release/kinetic-scholar.zip` and `release/SHA256SUMS.txt`. Packaging uses an explicit source inventory, not the whole working directory. It excludes databases, the original backup, virtual environments, QA files, caches, and previous releases.

Extract the ZIP into a new folder for the cleanest GitHub review. Set up a virtual environment there and follow the README. No Git history is included because the supplied folder had no `.git` directory. Existing remote repository history, past secret exposure, and GitHub settings were not available to inspect.

## Suggested GitHub presentation

- Name: `kinetic-scholar`
- Description: “A local study workspace with time-budgeted plans, a recoverable focus timer, and session analytics. Built with Flask, SQLite, and JavaScript.”
- Topics: `python`, `flask`, `sqlite`, `javascript`, `study-planner`, `pomodoro`, `productivity`
- About link: add your own walkthrough video or portfolio page; do not invent a hosted application URL.

Resume wording you can adapt:

- Built a local study-planning application with Flask, SQLite, and vanilla JavaScript, connecting prioritized subjects, focus sessions, and persistent analytics.
- Implemented bounded scheduling and exact integer allocations, plus a deadline-based timer with reload recovery and idempotent session saves.
- Added automated API, persistence, scheduling, timer, and browser-flow checks; documented security boundaries and reproducible setup.

Do not describe this as a multi-user service, an AI model, or a deployed production app. Those are outside the agreed scope.
