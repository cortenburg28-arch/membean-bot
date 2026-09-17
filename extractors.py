"""Extract words, questions, and answer options from Membean pages."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from playwright.sync_api import Page

from page_detector import PageType, detect_page_type, get_body_text

logger = logging.getLogger(__name__)

OPTION_LINE = re.compile(r"^\s*([a-d])\.\s*(.+)$", re.IGNORECASE | re.MULTILINE)
QUESTION_PATTERNS = (
    re.compile(r"Quiz:\s*(.+?)(?:\n|$)", re.IGNORECASE),
    re.compile(r"Q:\s*(.+?)(?:\n|$)", re.IGNORECASE),
)

STOP_MARKERS = (
    "allotted time",
    "i'm done",
    "i’m done",
    "next",
    "context",
    "word ingredients",
    "memory hook",
    "membean",
    "copyright",
    "all text and design",
)


def parse_labeled_options(text: str) -> Dict[str, str]:
    options: Dict[str, str] = {}
    for letter, label in OPTION_LINE.findall(text):
        options[letter.lower()] = label.strip()
    return options


def parse_unlabeled_options(text: str) -> Dict[str, str]:
    """Parse Membean options listed as plain lines after Q:/Quiz:."""
    lines = text.splitlines()
    question_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*Q:\s*", line, re.I) or re.match(r"^\s*Quiz:\s*", line, re.I):
            question_idx = i
            break
    if question_idx is None:
        return {}

    options: Dict[str, str] = {}
    letters = ["a", "b", "c", "d"]
    idx = 0
    for line in lines[question_idx + 1 :]:
        stripped = line.strip()
        if not stripped:
            if idx >= 2:
                break
            continue
        lower = stripped.lower()
        if any(lower.startswith(m) for m in STOP_MARKERS):
            break
        if lower in {"answer", "definition"}:
            continue
        if idx < len(letters):
            options[letters[idx]] = stripped
            idx += 1
        if idx >= 4:
            break
    return options


def parse_options(text: str) -> Dict[str, str]:
    labeled = parse_labeled_options(text)
    if len(labeled) >= 2:
        return labeled
    return parse_unlabeled_options(text)


def extract_question(text: str) -> Optional[str]:
    for pattern in QUESTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def extract_word_from_page(page: Page, text: str) -> Optional[str]:
    """Try several strategies to find the vocabulary word."""
    selectors = (
        "h1",
        "h2",
        ".word-title",
        "[class*='word']",
        "[data-word]",
    )
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() == 0:
            continue
        try:
            raw = locator.inner_text(timeout=1000).strip()
        except Exception:
            continue
        word = clean_word_candidate(raw)
        if word:
            return word

    # Membean MCQ layout: word often appears as standalone line after "Answer"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    skip = {"answer", "definition", "quiz", "context", "membean", "i'm done", "i’m done"}
    for i, line in enumerate(lines):
        lower = line.lower()
        if lower in skip:
            continue
        if lower.startswith("q:") or lower.startswith("quiz:"):
            break
        if re.match(r"^[A-Z]{2,}[-a-z]*$", line) and "-" in line:
            # pronunciation line like STACH-er — word is previous line
            if i > 0:
                word = clean_word_candidate(lines[i - 1])
                if word:
                    return word
            continue
        word = clean_word_candidate(line)
        if word and len(word) >= 4:
            return word

    return None


def clean_word_candidate(raw: str) -> Optional[str]:
    text = raw.strip()
    if not text:
        return None
    first_token = re.split(r"[\s,]", text)[0].lower()
    if first_token in {"verb", "noun", "adjective", "adverb", "quiz", "context", "answer"}:
        return None
    word = re.sub(r"[^a-zA-Z'-]", "", first_token)
    if len(word) < 3:
        return None
    if word.lower() in {"next", "quiz", "context", "definition", "membean", "allotted"}:
        return None
    return word.lower()


def extract_spell_length(text: str) -> Optional[int]:
    match = re.search(r"(_\s*)+", text)
    if not match:
        match = re.search(r"[_\s]{3,}", text)
    if match:
        return match.group(0).count("_")
    return None


def extract_learn_quiz(text: str) -> tuple[str, Dict[str, str]]:
    """Parse only the Quiz: block on learn pages (not standalone Q: MCQ)."""
    lines = text.splitlines()
    quiz_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*Quiz:\s*", line, re.I):
            quiz_idx = i
            break
    if quiz_idx is None:
        return "", {}

    q_match = re.match(r"^\s*Quiz:\s*(.+)", lines[quiz_idx], re.I)
    question = q_match.group(1).strip() if q_match else ""

    stop = (
        "word ingredients",
        "memory hook",
        "word theater",
        "definition",
        "examples",
        "next",
        "i'm done",
        "i’m done",
    )
    options: Dict[str, str] = {}
    letters = ["a", "b", "c", "d"]
    idx = 0
    for line in lines[quiz_idx + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(lower.startswith(s) for s in stop):
            break
        if idx < len(letters):
            options[letters[idx]] = stripped
            idx += 1
        if idx >= 4:
            break

    return question, options


def page_has_learn_quiz(text: str) -> bool:
    return bool(re.search(r"^\s*Quiz:\s*", text, re.I | re.MULTILINE))


def extract_learn_page(page: Page) -> dict:
    text = get_body_text(page)
    word = extract_word_from_page(page, text)
    quiz_question, quiz_options = extract_learn_quiz(text)

    context = ""
    context_match = re.search(
        r"Context\s*\n(.+?)(?:\nQuiz:|\nWord Ingredients|\nMemory Hook|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if context_match:
        context = context_match.group(1).strip()

    definition = ""
    definition_match = re.search(
        r"Definition\s*\n(.+?)(?:\nContext|\nQuiz:|\nWord Ingredients|\nMemory Hook|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if definition_match:
        definition = definition_match.group(1).strip()

    explanation = context or definition

    return {
        "word": word,
        "context": context,
        "definition": definition,
        "explanation": explanation,
        "quiz_question": quiz_question,
        "quiz_options": quiz_options,
        "has_quiz": page_has_learn_quiz(text),
        "quiz_ready": bool(quiz_question and len(quiz_options) >= 2),
    }


def extract_mcq_page(page: Page) -> dict:
    text = get_body_text(page)
    return {
        "word": extract_word_from_page(page, text),
        "question": extract_question(text) or "",
        "options": parse_options(text),
    }


def extract_survey_page(page: Page) -> dict:
    text = get_body_text(page)
    question = extract_question(text)
    if not question:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not OPTION_LINE.match(stripped):
                if stripped.lower() not in {"membean", "i'm done", "i’m done", "answer"}:
                    question = stripped
                    break
    return {
        "question": question or "",
        "options": parse_options(text),
    }


def extract_spell_page(page: Page) -> dict:
    text = get_body_text(page)
    return {
        "length": extract_spell_length(text),
        "instruction": "spell the word" if "spell" in text.lower() else "",
    }


def extract_page(page: Page) -> dict:
    """Extract structured data for the current page."""
    page_type: PageType = detect_page_type(page)
    base = {"page_type": page_type, "url": page.url}

    if page_type == "learn":
        base["data"] = extract_learn_page(page)
    elif page_type == "mcq":
        base["data"] = extract_mcq_page(page)
    elif page_type == "survey":
        base["data"] = extract_survey_page(page)
    elif page_type == "spell":
        base["data"] = extract_spell_page(page)
    elif page_type == "continue":
        base["data"] = {"message": "Interstitial — click Let's continue"}
    elif page_type == "done":
        text = get_body_text(page)
        base["data"] = {
            "message": text.split("\n")[0].strip() if text else "Session complete",
        }
    else:
        base["data"] = {"text_preview": get_body_text(page)[:500]}

    return base
