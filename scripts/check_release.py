"""Validate an explicit public source inventory, without touching private data."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "app.py",
    "database.py",
    "planning.py",
    "analytics.py",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    ".gitignore",
    ".env.example",
    "requirements.txt",
    "requirements.lock",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
]
DIRECTORIES = ["templates", "static", "docs", "tests", "scripts", ".github"]
SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".html", ".css", ".svg", ".png", ".md", ".yml"}


def release_files(root=ROOT):
    files = [root / name for name in FILES]
    for directory in DIRECTORIES:
        files.extend(
            p
            for p in (root / directory).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}
        )
    return sorted(files)


def check(root=ROOT):
    files = release_files(root)
    private_key = re.compile(
        r"sb_(?:secret|publishable)_[A-Za-z0-9_-]{12,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    )
    for path in files:
        assert path.is_file(), f"Missing release file: {path}"
        assert not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), f"Linked file: {path}"
        assert path.relative_to(root).as_posix() in FILES or path.suffix in SOURCE_SUFFIXES, (
            f"Unexpected release file: {path}"
        )
        if path.suffix != ".png":
            content = path.read_text(encoding="utf-8")
            assert not private_key.search(content), f"Credential-like value found: {path}"
            if path.suffix == ".md":
                for target in re.findall(r"\]\(([^\s)]+)\)", content):
                    if not target.startswith(("https://", "http://", "#", "mailto:")):
                        linked = (path.parent / target.split("#")[0]).resolve()
                        assert linked in {item.resolve() for item in files}, f"Broken release link: {path}: {target}"
    for name in (
        "Dash.html",
        "Data.html",
        "Timer.html",
        "Subjects.html",
        "index.html",
        "script.js",
        "style.css",
        "study_planner.db",
        "IMPLEMENTATION_SUMMARY.md",
        ".github/workflows/static.yml",
    ):
        assert not (root / name).exists(), f"Legacy file still at release root: {name}"
    for page in (root / "templates").glob("*.html"):
        content = page.read_text(encoding="utf-8")
        assert not re.search(r"(?:src|href)=['\"]https?://", content), f"External asset in {page}"
    print(f"Release inventory OK: {len(files)} files; no databases, legacy entrypoints, or credential-like values.")
    return files


if __name__ == "__main__":
    check()
