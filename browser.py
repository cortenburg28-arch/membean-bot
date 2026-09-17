"""Playwright browser helpers for Membean login and session reuse."""

from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

import config

logger = logging.getLogger(__name__)

SESSION_META_PATH = config.ROOT_DIR / "session_meta.json"
AUTH_COOKIE_NAMES = {"auth_token", "_new_membean_session_id"}


def ensure_dirs() -> None:
    config.LOGS_DIR.mkdir(exist_ok=True)
    config.SCREENSHOTS_DIR.mkdir(exist_ok=True)


def has_saved_session() -> bool:
    return config.STORAGE_STATE_PATH.exists()


def load_session_meta() -> dict:
    if not SESSION_META_PATH.exists():
        return {}
    try:
        return json.loads(SESSION_META_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_session_meta(meta: dict) -> None:
    SESSION_META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Saved session meta to %s", SESSION_META_PATH)


def get_verify_url() -> str:
    if config.MEMBEAN_TRAINING_URL:
        return config.MEMBEAN_TRAINING_URL
    meta = load_session_meta()
    if meta.get("last_url"):
        return meta["last_url"]
    return config.MEMBEAN_HOME_URL


def has_membean_auth_cookies(context: BrowserContext) -> bool:
    cookies = context.cookies("https://membean.com")
    names = {cookie["name"] for cookie in cookies}
    return bool(names & AUTH_COOKIE_NAMES)


@contextmanager
def launch_browser() -> Iterator[tuple[Playwright, Browser, BrowserContext]]:
    ensure_dirs()
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=config.HEADLESS,
        slow_mo=config.BROWSER_SLOW_MO,
    )
    if sys.platform == "win32":
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    else:
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    context_kwargs: dict = {
        # Näher an normalem Chrome — manche Logins funktionieren sonst nicht sauber.
        "user_agent": user_agent,
    }
    if has_saved_session():
        context_kwargs["storage_state"] = str(config.STORAGE_STATE_PATH)
        logger.info("Loaded saved session from %s", config.STORAGE_STATE_PATH)

    context = browser.new_context(**context_kwargs)
    try:
        yield playwright, browser, context
    finally:
        context.close()
        browser.close()
        playwright.stop()


def save_session(context: BrowserContext, page: Page) -> None:
    context.storage_state(path=str(config.STORAGE_STATE_PATH))
    save_session_meta(
        {
            "last_url": page.url,
            "saved_at": page.evaluate("() => new Date().toISOString()"),
        }
    )
    logger.info("Saved session to %s (url=%s)", config.STORAGE_STATE_PATH, page.url)


def wait_for_manual_login(page: Page) -> None:
    """Keep browser open until the user confirms login in the terminal."""
    page.goto(config.MEMBEAN_HOME_URL, wait_until="domcontentloaded")
    print()
    print("=" * 60)
    print("  Membean Login")
    print("=" * 60)
    print("1. Log in manually in the browser window.")
    print("2. Stay on the dashboard (Welcome screen is fine).")
    print("3. Come back here and press Enter to save the session.")
    print("=" * 60)
    input("\nPress Enter when you are on the training page... ")


def is_logged_in(page: Page, context: BrowserContext) -> bool:
    """Check login using auth cookies and page URL — not homepage button text."""
    if not has_membean_auth_cookies(context):
        logger.warning("No Membean auth cookies found")
        return False

    url = page.url.lower()
    if any(token in url for token in ("login", "sign_in", "signin", "sessions/new")):
        logger.warning("On login page despite cookies (url=%s)", page.url)
        return False

    logged_in_urls = ("training_sessions", "dashboard", "user_state", "calibrations")
    if any(token in url for token in logged_in_urls):
        return True

    # Positive UI signals on Membean when logged in
    for selector in (
        "text=I'm done",
        "text=Next",
        "text=Log out",
        "text=Logout",
    ):
        if page.locator(selector).count() > 0:
            return True

    # Auth cookies exist and we are on membean — treat as logged in
    if "membean.com" in url:
        return True

    return False


def verify_session(page: Page, context: BrowserContext) -> bool:
    target = get_verify_url()
    logger.info("Verifying session at %s", target)

    page.goto(target, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    if not is_logged_in(page, context):
        logger.warning("Session looks logged out (url=%s)", page.url)
        save_debug_screenshot(page, "verify_failed")
        return False

    logger.info("Session OK — current URL: %s", page.url)
    return True


def save_debug_screenshot(page: Page, name: str) -> Path:
    ensure_dirs()
    path = config.SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    logger.info("Saved screenshot to %s", path)
    return path
