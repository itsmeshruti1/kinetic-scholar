"""Capture repository screenshots from an isolated synthetic workspace."""

import argparse
import logging
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app  # noqa: E402
from scripts.seed_demo import seed  # noqa: E402


def capture(channel=None):
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    output = ROOT / "docs" / "images"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        database = Path(temporary) / "screenshots.sqlite3"
        seed(database)
        app = create_app({"DATABASE": str(database)})
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel=channel, headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                base = f"http://127.0.0.1:{server.server_port}"
                for name, path in (
                    ("dashboard", "/"),
                    ("subjects", "/subjects"),
                    ("insights", "/data"),
                    ("focus", "/focus"),
                ):
                    page.goto(base + path, wait_until="networkidle")
                    page.screenshot(path=output / f"{name}.png", full_page=True)
                page.get_by_role("button", name="Switch to dark theme").click()
                page.screenshot(path=output / "focus-dark.png", full_page=True)
                page.get_by_role("button", name="Switch to light theme").click()
                page.set_viewport_size({"width": 375, "height": 900})
                page.goto(base, wait_until="networkidle")
                page.screenshot(path=output / "dashboard-mobile.png", full_page=True)
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
    print(f"Synthetic-data screenshots saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default=None)
    capture(parser.parse_args().channel)
