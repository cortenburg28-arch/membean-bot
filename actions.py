"""Human-like browser interactions for Membean."""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Dict, Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeout

import config

logger = logging.getLogger(__name__)

WARNING_KEYWORDS = (
    "please answer",
    "must answer",
    "select an answer",
    "answer the question",
    "before you continue",
    "before continuing",
    "try again",
    "hold on",
    "wait a moment",
    "oops",
)

DISMISS_BUTTON_PATTERNS = (
    r"^ok$",
    r"^got it$",
    r"^close$",
    r"^dismiss$",
    r"^continue$",
    r"^i understand$",
    r"^yes$",
    r"^alright$",
)


def human_pause(min_s: Optional[float] = None, max_s: Optional[float] = None) -> None:
    lo = config.DELAY_MIN if min_s is None else min_s
    hi = config.DELAY_MAX if max_s is None else max_s
    if hi < lo:
        hi = lo
    time.sleep(random.uniform(lo, hi))


def thinking_pause() -> None:
    """Pause as if reading the question before answering."""
    human_pause(config.THINK_PAUSE_MIN, config.THINK_PAUSE_MAX)


def reading_pause() -> None:
    human_pause(config.READ_PAUSE_MIN, config.READ_PAUSE_MAX)


def page_transition_pause() -> None:
    human_pause(config.PAGE_TRANSITION_MIN, config.PAGE_TRANSITION_MAX)


def _jitter(value: float, amount: float = 6.0) -> float:
    return value + random.uniform(-amount, amount)


def human_mouse_move(page: Page, target_x: float, target_y: float) -> None:
    """Move mouse along a slightly curved path — not a perfect line."""
    viewport = page.viewport_size or {"width": 1280, "height": 720}
    start_x = random.uniform(viewport["width"] * 0.15, viewport["width"] * 0.85)
    start_y = random.uniform(viewport["height"] * 0.15, viewport["height"] * 0.85)

    control_x = (start_x + target_x) / 2 + random.uniform(-55, 55)
    control_y = (start_y + target_y) / 2 + random.uniform(-40, 40)

    steps = random.randint(10, 22)
    for step in range(steps + 1):
        t = step / steps
        # Quadratic bezier with random control point → leicht gebogene Spur
        x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * control_x + t**2 * target_x
        y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * control_y + t**2 * target_y
        page.mouse.move(_jitter(x, 2.5), _jitter(y, 2.5))
        time.sleep(random.uniform(0.006, 0.022))


def human_click_at(page: Page, x: float, y: float) -> None:
    human_mouse_move(page, x, y)
    time.sleep(random.uniform(0.04, 0.18))
    page.mouse.click(_jitter(x, 2.0), _jitter(y, 2.0))


def human_click_locator(page: Page, locator: Locator) -> None:
    locator.scroll_into_view_if_needed(timeout=2000)
    box = locator.bounding_box()
    if not box:
        locator.click(timeout=5000)
        return
    tx = box["x"] + box["width"] * random.uniform(0.28, 0.72)
    ty = box["y"] + box["height"] * random.uniform(0.30, 0.70)
    human_click_at(page, tx, ty)


def char_delay_ms(word: str, char_index: int) -> int:
    """Slower typing for longer words — not perfectly uniform."""
    base = random.randint(config.TYPE_DELAY_MIN_MS, config.TYPE_DELAY_MAX_MS)
    length_factor = 1.0 + max(0, len(word) - 5) * 0.04
    delay = int(base * length_factor)
    if char_index > 2 and random.random() < 0.1:
        delay += random.randint(80, 220)
    return delay


def has_blocking_warning(page: Page) -> bool:
    try:
        text = page.locator("body").inner_text(timeout=2000).lower()
    except PlaywrightTimeout:
        return False
    return any(keyword in text for keyword in WARNING_KEYWORDS)


def dismiss_blocking_dialogs(page: Page) -> bool:
    dismissed = False

    for pattern in DISMISS_BUTTON_PATTERNS:
        locator = page.get_by_role("button", name=re.compile(pattern, re.I))
        if locator.count() == 0:
            continue
        try:
            human_click_locator(page, locator.first)
            dismissed = True
            logger.info("Dismissed dialog via button: %s", pattern)
            break
        except PlaywrightTimeout:
            continue

    if not dismissed:
        for label in ("OK", "Got it", "Close", "Dismiss", "Continue"):
            locator = page.get_by_text(label, exact=True)
            if locator.count() == 0:
                continue
            try:
                human_click_locator(page, locator.first)
                dismissed = True
                logger.info("Dismissed dialog via text: %s", label)
                break
            except PlaywrightTimeout:
                continue

    if dismissed:
        page.wait_for_timeout(random.randint(400, 700))
    return dismissed


