#!/usr/bin/env python3
"""Membean bot — automation for Membean training sessions."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

import config
from ai_client import build_vocab_prompt
from browser import (
    get_verify_url,
    has_membean_auth_cookies,
    is_logged_in,
    launch_browser,
    load_session_meta,
    save_debug_screenshot,
    save_session,
    verify_session,
    wait_for_manual_login,
)
from session_flow import bootstrap_training_session
from extractors import extract_page
from page_detector import describe_page, detect_page_type
from runner import run_session
from settings_server import run_settings_server


def setup_logging(verbose: bool = False) -> None:
    config.LOGS_DIR.mkdir(exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOGS_DIR / "session.log", encoding="utf-8"),
        ],
    )


def cmd_setup(_: argparse.Namespace) -> int:
    print("Phase 0 — Setup check")
    print("-" * 40)
    print(f"Python:       OK ({sys.version.split()[0]})")
    print(f"Project dir:  {config.ROOT_DIR}")
    print(f"AI API URL:   {config.AI_API_URL}")
    print(f"AI model:     {config.AI_MODEL}")
    print(f"Membean URL:  {config.MEMBEAN_HOME_URL}")
    print()
    print("Next steps:")
    print("  1. Copy .env.example to .env and adjust if needed")
    print("  2. python main.py login      — save Membean session")
    print("  3. python main.py test-ai    — test LM Studio (after install)")
    print("  4. python main.py verify     — check saved session works")
    return 0


def cmd_login(_: argparse.Namespace) -> int:
    print("Phase 1 — Login & save session")
    with launch_browser() as (_, __, context):
        page = context.new_page()
        wait_for_manual_login(page)
        save_session(context, page)
    meta = load_session_meta()
    print(f"\nSession saved to: {config.STORAGE_STATE_PATH}")
    print(f"Saved URL:        {meta.get('last_url', '(unknown)')}")
    print("\nTip: Copy the training URL into .env as MEMBEAN_TRAINING_URL")
    print("Run: python main.py verify")
    return 0


def cmd_verify(_: argparse.Namespace) -> int:
    print("Phase 1 — Verify saved session")
    if not config.STORAGE_STATE_PATH.exists():
        print("No saved session found. Run: python main.py login")
        return 1

    target = get_verify_url()
    print(f"Opening: {target}")

    with launch_browser() as (_, __, context):
        page = context.new_page()
        has_cookies = has_membean_auth_cookies(context)
        print(f"Auth cookies loaded: {'yes' if has_cookies else 'no'}")

        ok = verify_session(page, context)
        if ok:
            print(f"\nSession is valid. Current page: {page.url}")
            print("Browser will stay open for 10 seconds.")
            page.wait_for_timeout(10_000)
        else:
            print("\nVerify failed.")
            print("Check screenshots/verify_failed.png if it exists.")
            print("\nTry this:")
            print("  1. python main.py login")
            print("  2. Stay on the TRAINING page before pressing Enter")
            print("  3. Optional: paste training URL into .env as MEMBEAN_TRAINING_URL")
            return 1
    return 0


def cmd_test_ai(_: argparse.Namespace) -> int:
    print("Test AI connection")
    print(f"Provider: {config.AI_PROVIDER}")
    print(f"API:      {config.AI_API_URL}")
    print(f"Model:    {config.AI_MODEL}")
    print()

    prompt = build_vocab_prompt(
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
        from ai_client import ask_ai

        letter = ask_ai(prompt)
        print(f"AI answered: {letter}")
        if letter == "a":
            print("Test passed.")
            return 0
        print("Connected, but answer unexpected (wanted 'a'). Model may need a better prompt.")
        return 0
    except Exception as exc:
        print(f"Test failed: {exc}")
        print()
        print("Checklist:")
        print("  - AI_API_KEY in .env set?")
        print("  - Groq: https://console.groq.com")
        print("  - LM Studio: AI_PROVIDER=lmstudio + local server running")
        return 1


def cmd_describe(_: argparse.Namespace) -> int:
    """Detect current page type once and print extracted data."""
    if not config.STORAGE_STATE_PATH.exists():
        print("No saved session. Run: python main.py login")
        return 1

    with launch_browser() as (_, __, context):
        page = context.new_page()
        if not verify_session(page, context):
            print("Session invalid. Run: python main.py login")
            return 1

        info = extract_page(page)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        print("\nBrowser stays open for 15 seconds — click through pages to test.")
        page.wait_for_timeout(15_000)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Watch page type changes while you click through Membean manually."""
    if not config.STORAGE_STATE_PATH.exists():
        print("No saved session. Run: python main.py login")
        return 1

    print("Phase 2 — Page watcher")
    print("Click through your Membean session. Press Ctrl+C to stop.")
    print("-" * 50)

    with launch_browser() as (_, __, context):
        page = context.new_page()
        if not verify_session(page, context):
            print("Session invalid. Run: python main.py login")
            return 1

        last_type = None
        try:
            while True:
                page.wait_for_timeout(800)
                page_type = detect_page_type(page)
                if page_type != last_type:
                    info = describe_page(page)
                    print(f"\n[{time.strftime('%H:%M:%S')}] → {page_type.upper()}")
                    print(f"  URL: {info['url']}")
                    extracted = extract_page(page)
                    data = extracted.get("data", {})
                    if data:
                        preview = json.dumps(data, ensure_ascii=False)
                        if len(preview) > 200:
                            preview = preview[:200] + "..."
                        print(f"  Data: {preview}")
                    last_type = page_type
                    if page_type == "done":
                        print("\nSession finished (10 min done). Exiting.")
                        break
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


