"""Starts the browser the store scrapers drive."""
from contextlib import contextmanager

from playwright.sync_api import sync_playwright


def _launch(playwright, channel, headless):
    """Use the configured browser, or the first that is installed: Playwright's own, Edge, Chrome."""
    channels = [channel] if channel else [None, "msedge", "chrome"]
    error = None
    for name in channels:
        try:
            options = {"headless": headless, "args": ["--disable-blink-features=AutomationControlled"]}
            if name:
                options["channel"] = name
            return playwright.chromium.launch(**options), name
        except Exception as failure:
            error = failure
    raise RuntimeError(
        "No browser could be started. Run `playwright install chromium`, or set BROWSER_CHANNEL "
        f"to msedge or chrome in .env. ({str(error).splitlines()[0]})"
    )


@contextmanager
def open_page(channel="", headless=True):
    """A page in a fresh browser session that looks like an ordinary Indian desktop visitor."""
    with sync_playwright() as playwright:
        browser, name = _launch(playwright, channel, headless)
        try:
            major = browser.version.split(".")[0]
            # A headless browser announces itself in its user agent; stores turn those away.
            agent = (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                     f"Chrome/{major}.0.0.0 Safari/537.36" + (f" Edg/{major}.0.0.0" if name == "msedge" else ""))
            context = browser.new_context(
                locale="en-IN", timezone_id="Asia/Kolkata", user_agent=agent,
                viewport={"width": 1366, "height": 900},
            )
            yield context.new_page()
        finally:
            browser.close()
