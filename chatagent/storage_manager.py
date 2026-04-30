# storage_manager.py - StorageManager class for persistent local storage
# -*- coding: utf-8 -*-

import json
import os
from typing import Any, Dict, List, Optional

from abstractions import BaseStorage
from session_state import SessionState


class StorageManager(BaseStorage):
    """
    File-backed implementation of ``BaseStorage``.

    Manages persistent local storage for sessions and data files using JSON.
    Atomic writes (write-to-temp then os.replace) prevent data corruption on
    crash.

    OOP features demonstrated:
      • Inheritance    : implements the ``BaseStorage`` abstract interface
      • __str__        : shows storage path and session count
      • __repr__       : programmer-facing format
      • __len__        : ``len(storage)`` → number of persisted sessions
      • __contains__   : ``session_id in storage`` → membership test
    """

    def __init__(self, storage_path: str = "data"):
        self.storage_path: str = storage_path
        os.makedirs(storage_path, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Magic methods
    # ──────────────────────────────────────────────────────────────────────────

    def __str__(self) -> str:
        """Human-readable summary: path and session count."""
        return (
            f"StorageManager(path={self.storage_path!r}, "
            f"sessions={len(self)})"
        )

    def __repr__(self) -> str:
        return f"StorageManager(storage_path={self.storage_path!r})"

    def __len__(self) -> int:
        """Return the number of persisted session files."""
        return len(self.list_sessions())

    def __contains__(self, session_id: object) -> bool:
        """
        Membership test: ``session_id in storage``.

        Returns ``True`` if a session file exists for *session_id*.
        """
        if not isinstance(session_id, str):
            return False
        path = os.path.join(self.storage_path, "sessions", f"{session_id}.json")
        return os.path.isfile(path)

    # ──────────────────────────────────────────────────────────────────────────
    # BaseStorage — generic JSON helpers
    # ──────────────────────────────────────────────────────────────────────────

    def load_json(self, path: str, default: Any = None) -> Any:
        """Load a JSON file, returning *default* if missing or malformed."""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return default
        return default

    def save_json(self, path: str, data: Any) -> None:
        """Atomically persist *data* as JSON to *path*."""
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".",
            exist_ok=True,
        )
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    # ──────────────────────────────────────────────────────────────────────────
    # BaseStorage — session persistence
    # ──────────────────────────────────────────────────────────────────────────

    def save_session(self, session_state: SessionState) -> None:
        """Persist a ``SessionState`` under ``storage_path/sessions/``."""
        path = os.path.join(
            self.storage_path, "sessions",
            f"{session_state.session_id}.json",
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.save_json(path, session_state.to_dict())

    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load a ``SessionState`` from disk. Returns ``None`` if not found."""
        path = os.path.join(self.storage_path, "sessions", f"{session_id}.json")
        data = self.load_json(path)
        if data:
            return SessionState.from_dict(data)
        return None

    def list_sessions(self) -> List[str]:
        """Return a list of all saved session IDs."""
        d = os.path.join(self.storage_path, "sessions")
        if not os.path.isdir(d):
            return []
        return [f[:-5] for f in os.listdir(d) if f.endswith(".json")]

    # ──────────────────────────────────────────────────────────────────────────
    # Strategy / analysis library loading
    # ──────────────────────────────────────────────────────────────────────────

    def load_strategies(self, path: str = "strategies_en.json") -> List[Dict[str, Any]]:
        """Load the intervention strategy library from a JSON file."""
        result = self.load_json(path, [])
        if not isinstance(result, list) or not result:
            result = self.load_json("strategies.json", [])
        return result if isinstance(result, list) else []

    def load_analysis_lib(self, path: str = "analysis_library.json") -> Dict[str, Any]:
        """Load the psychological analysis library from a JSON file."""
        result = self.load_json(path, {})
        if not isinstance(result, dict) or not result:
            legacy_name = "\u60c5\u611f\u5206\u6790\u5e93.json"
            result = self.load_json(legacy_name, {})
        return result if isinstance(result, dict) else {}
