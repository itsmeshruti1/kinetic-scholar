# Contributing

Keep the product focused on a local, single-user study workflow. Discuss cloud accounts, frameworks, or major dependencies before introducing them.

1. Follow the README setup and use a separate demo/test database.
2. Keep private data, credentials, databases, virtual environments, and release ZIPs out of commits.
3. Add a small regression test for behavioral changes. Python tests use `unittest`; timer transitions use Node's built-in runner.
4. Run backend tests, timer tests, Ruff, and the release check. Run the browser check when changing the primary flow.
5. Describe the user-visible problem, final behavior, and checks performed in your pull request.

Use parameterized SQL, Jinja autoescaping or DOM text assignment, bounded validation, and existing transaction patterns. Preserve history when changing subjects. Do not remove origin or trusted-host protections to make an integration work.

For bug reports, include reproduction steps, Python/browser versions, expected behavior, and error messages. Remove personal data before attaching anything. For security reports, contact the repository owner privately through their GitHub profile; do not post credentials or user records publicly.
