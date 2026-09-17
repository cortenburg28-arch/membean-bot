"""Simple interactive menu for non-technical users."""

from __future__ import annotations

import importlib
import os
import sys

import config
from env_store import save_settings

SESSION_OPTIONS = (5, 10, 15, 20, 25, 30)


class EmptyArgs:
    pass


def clear_screen() -> None:
    if not sys.stdout.isatty():
        return
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="")


def pause(msg: str = "\nEnter drücken zum Weiter…") -> None:
    try:
        input(msg)
    except (KeyboardInterrupt, EOFError):
        print()
        raise SystemExit(0)


def banner() -> None:
    print()
    print("=" * 50)
    print("   Membean Bot — Vokabel-Training automatisch")
    print("=" * 50)
    print()


def status_line(label: str, ok: bool, detail: str = "") -> None:
    mark = "✓" if ok else "✗"
    extra = f" ({detail})" if detail else ""
    print(f"  {mark} {label}{extra}")


def check_setup() -> list[str]:
    problems: list[str] = []

    if not (config.ROOT_DIR / ".env").exists():
        problems.append("Keine .env — kopiere .env.example nach .env und trage Groq-Key ein.")

    if not config.AI_API_KEY:
        problems.append("AI_API_KEY fehlt in .env (von Christoph kopieren oder .env.example)")

    if not config.STORAGE_STATE_PATH.exists():
        problems.append("Noch nicht eingeloggt — Menüpunkt [2] Login.")

    if not (config.ROOT_DIR / "venv").exists():
        problems.append("venv fehlt — einmal Setup aus README durchführen.")

    return problems


def show_status() -> None:
    print("Status:")
    status_line("Python", True, sys.version.split()[0])
    status_line(".env", (config.ROOT_DIR / ".env").exists())
    status_line("Groq API-Key", bool(config.AI_API_KEY))
    status_line("Membean Login", config.STORAGE_STATE_PATH.exists())
    status_line("Wortliste", config.WORTER_PATH.exists(), config.WORTER_PATH.name)
    print(f"\n  Standard-Dauer: {config.SESSION_DURATION_MINUTES} Minuten")
    print(f"  KI-Modell:      {config.AI_MODEL}")

    problems = check_setup()
    if problems:
        print("\n  Noch zu erledigen:")
        for item in problems:
            print(f"    • {item}")
    print()


def pick_session_duration() -> int:
    """5-Minuten-Schritte von 5 bis 30."""
    current = config.SESSION_DURATION_MINUTES
    if current not in SESSION_OPTIONS:
        current = 10

    print("\n  Wie lange lernen? (5-Minuten-Schritte)\n")
    for i, minutes in enumerate(SESSION_OPTIONS, start=1):
        tag = "  ← zuletzt" if minutes == current else ""
        print(f"    [{i}]  {minutes} Minuten{tag}")
    print(f"\n    [Enter] = {current} Minuten beibehalten\n")

    while True:
        try:
            choice = input("  Auswahl (1–6): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            raise SystemExit(0)

        if not choice:
            return current
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(SESSION_OPTIONS):
                return SESSION_OPTIONS[idx - 1]
        print("  Bitte 1–6 oder Enter.")


def apply_duration(minutes: int) -> None:
    save_settings({"SESSION_DURATION_MINUTES": minutes})
    os.environ["SESSION_DURATION_MINUTES"] = str(minutes)
    importlib.reload(config)


def run_training() -> int:
    from main import cmd_run

    problems = check_setup()
    if problems:
        print("\n  Setup noch nicht fertig:\n")
        for item in problems:
            print(f"    • {item}")
        pause()
        return 1

    minutes = pick_session_duration()
    apply_duration(minutes)
    print(f"\n  → {minutes} Minuten gewählt")
    print("  Browser öffnet sich gleich — nicht schließen.")
    print("  Stoppen: Ctrl+C\n")
    pause("  Enter zum Start…")
    return cmd_run(EmptyArgs())


def run_main_menu() -> int:
    while True:
        clear_screen()
        banner()
        show_status()

        print("  Menü:\n")
        print("    [1]  Training starten")
        print("    [2]  Bei Membean einloggen")
        print("    [3]  Einstellungen (Browser)")
        print("    [4]  KI testen")
        print("    [5]  Wortliste anzeigen")
        print("    [0]  Beenden\n")

        try:
            choice = input("  Auswahl: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nTschüss!")
            return 0

        if choice == "1":
            if run_training() != 0:
                pause()
        elif choice == "2":
            from main import cmd_login

            print("\n  Browser öffnet sich → einloggen → Dashboard → Enter hier\n")
            cmd_login(EmptyArgs())
            pause()
        elif choice == "3":
            from main import cmd_settings

            args = EmptyArgs()
            args.port = 8765  # type: ignore[attr-defined]
            args.no_browser = False  # type: ignore[attr-defined]
            cmd_settings(args)
        elif choice == "4":
            from main import cmd_test_ai

            print()
            cmd_test_ai(EmptyArgs())
            pause()
        elif choice == "5":
            if config.WORTER_PATH.exists():
                print(f"\n--- {config.WORTER_PATH.name} ---\n")
                print(config.WORTER_PATH.read_text(encoding="utf-8"))
            else:
                print("\n  Noch leer — erst Training starten.")
            pause()
        elif choice == "0":
            print("\nTschüss!")
            return 0
        else:
            print("\n  Ungültige Auswahl.")
            pause()
