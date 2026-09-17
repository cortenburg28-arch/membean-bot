"""Read and write .env settings for the settings UI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

ENV_PATH = config.ROOT_DIR / ".env"
EXAMPLE_PATH = config.ROOT_DIR / ".env.example"

_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _defaults() -> Dict[str, str]:
    return {
        "AI_PROVIDER": "groq",
        "AI_API_URL": "https://api.groq.com/openai/v1",
        "AI_MODEL": "allam-2-7b",
        "AI_API_KEY": "",
        "ANSWER_MODE": "ai",
        "AI_PROMPT_STYLE": "compact",
        "MEMBEAN_HOME_URL": "https://membean.com",
        "MEMBEAN_DASHBOARD_URL": "https://membean.com/dashboard",
        "MEMBEAN_TRAINING_URL": "",
        "AUTO_START_TRAINING": "true",
        "SESSION_DURATION_MINUTES": "10",
        "HEADLESS": "false",
        "BROWSER_SLOW_MO": "0",
        "DELAY_MIN": "0.8",
        "DELAY_MAX": "2.5",
        "READ_PAUSE_MIN": "2.0",
        "READ_PAUSE_MAX": "5.0",
        "THINK_PAUSE_MIN": "1.0",
        "THINK_PAUSE_MAX": "3.0",
        "PAGE_TRANSITION_MIN": "0.5",
        "PAGE_TRANSITION_MAX": "1.5",
        "LEARN_PAGE_WAIT": "1.0",
        "QUIZ_LOAD_WAIT_MIN": "3.0",
        "QUIZ_LOAD_WAIT_MAX": "6.0",
        "QUIZ_AFTER_ANSWER_WAIT": "2.0",
        "SPELL_PAUSE_BEFORE_MIN": "1.0",
        "SPELL_PAUSE_BEFORE_MAX": "2.5",
        "SPELL_PAUSE_AFTER_MIN": "0.4",
        "SPELL_PAUSE_AFTER_MAX": "0.9",
        "TYPE_DELAY_MIN_MS": "90",
        "TYPE_DELAY_MAX_MS": "220",
        "SURVEY_REALISTIC_RATE": "0.95",
        "QUIZ_TARGET_ACCURACY": "100",
    }


def parse_env_file(path: Path) -> Dict[str, str]:
    values = _defaults()
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _KEY_RE.match(stripped)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def load_settings() -> Dict[str, str]:
    return parse_env_file(ENV_PATH)


def _format_value(key: str, value: Any) -> str:
    if key == "HEADLESS":
        return "true" if str(value).lower() in {"1", "true", "yes", "on"} else "false"
    if key == "SURVEY_REALISTIC_RATE":
        rate = float(value)
        if rate > 1.0:
            rate = rate / 100.0
        return f"{rate:.2f}".rstrip("0").rstrip(".")
    return str(value).strip()


def save_settings(updates: Dict[str, Any]) -> None:
    """Merge updates into .env, preserving comments and unknown keys."""
    source = ENV_PATH if ENV_PATH.exists() else EXAMPLE_PATH
    lines: List[str] = []
    seen: set[str] = set()

    if source.exists():
        lines = source.read_text(encoding="utf-8").splitlines()

    normalized = {k: _format_value(k, v) for k, v in updates.items()}

    new_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        match = _KEY_RE.match(stripped) if stripped and not stripped.startswith("#") else None
        if match:
            key = match.group(1)
            if key in normalized:
                new_lines.append(f"{key}={normalized[key]}")
                seen.add(key)
                continue
        new_lines.append(line)

    for key, value in normalized.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def settings_for_api() -> Dict[str, Any]:
    """Return settings with UI-friendly types."""
    raw = load_settings()
    return {
        **raw,
        "HEADLESS": raw.get("HEADLESS", "false").lower() in {"1", "true", "yes"},
        "AUTO_START_TRAINING": raw.get("AUTO_START_TRAINING", "true").lower() in {"1", "true", "yes"},
        "SESSION_DURATION_MINUTES": int(raw.get("SESSION_DURATION_MINUTES", "10")),
        "SURVEY_REALISTIC_PERCENT": round(float(raw.get("SURVEY_REALISTIC_RATE", "0.95")) * 100),
        "QUIZ_TARGET_ACCURACY": float(raw.get("QUIZ_TARGET_ACCURACY", "100")),
        "BROWSER_SLOW_MO": int(raw.get("BROWSER_SLOW_MO", "0")),
        "TYPE_DELAY_MIN_MS": int(raw.get("TYPE_DELAY_MIN_MS", "90")),
        "TYPE_DELAY_MAX_MS": int(raw.get("TYPE_DELAY_MAX_MS", "220")),
    }


def apply_api_payload(payload: Dict[str, Any]) -> None:
    """Validate and save settings from the web UI."""
    allowed = set(_defaults().keys())
    updates: Dict[str, Any] = {}

    for key, value in payload.items():
        if key == "SURVEY_REALISTIC_PERCENT":
            updates["SURVEY_REALISTIC_RATE"] = float(value) / 100.0
            continue
        if key == "QUIZ_TARGET_ACCURACY":
            updates["QUIZ_TARGET_ACCURACY"] = str(float(value))
            continue
        if key == "AUTO_START_TRAINING":
            updates["AUTO_START_TRAINING"] = "true" if value else "false"
            continue
        if key == "SESSION_DURATION_MINUTES":
            updates["SESSION_DURATION_MINUTES"] = str(int(value))
            continue
        if key in allowed:
            updates[key] = value

    if "HEADLESS" in updates:
        updates["HEADLESS"] = "true" if updates["HEADLESS"] else "false"

    save_settings(updates)
