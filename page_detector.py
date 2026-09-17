"""Detect which Membean training page is currently shown."""

from __future__ import annotations

import logging
import re
from typing import Literal

from playwright.sync_api import Page

logger = logging.getLogger(__name__)

PageType = Literal["spell", "mcq", "survey", "learn", "continue", "done", "unknown"]

SURVEY_KEYWORDS = (
    "how well do you",
    "how difficult",
    "how familiar",
    "have you seen this word",
    "have you heard this word",
    "how confident",
    "how sure are you",
    "rate your",
    "did you know",
    "before today",
    "how often",
)

DONE_KEYWORDS = (
    "take a break",
    "session complete",
    "training complete",
    "great job",
    "you're done",
    "you’ve done",
    "you are done",
    "see you next time",
    "finished your training",
    "session summary",
    "been in this study session for",
    "studying for prolonged periods",
)

OPTION_LINE = re.compile(r"^\s*([a-d])\.\s*(.+)$", re.IGNORECASE | re.MULTILINE)
QUESTION_LINE = re.compile(r"^\s*Q:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
QUIZ_LINE = re.compile(r"^\s*Quiz:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def get_body_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


def page_has_time_limit(page: Page) -> bool:
    """Membean timed tasks — skip long pauses to avoid timeouts."""
    text = get_body_text(page).lower()
    return "allotted time" in text or "time left" in text or "seconds left" in text


def has_labeled_choice_options(text: str) -> bool:
    letters = set(OPTION_LINE.findall(text))
    return len(letters) >= 2


def has_mcq_layout(text: str) -> bool:
    """Membean MCQ: Q: question + option lines (often without a./b./ prefixes)."""
    if not (QUESTION_LINE.search(text) or QUIZ_LINE.search(text)):
        return False
    if has_labeled_choice_options(text):
        return True
    if "i'm not sure" in text.lower() or "i’m not sure" in text.lower():
        return True
    return count_option_lines(text) >= 3


def count_option_lines(text: str) -> int:
    """Count lines after Q: that look like answer choices."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*Q:\s*", line, re.I) or re.match(r"^\s*Quiz:\s*", line, re.I):
            start = i + 1
            break
    if start is None:
        return 0

    stop_words = (
        "allotted time",
        "i'm done",
        "next",
        "context",
        "word ingredients",
        "membean",
        "copyright",
    )
    count = 0
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            if count >= 2:
                break
            continue
        lower = stripped.lower()
        if any(lower.startswith(w) for w in stop_words):
            break
        if lower in {"answer", "definition"}:
            continue
        count += 1
        if count >= 4:
            break
    return count


def has_next_button(page: Page) -> bool:
    return page.get_by_role("button", name=re.compile(r"^next$", re.I)).count() > 0


def has_spell_instruction(text: str) -> bool:
    lower = text.lower()
    return "spell the word" in lower or "spell the word you saw" in lower


def has_learn_markers(text: str) -> bool:
    lower = text.lower()
    markers = (
        "word ingredients",
        "memory hook",
        "word theater",
        "context",
        "definition",
    )
    return any(marker in lower for marker in markers)


def has_learn_quiz(text: str) -> bool:
    return bool(QUIZ_LINE.search(text)) and has_learn_markers(text)


def is_survey_question(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in SURVEY_KEYWORDS)


def is_done_page_from(page: Page, text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in DONE_KEYWORDS)


def is_continue_page(text: str) -> bool:
    lower = text.lower()
    markers = (
        "let's continue",
        "lets continue",
        "you've just answered",
        "you’ve just answered",
        "root question",
        "click below to continue",
        "ready to continue",
        "before we begin",
        "here's how",
        "here is how",
        "good to know",
        "just so you know",
    )
    return any(marker in lower for marker in markers)


def detect_page_type(page: Page) -> PageType:
    """Return the current Membean page type."""
    text = get_body_text(page)
    url = page.url.lower()

    if is_done_page_from(page, text):
        logger.debug("Detected done page")
        return "done"

    if is_continue_page(text):
        logger.debug("Detected continue/interstitial page")
        return "continue"

    if has_spell_instruction(text):
        logger.debug("Detected spell page")
        return "spell"

    # Learn page with embedded quiz (Quiz: ...) — before standalone MCQ.
    if has_next_button(page) and has_learn_quiz(text):
        logger.debug("Detected learn page with quiz")
        return "learn"

    if has_next_button(page) and has_learn_markers(text):
        logger.debug("Detected learn page")
        return "learn"

    # Standalone vocabulary MCQ (Q: ...)
    if QUESTION_LINE.search(text) and has_mcq_layout(text):
        if is_survey_question(text):
            logger.debug("Detected survey page")
            return "survey"
        logger.debug("Detected mcq page")
        return "mcq"

    if has_labeled_choice_options(text) and is_survey_question(text):
        logger.debug("Detected survey page (labeled options)")
        return "survey"

    if has_next_button(page) and "training_sessions" in url:
        logger.debug("Detected learn page (fallback)")
        return "learn"

    if has_mcq_layout(text) and "training_sessions" in url:
        logger.debug("Detected mcq page (fallback)")
        return "mcq"

    logger.debug("Unknown page (url=%s)", page.url)
    return "unknown"


def describe_page(page: Page) -> dict:
    """Detect page type and return debug info."""
    text = get_body_text(page)
    page_type = detect_page_type(page)
    return {
        "type": page_type,
        "url": page.url,
        "has_next": has_next_button(page),
        "has_choices": has_labeled_choice_options(text) or count_option_lines(text) >= 3,
        "has_q": bool(QUESTION_LINE.search(text)),
        "text_preview": text[:400].replace("\n", " | "),
    }