def _click_first_visible(page: Page, locators: tuple, label: str) -> None:
    for locator in locators:
        if locator.count() == 0:
            continue
        try:
            human_click_locator(page, locator.first)
            logger.info("Clicked %s", label)
            return
        except PlaywrightTimeout:
            continue
    raise RuntimeError(f"{label} not found")


def dismiss_promo_banners(page: Page) -> bool:
    """Close optional promo banners on the dashboard."""
    text = page.locator("body").inner_text(timeout=2000).lower()
    if not any(k in text for k in ("win big", "learn more", "chance to win", "contest")):
        return False

    locators = (
        page.locator("[class*='banner' i] button[class*='close' i]"),
        page.locator("[class*='alert' i] button[class*='close' i]"),
        page.get_by_role("button", name=re.compile(r"^close$|^dismiss$|×", re.I)),
    )
    for locator in locators:
        if locator.count() == 0:
            continue
        try:
            human_click_locator(page, locator.first)
            page.wait_for_timeout(random.randint(300, 600))
            logger.info("Dismissed promo banner")
            return True
        except PlaywrightTimeout:
            continue
    return False


def click_start_training(page: Page) -> None:
    human_pause(0.4, 0.8)
    _click_first_visible(
        page,
        (
            page.get_by_role("link", name=re.compile(r"start training", re.I)),
            page.get_by_role("button", name=re.compile(r"start training", re.I)),
            page.locator("a:has-text('Start Training')"),
            page.locator("button:has-text('Start Training')"),
            page.get_by_text(re.compile(r"start training\s*>?", re.I)),
        ),
        "Start Training",
    )


def _proceed_locators(page: Page) -> tuple:
    return (
        page.get_by_role("button", name=re.compile(r"^proceed$", re.I)),
        page.get_by_role("link", name=re.compile(r"^proceed$", re.I)),
        page.locator("button:has-text('Proceed')"),
        page.locator("a:has-text('Proceed')"),
        page.get_by_text(re.compile(r"^proceed$", re.I)),
    )


def proceed_button_visible(page: Page) -> bool:
    for locator in _proceed_locators(page):
        if locator.count() == 0:
            continue
        try:
            if locator.first.is_visible():
                return True
        except PlaywrightTimeout:
            continue
    return False


