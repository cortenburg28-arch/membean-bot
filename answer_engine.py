"""Answer MCQ/survey/learn-quiz with minimal or zero tokens."""

from __future__ import annotations

import logging
import random
import re
from typing import Dict, Optional, Tuple

import config

logger = logging.getLogger(__name__)

NOT_SURE = ("not sure", "i'm not sure", "i’m not sure")


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-z]{3,}", text.lower())
    stop = {
        "the", "and", "for", "that", "with", "you", "your", "this", "from",
        "have", "has", "are", "was", "were", "not", "but", "when", "what",
        "how", "who", "they", "them", "their", "about", "into", "over", "would",
    }
    return {w for w in words if w not in stop}


def _valid_options(options: Dict[str, str]) -> Dict[str, str]:
    return {k.lower(): v for k, v in options.items() if k.lower() in "abcd"}


def _is_not_sure(label: str) -> bool:
    lower = label.lower()
    return any(p in lower for p in NOT_SURE)


def score_option(label: str, reference: str) -> float:
    if _is_not_sure(label):
        return -1.0
    ref = _tokenize(reference)
    opt = _tokenize(label)
    if not ref or not opt:
        return 0.0
    overlap = len(ref & opt)
    return overlap / max(len(opt), 1)


def pick_from_context(reference: str, options: Dict[str, str]) -> Tuple[Optional[str], float]:
    options = _valid_options(options)
    if len(options) < 2 or not reference.strip():
        return None, 0.0

    best_letter = None
    best_score = 0.0
    for letter, label in options.items():
        score = score_option(label, reference)
        if score > best_score:
            best_score = score
            best_letter = letter

    if best_letter and best_score >= 0.15:
        return best_letter, best_score
    return None, best_score


def pick_survey(question: str, options: Dict[str, str]) -> str:
    """Rule-based survey answers — 0 tokens, realistic middle choices."""
    options = _valid_options(options)
    q = question.lower()
    labels = list(options.items())

    def find_keyword(keywords: tuple, prefer_last: bool = False) -> Optional[str]:
        matches = [
            letter
            for letter, label in labels
            if any(k in label.lower() for k in keywords) and not _is_not_sure(label)
        ]
        if not matches:
            return None
        return matches[-1 if prefer_last else 0]

    if "how well" in q or "how confident" in q or "familiar" in q:
        letter = find_keyword(("kind of", "somewhat", "moderately", "fairly"))
        if letter:
            return letter

    if "how difficult" in q or "how hard" in q:
        letter = find_keyword(("moderate", "somewhat", "average", "little"))
        if letter:
            return letter

    if "have you seen" in q or "have you heard" in q or "before today" in q:
        letter = find_keyword(("seen it", "heard it", "once", "few times"))
        if letter:
            return letter

    # Default: middle option (not first/last extreme)
    letters = sorted(options.keys())
    if len(letters) >= 3:
        return letters[len(letters) // 2]
    return letters[0]


def apply_quiz_target_accuracy(letter: str, options: Dict[str, str]) -> str:
    """Optionally miss some MCQ/Learn answers to hit a target accuracy (e.g. 87 %)."""
    target = config.QUIZ_TARGET_ACCURACY
    if target >= 100:
        return letter

    if random.random() * 100 < target:
        return letter

    options = _valid_options(options)
    wrong = [
        key
        for key in sorted(options.keys())
        if key != letter and not _is_not_sure(options[key])
    ]
    if not wrong:
        wrong = [key for key in sorted(options.keys()) if key != letter]
    if not wrong:
        return letter

    varied = random.choice(wrong)
    logger.info("Quiz target %s%% — absichtlich daneben: %s → %s", target, letter, varied)
    return varied


def pick_survey_humanized(question: str, options: Dict[str, str]) -> str:
    """95 % realistische Antwort, 5 % leicht daneben — nicht immer gleich."""
    options = _valid_options(options)
    ideal = pick_survey(question, options)

    if random.random() < config.SURVEY_REALISTIC_RATE:
        return ideal

    letters = sorted(options.keys())
    if ideal not in letters:
        return ideal

    idx = letters.index(ideal)
    shift = random.choice([-1, 1])
    varied_idx = max(0, min(len(letters) - 1, idx + shift))
    varied = letters[varied_idx]
    logger.info("Survey varied: %s → %s (5%% human imperfection)", ideal, varied)
    return varied


def pick_with_ai(
    question: str,
    options: Dict[str, str],
    *,
    word: str = "",
    context: str = "",
    page_type: str = "mcq",
) -> str:
    from ai_client import ask_ai, build_minimal_prompt

    prompt = build_minimal_prompt(
        question, options, word=word, context=context[:200], page_type=page_type
    )
    return ask_ai(prompt)


def pick_answer(
    question: str,
    options: Dict[str, str],
    *,
    word: str = "",
    context: str = "",
    page_type: str = "mcq",
) -> Tuple[str, str]:
    """
    Pick answer letter a-d.
    Returns (letter, method) where method is 'context', 'survey', or 'ai'.
    """
    options = _valid_options(options)
    if len(options) < 2:
        raise ValueError("Need at least 2 options")

    mode = config.ANSWER_MODE.lower()

    if page_type == "survey":
        letter = pick_survey_humanized(question, options)
        return letter, "survey"

    if mode == "ai":
        letter = pick_with_ai(
            question, options, word=word, context=context, page_type=page_type
        )
        logger.info("Answer via AI (%s): %s", page_type, letter)
        return letter, "ai"

    reference = " ".join(filter(None, [context, word, question])).strip()
    letter, score = pick_from_context(reference, options)

    if letter and mode in ("context", "hybrid"):
        logger.info("Answer via context (score=%.2f): %s", score, letter)
        return letter, "context"

    if mode == "hybrid":
        try:
            letter = pick_with_ai(
                question, options, word=word, context=context, page_type=page_type
            )
            logger.info("Answer via AI: %s", letter)
            return letter, "ai"
        except Exception:
            logger.exception("AI answer failed")
            if letter:
                return letter, "context-fallback"

    if letter:
        return letter, "context"

    # Last resort: first non-"not sure" option
    for key in sorted(options.keys()):
        if not _is_not_sure(options[key]):
            return key, "guess"

    return "a", "guess"
