"""Main automation loop for Membean sessions."""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Dict, Optional, Tuple

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

import config
from actions import (
    click_continue,
    click_next,
    click_option_by_letter,
    dismiss_blocking_dialogs,
    has_blocking_warning,
    human_pause,
    page_transition_pause,
    thinking_pause,
    type_word_human,
)
from answer_engine import pick_answer
from browser import save_debug_screenshot
from extractors import (
    extract_learn_page,
    extract_mcq_page,
    extract_page,
    extract_question,
    extract_spell_page,
    extract_survey_page,
    extract_word_from_page,
    page_has_learn_quiz,
)
from answer_engine import apply_quiz_target_accuracy
from page_detector import PageType, detect_page_type, get_body_text, page_has_time_limit
from session_flow import try_recover_unknown_page
from word_log import WordLog

logger = logging.getLogger(__name__)


def stable_fingerprint(page: Page, page_type: PageType, cache_word: Optional[str] = None) -> Tuple[str, str]:
    text = get_body_text(page)

    if page_type == "continue":
        return page_type, "interstitial"

    if page_type == "spell":
        return page_type, cache_word or "spell"

    if page_type == "learn":
        word = extract_word_from_page(page, text)
        return page_type, word or "learn"

    question = extract_question(text)
    if question:
        return page_type, question[:120]

    word = extract_word_from_page(page, text)
    if word:
        return page_type, word

    cleaned = re.sub(r"allotted time", "", text, flags=re.I)
    return page_type, cleaned[:100]


class WordCache:
    def __init__(self, word_log: Optional[WordLog] = None) -> None:
        self.words: Dict[str, str] = {}
        self.word_log = word_log

    def update(self, word: Optional[str], context: str = "", *, log: bool = True) -> None:
        if word:
            if context:
                self.words[word] = context
            elif word not in self.words:
                self.words[word] = ""
            logger.info("Cached word: %s", word)
            if log and self.word_log:
                explanation = context or self.words.get(word, "")
                self.word_log.record(word, explanation)

    @property
    def last_word(self) -> Optional[str]:
        if not self.words:
            return None
        return next(reversed(self.words))

    def context_for(self, word: Optional[str]) -> str:
        if word and word in self.words:
            return self.words[word]
        if self.last_word:
            return self.words.get(self.last_word, "")
        return ""


def page_closed(page: Page) -> bool:
    try:
        return page.is_closed()
    except PlaywrightError:
        return True


def wait_until_changed(
    page: Page,
    old_fp: Tuple[str, str],
    cache_word: Optional[str],
    timeout_s: float = 120.0,
) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if page_closed(page):
            return False
        dismiss_blocking_dialogs(page)
        page.wait_for_timeout(500)
        page_type = detect_page_type(page)
        fp = stable_fingerprint(page, page_type, cache_word)
        if fp != old_fp:
            return True
    return False