def wait_for_proceed_button(page: Page, timeout_s: float = 15.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proceed_button_visible(page):
            return True
        page.wait_for_timeout(350)
    return False


def duration_buttons_visible(page: Page) -> bool:
    buttons = page.locator("button").filter(has_text=re.compile(r"^\s*\d+\s*min\.?\s*$", re.I))
    return buttons.count() >= 3


def select_session_duration(page: Page, minutes: int) -> None:
    human_pause(0.5, 1.0)
    labels = (f"{minutes} min.", f"{minutes} min", f"{minutes} minutes")
    last_error: Optional[Exception] = None

    for label in labels:
        pattern = re.compile(rf"^{re.escape(label)}$", re.I)
        locators = (
            page.get_by_role("button", name=pattern),
            page.get_by_role("link", name=pattern),
            page.locator("button").filter(has_text=pattern),
            page.get_by_text(pattern),
        )
        for locator in locators:
            if locator.count() == 0:
                continue
            try:
                target = locator.first
                target.wait_for(state="visible", timeout=8000)
                human_click_locator(page, target)
                logger.info("Selected duration: %s", label)
                page.wait_for_timeout(random.randint(600, 1200))
                return
            except (PlaywrightTimeout, RuntimeError) as exc:
                last_error = exc
                continue

    raise RuntimeError(f"Duration button not found: {minutes} min") from last_error


def click_proceed(page: Page) -> None:
    if not wait_for_proceed_button(page, timeout_s=15.0):
        raise RuntimeError("Proceed button not visible yet")

    human_pause(0.6, 1.2)
    _click_first_visible(page, _proceed_locators(page), "Proceed")


def click_through_interstitial(page: Page) -> bool:
    """Click generic continue buttons on info/interstitial pages (not duration picker)."""
    if "you decide" in page.locator("body").inner_text(timeout=1500).lower():
        return False

    human_pause(0.3, 0.6)
    patterns = (
        (r"let'?s continue", "Let's continue"),
        (r"^continue$", "Continue"),
        (r"^got it$", "Got it"),
        (r"^ok$", "OK"),
        (r"^next$", "Next"),
    )
    for pattern, label in patterns:
        locators = (
            page.get_by_role("button", name=re.compile(pattern, re.I)),
            page.get_by_role("link", name=re.compile(pattern, re.I)),
            page.get_by_text(re.compile(pattern, re.I)),
        )
        for locator in locators:
            if locator.count() == 0:
                continue
            try:
                human_click_locator(page, locator.first)
                logger.info("Clicked through interstitial: %s", label)
                return True
            except PlaywrightTimeout:
                continue
    return False


def click_continue(page: Page) -> None:
    human_pause(0.4, 0.8)
    try:
        _click_first_visible(
            page,
            (
                page.get_by_role("button", name=re.compile(r"let'?s continue", re.I)),
                page.get_by_text(re.compile(r"let'?s continue", re.I)),
                page.get_by_role("button", name=re.compile(r"^continue$", re.I)),
                page.get_by_text(re.compile(r"^continue$", re.I)),
                page.get_by_role("button", name=re.compile(r"^proceed$", re.I)),
            ),
            "Continue",
        )
    except RuntimeError:
        if not click_through_interstitial(page):
            raise


def click_next(page: Page, *, after_quiz: bool = False) -> None:
    if not after_quiz:
        human_pause(0.5, 0.9)

    locators = (
        page.get_by_text("Next", exact=True),
        page.locator("a:has-text('Next')"),
        page.locator("button:has-text('Next')"),
        page.get_by_role("button", name=re.compile(r"next", re.I)),
        page.get_by_role("link", name=re.compile(r"next", re.I)),
        page.locator("text=Next"),
    )
    for locator in locators:
        if locator.count() == 0:
            continue
        try:
            human_click_locator(page, locator.first)
            logger.info("Clicked Next")
            return
        except PlaywrightTimeout:
            continue

    raise RuntimeError("Next button not found")


def click_option_by_text(page: Page, option_text: str) -> None:
    human_pause(0.5, 1.2)
    text = option_text.strip()
    for locator in (page.get_by_text(text, exact=True), page.locator(f"text={text}")):
        if locator.count() == 0:
            continue
        try:
            human_click_locator(page, locator.first)
            logger.info("Clicked option: %s", text[:60])
            return
        except PlaywrightTimeout:
            continue
    raise RuntimeError(f"Could not click option: {text!r}")


def click_option_by_letter(page: Page, options: Dict[str, str], letter: str) -> None:
    letter = letter.lower()
    if letter not in options:
        raise KeyError(f"Option {letter} not in {list(options)}")
    click_option_by_text(page, options[letter])


def find_spell_input(page: Page) -> Optional[Locator]:
    selectors = (
        "input[type='text']",
        "input:not([type='hidden'])",
        "input[autocomplete='off']",
        "input[inputmode]",
        "[contenteditable='true']",
        "textarea",
    )
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            logger.info("Spell input found: %s", selector)
            return locator.first
    return None


def focus_spell_area(page: Page) -> str:
    candidates = (
        ("instruction", page.get_by_text(re.compile(r"spell the word", re.I))),
        ("underscores", page.locator("text=/(_\\s*){2,}/")),
        ("underscores_alt", page.get_by_text(re.compile(r"(_\s*){2,}"))),
        ("spell_box", page.locator("[class*='spell' i]").first),
        ("typing_box", page.locator("[class*='typing' i]").first),
    )
    for name, locator in candidates:
        if locator.count() == 0:
            continue
        try:
            target = locator.first
            box = target.bounding_box()
            if box:
                tx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                ty = box["y"] + box["height"] * random.uniform(0.4, 0.6)
                human_click_at(page, tx, ty)
            else:
                human_click_locator(page, target)
            logger.info("Spell focus via: %s", name)
            return name
        except PlaywrightTimeout:
            continue

    viewport = page.viewport_size or {"width": 1280, "height": 720}
    human_click_at(page, viewport["width"] // 2, int(viewport["height"] * 0.45))
    logger.warning("Spell focus fallback: viewport center")
    return "viewport"


def type_into_locator(locator: Locator, word: str) -> None:
    page = locator.page
    human_click_locator(page, locator)
    time.sleep(random.uniform(0.1, 0.25))
    try:
        locator.fill("")
    except PlaywrightTimeout:
        pass
    for i, char in enumerate(word):
        page.keyboard.type(char, delay=char_delay_ms(word, i))


def type_word_human(page: Page, word: str) -> None:
    human_pause(config.SPELL_PAUSE_BEFORE_MIN, config.SPELL_PAUSE_BEFORE_MAX)

    spell_input = find_spell_input(page)
    if spell_input:
        type_into_locator(spell_input, word)
    else:
        focus_spell_area(page)
        page.wait_for_timeout(random.randint(200, 450))
        for i, char in enumerate(word):
            page.keyboard.type(char, delay=char_delay_ms(word, i))

    human_pause(config.SPELL_PAUSE_AFTER_MIN, config.SPELL_PAUSE_AFTER_MAX)
    page.keyboard.press("Enter")
    logger.info("Typed word: %s", word)
