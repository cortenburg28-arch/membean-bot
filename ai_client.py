"""AI client — Groq, LM Studio, or any OpenAI-compatible API."""

from __future__ import annotations

import logging
import re
from typing import Optional

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

LETTER_PATTERN = re.compile(r"[abcd]", re.IGNORECASE)


def get_client() -> OpenAI:
    if not config.AI_API_KEY:
        raise ValueError("AI_API_KEY missing — set it in .env")
    return OpenAI(base_url=config.AI_API_URL, api_key=config.AI_API_KEY)


def parse_letter(raw: str) -> Optional[str]:
    match = LETTER_PATTERN.search(raw.strip())
    if match:
        return match.group(0).lower()
    return None


def ask_ai(prompt: str, *, temperature: float = 0.0) -> str:
    """Send a prompt and return a single letter a-d."""
    client = get_client()
    response = client.chat.completions.create(
        model=config.AI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=4,
    )
    raw = response.choices[0].message.content or ""
    letter = parse_letter(raw)
    if letter is None:
        raise ValueError(f"Invalid AI response (expected a-d): {raw!r}")
    return letter


def _clean_question(question: str) -> str:
    text = question.strip()
    for prefix in ("Q:", "Quiz:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix) :].strip()
    return text[:140]


def build_ultra_prompt(
    question: str,
    options: dict[str, str],
    *,
    word: str = "",
    page_type: str = "mcq",
) -> str:
    """Shortest prompt (~15-25 tokens). No context, no filler."""
    parts: list[str] = []
    if word:
        parts.append(word)
    parts.append(_clean_question(question))
    for key in sorted(options.keys()):
        if key in "abcd":
            parts.append(f"{key}){options[key][:55]}")
    parts.append("→a/b/c/d")
    return "\n".join(parts)


def build_standard_prompt(
    question: str,
    options: dict[str, str],
    *,
    word: str = "",
    context: str = "",
    page_type: str = "mcq",
) -> str:
    """Balanced prompt (~90-110 tokens). Word + short context + full options."""
    parts = ["Vocabulary quiz. Pick the best answer."]
    if word:
        parts.append(f"Word: {word}")
    if context:
        parts.append(f"Context: {context[:100]}")
    parts.append(f"Question: {_clean_question(question)}")
    for key in sorted(options.keys()):
        if key in "abcd":
            parts.append(f"{key}) {options[key][:85]}")
    parts.append("Reply with ONE letter only: a, b, c, or d.")
    return "\n".join(parts)


def build_compact_prompt(
    question: str,
    options: dict[str, str],
    *,
    word: str = "",
    context: str = "",
    page_type: str = "mcq",
) -> str:
    """Compact prompt (~50-70 tokens)."""
    parts = ["Vocab quiz. Best answer:"]
    if word:
        parts.append(f"Word: {word}")
    if context:
        parts.append(f"Hint: {context[:80]}")
    parts.append(f"Q: {_clean_question(question)}")
    for key in sorted(options.keys()):
        if key in "abcd":
            parts.append(f"{key}) {options[key][:70]}")
    parts.append("Letter only: a/b/c/d")
    return "\n".join(parts)


def build_minimal_prompt(
    question: str,
    options: dict[str, str],
    *,
    word: str = "",
    context: str = "",
    page_type: str = "mcq",
) -> str:
    """Route to ultra | compact | standard based on AI_PROMPT_STYLE."""
    style = config.AI_PROMPT_STYLE
    if style == "ultra":
        return build_ultra_prompt(question, options, word=word, page_type=page_type)
    if style == "compact":
        return build_compact_prompt(
            question, options, word=word, context=context, page_type=page_type
        )
    return build_standard_prompt(
        question, options, word=word, context=context, page_type=page_type
    )


def build_vocab_prompt(
    question: str,
    options: dict[str, str],
    *,
    word: str = "",
    context: str = "",
) -> str:
    return build_minimal_prompt(question, options, word=word, context=context)


def test_ai_connection() -> bool:
    prompt = build_minimal_prompt(
        question="Someone who is contemplating something is:",
        options={
            "a": "Carefully considering or watching it",
            "b": "Taking it without permission",
            "c": "Confused about what to do with it",
            "d": "I'm not sure",
        },
        word="contemplate",
    )
    try:
        letter = ask_ai(prompt)
        logger.info("AI test answer: %s (expected: a)", letter)
        return letter == "a"
    except Exception:
        logger.exception("AI connection test failed")
        return False
