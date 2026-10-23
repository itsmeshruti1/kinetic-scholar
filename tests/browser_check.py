"""End-to-end checks using an isolated database and a headless local browser."""

import argparse
import logging
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app  # noqa: E402


def check(channel=None):
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory() as temporary:
        app = create_app({"TESTING": True, "DATABASE": str(Path(temporary) / "browser.sqlite3")})
        server = make_server("127.0.0.1", 0, app, threaded=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel=channel, headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                page.get_by_role("button", name="Set up profile").click()
                page.get_by_label("Your name", exact=True).fill("Browser Review")
                page.get_by_label("Time zone", exact=True).fill("Asia/Kolkata")
                page.get_by_role("button", name="Save profile").click()
                expect(page.get_by_text("Welcome back, Browser Review.")).to_be_visible()
                page.get_by_role("link", name="Subjects", exact=False).first.click()
                for name, importance in (("Algorithms", "9"), ("Linear Algebra", "7")):
                    page.get_by_role("button", name="Add subject +", exact=True).click()
                    page.get_by_label("Subject name").fill(name)
                    page.get_by_label("Importance (1–10)").fill(importance)
                    page.get_by_role("button", name="Save subject").click()
                    expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
                page.get_by_role("searchbox").fill("algebra")
                expect(page.get_by_role("heading", name="Algorithms", exact=True)).not_to_be_visible()
                page.get_by_role("searchbox").fill("")
                page.goto(base)
                page.get_by_label("Time available (min)").fill("60")
                page.get_by_role("button", name="Build my plan").click()
                expect(page.locator(".plan-summary")).to_contain_text("60 min total")
                page.goto(base + "/focus")
                expect(page.locator("#timer-toggle")).to_be_enabled()
                page.clock.install()
                page.get_by_label("Session length (min)").fill("1")
                page.locator("#timer-toggle").click()
                expect(page.locator("#timer-status")).to_have_text("ONE THING AT A TIME")
                page.clock.run_for(20000)
                page.locator("#timer-toggle").click()
                expect(page.locator("#timer-status")).to_have_text("TAKE A BREATH")
                page.clock.run_for(10000)
                expect(page.locator("#timer-display")).to_have_text("00:40")
                page.reload()
                expect(page.locator("#timer-status")).to_have_text("TAKE A BREATH")
                expect(page.locator("#timer-display")).to_have_text("00:40")
                second = context.new_page()
                second.goto(base + "/focus")
                expect(second.locator("#timer-error")).to_contain_text("Focus tab is already open")
                second.close()
                page.locator("#timer-toggle").click()
                page.clock.run_for(40000)
                expect(page.get_by_role("heading", name="Give yourself credit.")).to_be_visible()

                def lose_saved_response(route):
                    response = route.fetch()
                    assert response.status == 201
                    route.abort("failed")

                page.route("**/api/sessions", lose_saved_response, times=1)
                page.locator("#completion-form button[type=submit]").click()
                expect(page.locator("#completion-form .form-error")).to_contain_text("Cannot reach")
                page.reload()
                expect(page.get_by_role("heading", name="Give yourself credit.")).to_be_visible()
                expect(page.locator("#completion-form select").first).to_be_disabled()
                page.locator("#completion-form button[type=submit]").click()
                expect(page).to_have_url(base + "/data")
                expect(page.locator(".session-panel tbody tr")).to_have_count(1)
                page.get_by_role("button", name="Log a session +").click()
                page.get_by_label("Minutes studied").fill("25")
                page.route("**/api/sessions", lose_saved_response, times=1)
                page.locator("#manual-form button[type=submit]").click()
                expect(page.locator("#manual-form .form-error")).to_contain_text("Cannot reach")
                page.reload()
                page.get_by_role("button", name="Log a session +").click()
                expect(page.get_by_label("Minutes studied")).to_have_value("25")
                expect(page.get_by_label("Minutes studied")).to_be_disabled()
                page.locator("#manual-form button[type=submit]").click()
                # The row already exists after a lost response; wait for the retry's reload.
                expect(page.locator("#manual-dialog")).not_to_be_visible()
                expect(page.locator("#toast")).to_have_text("Session saved. Your progress is up to date.")
                expect(page.locator(".session-panel tbody tr")).to_have_count(2)
                inputs = page.locator("#distribution-form input")
                inputs.nth(0).fill("60")
                inputs.nth(1).fill("40")
                expect(page.locator("#allocation-total")).to_have_text("Total: 100%")
                page.get_by_role("button", name="Save targets", exact=True).click()
                expect(page.locator("#toast")).to_have_text("Target allocation saved.")
                page.reload()
                expect(inputs.nth(0)).to_have_value("60")
                expect(inputs.nth(1)).to_have_value("40")
                expect(page.locator("#allocation-total")).to_have_text("Total: 100%")
                with page.expect_download() as download:
                    page.get_by_role("link", name="Export CSV").click()
                assert download.value.suggested_filename == "kinetic-scholar-sessions.csv"
                page.goto(base + "/subjects")
                page.locator("[data-edit-subject]").first.click()
                page.get_by_label("Archive this subject", exact=False).check()
                page.get_by_role("button", name="Save subject").click()
                expect(page.locator(".subject-card.archived")).to_have_count(1)
                page.locator(".subject-card.archived button").click()
                page.get_by_label("Archive this subject", exact=False).uncheck()
                page.get_by_role("button", name="Save subject").click()
                expect(page.locator(".subject-card.archived")).to_have_count(0)
                for width in (375, 768, 1440):
                    page.set_viewport_size({"width": width, "height": 900})
                    for path in ("/", "/subjects", "/focus", "/data"):
                        page.goto(base + path)
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, path)
                page.get_by_role("button", name="Switch to dark theme").click()
                page.reload()
                expect(page.locator("html")).to_have_attribute("data-theme", "dark")
                assert not errors, errors
                browser.close()
            print(
                "Browser flow passed: profile, subjects/search/archive, bounded plan, timer pause/reload/completion, tab lock, lost-response recovery for timer/manual logging, targets, export, theme, 3 viewport widths."
            )
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default=None, help="Use msedge or chrome, or omit for Playwright Chromium")
    check(parser.parse_args().channel)
