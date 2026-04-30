# log_manager.py - LogManager class for logging conversation turns
# -*- coding: utf-8 -*-

import datetime as dt
import json
import os
from typing import Any, Dict, Iterator, List, Optional

from abstractions import BaseLogger
from message import Message
from session_state import SessionState


class LogManager(BaseLogger):
    """
    JSONL file-backed implementation of ``BaseLogger``.

    Appends one JSON object per line to a ``.jsonl`` file.  Each record
    carries at least ``ts``, ``session_id``, and the relevant payload.

    OOP features demonstrated:
      • Inheritance  : implements the ``BaseLogger`` abstract interface
      • __str__      : shows log file path and total record count
      • __repr__     : programmer-facing format
      • __len__      : ``len(log_manager)`` → total records on disk
      • __iter__     : ``for record in log_manager`` → chronological iteration
    """

    def __init__(self, log_file: str = "logs/session.jsonl"):
        self.log_file: str = log_file
        os.makedirs(
            os.path.dirname(log_file) if os.path.dirname(log_file) else ".",
            exist_ok=True,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Magic methods
    # ──────────────────────────────────────────────────────────────────────────

    def __str__(self) -> str:
        """Human-readable summary: log file path and total record count."""
        return f"LogManager(file={self.log_file!r}, records={len(self)})"

    def __repr__(self) -> str:
        return f"LogManager(log_file={self.log_file!r})"

    def __len__(self) -> int:
        """Return the total number of valid log records in the backing file."""
        if not os.path.exists(self.log_file):
            return 0
        count = 0
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        json.loads(line)
                        count += 1
                    except Exception:
                        pass
        return count

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """
        Iterate over all log records in chronological order.

        Yields each record as a plain dict.  Malformed lines are skipped.
        """
        if not os.path.exists(self.log_file):
            return
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    # ──────────────────────────────────────────────────────────────────────────
    # BaseLogger — logging methods
    # ──────────────────────────────────────────────────────────────────────────

    def log_message(self, message: Message,
                    state_snapshot: Optional[Dict] = None) -> None:
        """Append a single message (plus optional state snapshot) to the log."""
        record: Dict[str, Any] = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "session_id": message.session_id,
            "sender": message.sender,
            "content": message.content,
        }
        if state_snapshot is not None:
            record["state"] = state_snapshot
        self._append(record)

    def log_state_update(self, state: SessionState) -> None:
        """Log a state-update event (e.g. after profile extraction)."""
        record: Dict[str, Any] = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "event": "state_update",
            "session_id": state.session_id,
            "state": state.to_dict(),
        }
        self._append(record)

    def log_turn(self, user_text: str, reply: str, state: SessionState) -> None:
        """Convenience: log a complete user → assistant turn."""
        record: Dict[str, Any] = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "session_id": state.session_id,
            "user": user_text,
            "reply": reply,
            "state": state.to_dict(),
        }
        self._append(record)

    def get_logs(
        self,
        session_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Return recent log records.

        If *session_id* is given, only records for that session are included.
        At most *limit* records are returned (the most recent ones).
        """
        if not os.path.exists(self.log_file):
            return []
        records: List[Dict[str, Any]] = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if session_id is None or rec.get("session_id") == session_id:
                        records.append(rec)
                except Exception:
                    continue
        return records[-limit:]

    # ──────────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────────

    def _append(self, record: Dict[str, Any]) -> None:
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
