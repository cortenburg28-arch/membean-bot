"""Append encountered vocabulary to worter.txt."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

WORTER_PATH = config.ROOT_DIR / "worter.txt"
ENTRY_RE = re.compile(r"^([a-zA-Z][a-zA-Z'-]*)\s*[—–-]\s*(.+)$")


def _normalize_word(word: str) -> str:
    return re.sub(r"[^a-zA-Z'-]", "", word.strip().lower())


def _shorten(text: str, max_len: int = 220) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


class WordLog:
    """Track words in worter.txt — no duplicates across sessions."""

    def __init__(self, path: Path = WORTER_PATH) -> None:
        self.path = path
        self._known = self._load_existing()

    def _load_existing(self) -> set[str]:
        known: set[str] = set()
        if not self.path.exists():
            return known
        for line in self.path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = ENTRY_RE.match(stripped)
            if match:
                known.add(_normalize_word(match.group(1)))
            else:
                word = _normalize_word(stripped.split()[0] if stripped.split() else "")
                if word:
                    known.add(word)
        return known

    def _ensure_header(self) -> None:
        if self.path.exists():
            return
        today = datetime.now().strftime("%Y-%m-%d")
        header = (
            f"# Membean Wörter — automatisch gespeichert\n"
            f"# Erstellt: {today}\n"
            f"# Format: wort — kurze Erklärung\n\n"
        )
        self.path.write_text(header, encoding="utf-8")

    def record(self, word: str, explanation: str = "") -> bool:
        """Append word if new. Returns True if written."""
        normalized = _normalize_word(word)
        if not normalized or len(normalized) < 3:
            return False
        if normalized in self._known:
            return False

        explanation = _shorten(explanation.strip()) if explanation.strip() else "(noch keine Erklärung)"
        line = f"{normalized} — {explanation}\n"

        self._ensure_header()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)

        self._known.add(normalized)
        logger.info("Logged word to %s: %s", self.path.name, normalized)
        print(f"  ↳ Wort gespeichert: {normalized}")
        return True

    @property
    def count(self) -> int:
        return len(self._known)