def cmd_settings(args: argparse.Namespace) -> int:
    """Open local web UI to edit .env settings."""
    run_settings_server(port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_start(_: argparse.Namespace) -> int:
    """Interactive menu — easiest way to use the bot."""
    from user_menu import run_main_menu

    return run_main_menu()


def cmd_run(args: argparse.Namespace) -> int:
    """Full automation: dashboard → training → all page types."""
    if not config.STORAGE_STATE_PATH.exists():
        print("No saved session. Run: python main.py login")
        return 1

    if getattr(args, "minutes", None):
        from env_store import save_settings
        import importlib
        import os

        save_settings({"SESSION_DURATION_MINUTES": args.minutes})
        os.environ["SESSION_DURATION_MINUTES"] = str(args.minutes)
        importlib.reload(config)

    if getattr(args, "ask_duration", False):
        from user_menu import apply_duration, pick_session_duration

        minutes = pick_session_duration()
        apply_duration(minutes)

    print("Membean — volle Automatisierung")
    if config.AUTO_START_TRAINING:
        print(f"Start: {config.MEMBEAN_DASHBOARD_URL}")
        print(f"Dauer: {config.SESSION_DURATION_MINUTES} Minuten")
    else:
        print(f"Training URL: {get_verify_url()}")
    print()

    with launch_browser() as (_, __, context):
        page = context.new_page()
        if config.AUTO_START_TRAINING:
            page.goto(config.MEMBEAN_DASHBOARD_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            if not is_logged_in(page, context):
                print("Session ungültig. Bitte: python main.py login")
                return 1
            if not bootstrap_training_session(page):
                save_debug_screenshot(page, "bootstrap_failed")
                print("\nTraining konnte nicht automatisch starten.")
                print("Screenshot: screenshots/bootstrap_failed.png")
                print("Im Notfall manuell Start Training klicken — Bot übernimmt danach.")
                return 1
        elif not verify_session(page, context):
            print("Session invalid. Run: python main.py login")
            return 1
        try:
            run_session(page)
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Membean bot")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Interaktives Menü (empfohlen für Einsteiger)")
    sub.add_parser("setup", help="Show setup status and next steps")
    sub.add_parser("login", help="Manual login and save browser session")
    sub.add_parser("verify", help="Verify saved session still works")
    sub.add_parser("test-ai", help="Test LM Studio / local AI connection")
    sub.add_parser("describe", help="Detect current page type and extract data")
    sub.add_parser("watch", help="Watch page types while clicking manually")
    run_parser = sub.add_parser("run", help="Volle Automatisierung: Dashboard → Training → Session")
    run_parser.add_argument(
        "--minutes",
        type=int,
        choices=[5, 10, 15, 20, 25, 30],
        help="Session-Dauer in Minuten (ohne Nachfrage)",
    )
    run_parser.add_argument(
        "--ask-duration",
        action="store_true",
        help="Dauer vor Start abfragen (5–30 Min.)",
    )
    settings_parser = sub.add_parser("settings", help="Web-UI für .env Einstellungen")
    settings_parser.add_argument(
        "--port", type=int, default=8765, help="Port (Standard: 8765)"
    )
    settings_parser.add_argument(
        "--no-browser", action="store_true", help="Browser nicht automatisch öffnen"
    )

    args = parser.parse_args()
    if not args.command:
        args.command = "start"
    setup_logging(args.verbose)

    commands = {
        "start": cmd_start,
        "setup": cmd_setup,
        "login": cmd_login,
        "verify": cmd_verify,
        "test-ai": cmd_test_ai,
        "describe": cmd_describe,
        "watch": cmd_watch,
        "run": cmd_run,
        "settings": cmd_settings,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
