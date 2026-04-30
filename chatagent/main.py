# main.py - Entry point: demonstrates the full OOP system in terminal mode
# -*- coding: utf-8 -*-
"""
Run this file to start an interactive counseling session in the terminal.
It wires together all 10 OOP classes and runs the chat loop.

Usage:
    python main.py

To start the web server instead:
    python api_server.py
"""

import uuid
from dotenv import load_dotenv

from application_services import ApplicationServices
from user import User
from chat_session import ChatSession
from admin_monitor import AdminMonitor

load_dotenv()


def build_services() -> ApplicationServices:
    """Build the canonical service container shared by all entrypoints."""
    return ApplicationServices.from_env(storage_path="data", log_file="logs/session.jsonl")


def login() -> User:
    """Minimal terminal login: ask for username and role."""
    print("=" * 50)
    print("  Psychological Counseling Chat System")
    print("=" * 50)
    username = input("Username (or press Enter for 'guest'): ").strip() or "guest"
    role_input = input("Role — [1] user  [2] counselor/admin  (default: 1): ").strip()
    role = "counselor" if role_input == "2" else "user"
    user = User(user_id=str(uuid.uuid4())[:8], username=username, role=role)
    print(f"\nWelcome, {user.username}! (role: {user.role})\n")
    return user


def run_chat(user: User, session: ChatSession, monitor: AdminMonitor) -> None:
    """Main interactive loop."""
    print("Type your message and press Enter.")
    print("Commands: /reset  /show (counselors only)  /report  /quit\n")

    while True:
        try:
            raw = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not raw:
            continue

        if raw.lower() in ("/quit", "quit", "exit"):
            print("Goodbye.")
            break

        # Counselor/admin-only commands
        if raw.lower() == "/report":
            if user.can_view_report():
                print("\n[Generating counselor report...]\n")
                report = monitor.generate_report(session.session_id)
                print(report)
                print()
            else:
                print("[Permission denied] Only counselors/admins can view reports.\n")
            continue

        allow_show = user.can_view_report()
        reply = session.send_message(raw, allow_show_report=allow_show)

        if reply:
            print(f"\nAssistant: {reply}\n")
        else:
            print("[No reply generated]\n")

        user.touch()


def main() -> None:
    services = build_services()
    user = login()

    # Each user gets a persistent session tied to their user_id
    session = services.create_session(user.user_id)

    run_chat(user, session, services.monitor)


if __name__ == "__main__":
    main()