def wait_until_not(page: Page, unwanted: PageType, timeout_s: float = 15.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if page_closed(page):
            return False
        dismiss_blocking_dialogs(page)
        page.wait_for_timeout(400)
        if detect_page_type(page) != unwanted:
            return True
    return False


def quiz_visible_on_page(page: Page) -> bool:
    if page.get_by_text(re.compile(r"Quiz:", re.I)).count() > 0:
        return True
    return page_has_learn_quiz(get_body_text(page))


def wait_for_learn_quiz(page: Page) -> dict:
    """Wait until quiz is loaded or confirmed absent. Never rush Next."""
    wait_ms = int(random.uniform(config.QUIZ_LOAD_WAIT_MIN, config.QUIZ_LOAD_WAIT_MAX) * 1000)
    page.wait_for_timeout(wait_ms)

    data: dict = {}
    deadline = time.time() + 6.0
    while time.time() < deadline:
        dismiss_blocking_dialogs(page)
        data = extract_learn_page(page)
        quiz_visible = quiz_visible_on_page(page)

        if not quiz_visible:
            return data
        if data.get("quiz_ready"):
            return data

        logger.info("Quiz sichtbar, warte auf Optionen…")
        page.wait_for_timeout(500)

    return extract_learn_page(page)


def handle_continue(page: Page) -> None:
    dismiss_blocking_dialogs(page)
    human_pause(0.4, 0.9)
    click_continue(page)


def answer_and_click(
    page: Page,
    question: str,
    options: Dict[str, str],
    *,
    word: str = "",
    context: str = "",
    page_type: str = "mcq",
) -> str:
    if page_type in ("mcq", "learn") and not page_has_time_limit(page):
        thinking_pause()
    letter, method = pick_answer(
        question,
        options,
        word=word,
        context=context,
        page_type=page_type,
    )
    if page_type in ("mcq", "learn"):
        letter = apply_quiz_target_accuracy(letter, options)
    print(f"  ↳ Antwort: {letter.upper()} ({method}, 0 Tokens)" if method != "ai" else f"  ↳ Antwort: {letter.upper()} (KI)")
    click_option_by_letter(page, options, letter)
    return letter


def handle_learn(page: Page, cache: WordCache) -> bool:
    """Quiz zuerst, dann Next. Warnungen wegklicken."""
    dismiss_blocking_dialogs(page)

    data = wait_for_learn_quiz(page)
    word = data.get("word") or ""
    explanation = data.get("explanation") or data.get("context") or data.get("definition") or ""
    cache.update(word, explanation)

    quiz_visible = quiz_visible_on_page(page)

    if quiz_visible:
        if not data.get("quiz_ready"):
            print("  ↳ Quiz noch nicht bereit — kein Next.")
            return False

        print("  ↳ Quiz zuerst beantworten…")
        options = data.get("quiz_options") or {}
        question = data.get("quiz_question") or ""
        answer_and_click(page, question, options, word=word, context=explanation, page_type="learn")

        time.sleep(config.QUIZ_AFTER_ANSWER_WAIT)
        dismiss_blocking_dialogs(page)

        if has_blocking_warning(page):
            dismiss_blocking_dialogs(page)
            print("  ↳ Warnung erkannt — Next abgebrochen, nochmal versuchen.")
            return False
    else:
        human_pause(0.8, 1.2)

    dismiss_blocking_dialogs(page)
    try:
        click_next(page, after_quiz=quiz_visible)
    except RuntimeError:
        logger.warning("Next button not found on learn page")
        print("  ↳ Next nicht gefunden — bitte manuell klicken (oben rechts).")
        return False

    page.wait_for_timeout(800)
    if has_blocking_warning(page):
        dismiss_blocking_dialogs(page)
        print("  ↳ Warnung nach Next — Seite nochmal bearbeiten.")
        return False

    wait_until_not(page, "learn", timeout_s=12.0)
    return True


def handle_mcq(page: Page, cache: WordCache) -> None:
    dismiss_blocking_dialogs(page)
    data = extract_mcq_page(page)
    word = data.get("word") or cache.last_word or ""
    context = cache.context_for(word)
    question = data.get("question") or ""
    options = data.get("options") or {}
    if not options or not question:
        print("  ↳ MCQ nicht lesbar — bitte manuell.")
        return
    if word and cache.word_log and word not in cache.words:
        cache.update(word, context or question, log=True)
    elif word and cache.word_log:
        cache.update(word, context, log=False)
    answer_and_click(page, question, options, word=word, context=context, page_type="mcq")


def handle_survey(page: Page) -> None:
    dismiss_blocking_dialogs(page)
    data = extract_survey_page(page)
    question = data.get("question") or ""
    options = data.get("options") or {}
    if not options:
        print("  ↳ Survey nicht lesbar — bitte manuell.")
        return
    answer_and_click(page, question, options, page_type="survey")


def handle_spell(page: Page, cache: WordCache) -> None:
    dismiss_blocking_dialogs(page)
    word = cache.last_word
    if not word:
        print("  ↳ Kein Wort im Cache — bitte manuell buchstabieren.")
        return

    page.wait_for_timeout(1200)
    data = extract_spell_page(page)
    expected_len = data.get("length")
    if expected_len and len(word) != expected_len:
        logger.warning("Length mismatch: word=%s (%s) expected %s", word, len(word), expected_len)

    print(f"  ↳ Buchstabiere: {word}")
    type_word_human(page, word)


def run_session(page: Page) -> None:
    word_log = WordLog()
    cache = WordCache(word_log=word_log)
    handled_fp: Optional[Tuple[str, str]] = None
    spelled_words: set[str] = set()
    learn_completed: set[str] = set()

    print("Automation running. Ctrl+C to stop.")
    print(f"  • Antworten: {config.AI_PROVIDER.upper()} ({config.AI_MODEL})")
    print(f"  • Quiz-Ziel: {config.QUIZ_TARGET_ACCURACY:.0f}% | KI-Prompt: {config.AI_PROMPT_STYLE}")
    print(f"  • Wortliste: worter.txt ({word_log.count} bisher)")
    print("-" * 50)

    while True:
        try:
            if page_closed(page):
                print("\nBrowser geschlossen.")
                break

            if dismiss_blocking_dialogs(page):
                handled_fp = None
                continue

            human_pause(0.3, 0.7)
            page_type = detect_page_type(page)
            fp = stable_fingerprint(page, page_type, cache.last_word)

            if page_type == "spell" and cache.last_word in spelled_words:
                page.wait_for_timeout(600)
                continue

            if fp == handled_fp:
                continue

            logger.info("Handling page: %s", page_type)
            print(f"[{time.strftime('%H:%M:%S')}] → {page_type.upper()}")

            if page_type == "done":
                msg = extract_page(page).get("data", {}).get("message", "Session complete")
                print(f"\nFinished: {msg}")
                break

            if page_type == "continue":
                handle_continue(page)
                handled_fp = fp
                wait_until_changed(page, fp, cache.last_word, timeout_s=8.0)
                page_transition_pause()
                handled_fp = None
                continue

            if page_type == "learn":
                learn_word = fp[1]
                if learn_word in learn_completed:
                    page.wait_for_timeout(600)
                    continue
                ok = handle_learn(page, cache)
                if ok and learn_word not in ("learn", "?"):
                    learn_completed.add(learn_word)
                else:
                    learn_completed.discard(learn_word)
                handled_fp = fp if ok else None
                if ok and not page_has_time_limit(page):
                    page_transition_pause()
                continue

            if page_type == "spell":
                if cache.last_word and cache.last_word in spelled_words:
                    continue
                handle_spell(page, cache)
                if cache.last_word:
                    spelled_words.add(cache.last_word)
                handled_fp = fp
                wait_until_not(page, "spell", timeout_s=15.0)
                if not page_has_time_limit(page):
                    page_transition_pause()
                handled_fp = None
                continue

            if page_type == "mcq":
                handle_mcq(page, cache)
                handled_fp = fp
                wait_until_changed(page, fp, cache.last_word, timeout_s=12.0)
                if not page_has_time_limit(page):
                    page_transition_pause()
                handled_fp = None
                continue

            if page_type == "survey":
                handle_survey(page)
                handled_fp = fp
                wait_until_changed(page, fp, cache.last_word, timeout_s=12.0)
                if not page_has_time_limit(page):
                    page_transition_pause()
                handled_fp = None
                continue

            if page_type == "unknown":
                if dismiss_blocking_dialogs(page):
                    handled_fp = None
                    continue
                if try_recover_unknown_page(page):
                    handled_fp = None
                    continue
                logger.warning("Unknown page at %s", page.url)
                save_debug_screenshot(page, f"unknown_{int(time.time())}")
                human_pause(1.5, 2.5)
                handled_fp = fp
                continue

            handled_fp = fp

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except PlaywrightError as exc:
            if "closed" in str(exc).lower():
                print("\nBrowser geschlossen.")
                break
            dismiss_blocking_dialogs(page)
            logger.exception("Playwright error")
            print(f"  ↳ Browser-Fehler: {exc}")
            human_pause(2.0, 3.0)
            handled_fp = None
        except Exception:
            dismiss_blocking_dialogs(page)
            logger.exception("Error in automation loop")
            if not page_closed(page):
                try:
                    save_debug_screenshot(page, f"error_{int(time.time())}")
                except PlaywrightError:
                    pass
            print("  ↳ Fehler — retry in 3s...")
            human_pause(2.0, 3.5)
            handled_fp = None
