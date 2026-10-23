# Running and protecting your workspace

## Supported use

Run `python app.py` locally. Waitress binds to `127.0.0.1`, debugging is off, and only local hostnames are trusted. Keep the terminal open while using the app.

This is **not a multi-user public website**. Do not forward its port, bind to `0.0.0.0`, or put it behind a public proxy. Hosted use would require authentication, data ownership checks, abuse controls, deployment-specific trusted hosts, and private durable storage.

GitHub can host the source. GitHub Pages cannot run Flask. The old whole-folder publishing workflow is removed; the included workflow only checks the code.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `KINETIC_PORT` | `5000` | Local HTTP port |
| `KINETIC_DATABASE` | `instance/kinetic.sqlite3` beside the app | Alternate private workspace; use an absolute path |

`.env.example` documents these settings. The app reads operating-system variables and does not automatically parse `.env`. No credentials are required.

```powershell
$env:KINETIC_PORT = '5001'
.\.venv\Scripts\python.exe app.py
```

Visit `http://127.0.0.1:5001`. Browser drafts belong to each origin/port; saved sessions use the selected database.

## Backup and recovery

Stop the server, then copy the database to a private location. Never commit it, publish it, or replace a live database during requests. Restore by pointing `KINETIC_DATABASE` at a copy of your backup while the server is stopped.

Cleanup preserved the original project in `.review-backup/` in the delivered workspace. It is ignored and excluded from the release ZIP, contains original configuration, and must not be published. The cleaned project starts a new database. No remote data was accessed or altered.

## Troubleshooting

- **Port in use:** stop the other process or select another local port.
- **Unknown time zone:** use an IANA identifier such as `Asia/Kolkata`; install locked timezone data, especially on Windows.
- **Unsupported database:** preserve the old file and choose a fresh path. Unrelated schemas are never silently overwritten.
- **Focus tab already open:** close the other Focus tab and reload to resume the same draft.
- **Save failed:** keep the draft, restart the local server, and retry. The UUID prevents duplicate records. Drafts over seven days old need to be discarded and logged manually.
- **Wrong day/week:** check your profile time zone; metrics use completion dates.
- **Storage blocked:** keep the timer page open until saving, or enable local storage for this origin.

## Dependencies

`requirements.txt` lists direct runtime dependencies; `requirements.lock` records their tested complete resolution. Update deliberately in isolation, run regression/browser checks and `pip-audit`, and update both files. Development tools are in `requirements-dev.txt`.
