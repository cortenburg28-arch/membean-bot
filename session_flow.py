"""Navigate from dashboard to an active training session."""

from __future__ import annotations

import logging
import re
import time

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

import config
from actions import (
    click_continue,
    click_proceed,
    click_start_training,
    click_through_interstitial,
    dismiss_promo_banners,
    duration_buttons_visible,
    proceed_button_visible,
    select_session_duration,
    wait_for_proceed_button,
)
from page_detector import detect_page_type, get_body_text, is_continue_page, is_done_page_from

logger = logging.getLogger(__name__)


def is_dashboard(page: Page) -> bool:
    text = get_body_text(page).lower()
    url = page.url.lower()
    if "start training" not in text:
        return False
    dashboard_markers = (
        "welcome",
        "to-do list",
        "your training",
        "your classes",
        "my words",
    )
    return any(m in text for m in dashboard_markers) or "dashboard" in url


def is_duration_page(page: Page) -> bool:
    text = get_body_text(page).lower()
    if "you decide" in text or "choose a session duration" in text:
        return True
    if "session will last" in text and re.search(r"\d+\s*min", text):
        return True
    return duration_buttons_visible(page)


def is_training_page(page: Page) -> bool:
    page_type = detect_page_type(page)
    if page_type in ("learn", "mcq", "spell", "survey", "continue"):
        return True
    url = page.url.lower()
    return "training_sessions" in url and page_type not in ("done", "unknown")


def wait_for_duration_page(page: Page, timeout_s: float = 20.0) -> bool:
    """Wait until duration grid AND Proceed are both visible."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if is_duration_page(page) and duration_buttons_visible(page) and proceed_button_visible(page):
            page.wait_for_timeout(500)
            return True
        page.wait_for_timeout(400)
    return False


def wait_after_start_training(page: Page, timeout_s: float = 20.0) -> bool:
    """After Start Training: either duration picker OR training already running."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if is_training_page(page):
            print("  ↳ Session läuft schon — Dauer-Auswahl übersprungen")
            return True

        text = get_body_text(page)
        if is_continue_page(text):
            print("  ↳ Direkt weiter (keine Dauer-Auswahl)")
            return True

        if is_duration_page(page):
            remaining = max(1.0, deadline - time.time())
            return wait_for_duration_page(page, timeout_s=remaining)

        page.wait_for_timeout(400)

    if is_training_page(page):
        print("  ↳ Session aktiv — Dauer-Auswahl übersprungen")
        return True
    return is_duration_page(page)


def handle_duration_page(page: Page) -> bool:
    """Select duration and click Proceed — retry-safe, no crash if not ready."""
    if not wait_for_duration_page(page, timeout_s=8.0):
        print("  ↳ Dauer-Seite lädt noch…")
        return False

    minutes = config.SESSION_DURATION_MINUTES
    print(f"  ↳ Session-Dauer: {minutes} Minuten")

    try:
        select_session_duration(page, minutes)
    except RuntimeError as exc:
        logger.warning("Duration select failed: %s", exc)
        print(f"  ↳ {minutes} min noch nicht klickbar — warte…")
        return False

    if not wait_for_proceed_button(page, timeout_s=10.0):
        print("  ↳ Proceed-Button noch nicht da — warte…")
        return False

    page.wait_for_timeout(800)

    try:
        click_proceed(page)
    except RuntimeError as exc:
        logger.warning("Proceed click failed: %s", exc)
        print("  ↳ Proceed noch nicht bereit — warte…")
        return False

    page.wait_for_timeout(2500)
    return True


def advance_pre_training_step(page: Page) -> bool:
    """One step: dashboard, duration picker, or interstitial. Returns True if acted."""
    dismiss_promo_banners(page)

    if is_dashboard(page):
        print("  ↳ Dashboard → Start Training")
        try:
            click_start_training(page)
        except RuntimeError as exc:
            logger.warning("Start Training failed: %s", exc)
            return False
        wait_after_start_training(page, timeout_s=20.0)
        return True

    if is_training_page(page):
        return False

    if is_duration_page(page):
        return handle_duration_page(page)

    text = get_body_text(page)
    if is_continue_page(text):
        print("  ↳ Interstitial → Weiter")
        try:
            click_continue(page)
        except RuntimeError:
            return False
        page.wait_for_timeout(1500)
        return True

    if click_through_interstitial(page):
        print("  ↳ Interstitial → Button geklickt")
        page.wait_for_timeout(1500)
        return True

    return False


def bootstrap_training_session(page: Page, timeout_s: float = 120.0) -> bool:
    """Dashboard → Start Training → duration → Proceed → training."""
    print("Starte Training automatisch…")
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        if is_training_page(page):
            print(f"Training aktiv: {page.url}")
            return True

        if is_done_page_from(page, get_body_text(page)):
            print("Session bereits beendet.")
            return False

        try:
            if advance_pre_training_step(page):
                continue
        except PlaywrightTimeout as exc:
            logger.warning("Pre-training step timeout: %s", exc)
            page.wait_for_timeout(1000)
            continue

        page.wait_for_timeout(800)

    if is_training_page(page):
        return True

    logger.warning("Bootstrap timeout (url=%s)", page.url)
    return False


def try_recover_unknown_page(page: Page) -> bool:
    """Try dashboard/duration/interstitial handlers when page type is unknown."""
    try:
        return advance_pre_training_step(page)
    except (RuntimeError, PlaywrightTimeout) as exc:
        logger.warning("Recovery failed: %s", exc)
        return False
