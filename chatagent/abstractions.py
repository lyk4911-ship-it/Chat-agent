# abstractions.py - Abstract base classes (interfaces) for MindChat's core services
# -*- coding: utf-8 -*-
"""
Defines the four abstract interfaces that form the backbone of the system:

    BaseUser       — shared identity contract for User and UserAccount
    BaseStorage    — persistence interface (load/save JSON + sessions)
    BaseLogger     — conversation logging interface
    BaseApiClient  — LLM API communication interface

Concrete classes inherit these ABCs, making them substitutable for testing
(mock implementations) and future backend swaps (e.g. swap file storage for
a database) without changing any caller code — Open/Closed Principle.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional


# ══════════════════════════════════════════════════════════════════════════════
#  BaseUser
# ══════════════════════════════════════════════════════════════════════════════

class BaseUser(ABC):
    """
    Abstract identity shared by the lightweight ``User`` (role/permission
    model) and the persistent ``UserAccount`` (password-hash model).

    Any component that needs to identify a caller can accept a ``BaseUser``
    and remain agnostic about whether it has a stored password or not.

    Contract: every concrete subclass MUST expose ``user_id: str`` and
    ``username: str`` attributes (either as instance variables or properties).
    """

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialise user data to a plain dictionary."""

    def __str__(self) -> str:
        uid  = getattr(self, "user_id",  "?")
        name = getattr(self, "username", "?")
        return f"{self.__class__.__name__}(id={uid!r}, username={name!r})"


# ══════════════════════════════════════════════════════════════════════════════
#  BaseStorage
# ══════════════════════════════════════════════════════════════════════════════

class BaseStorage(ABC):
    """
    Abstract persistence interface.

    ``StorageManager`` is the file-backed implementation.  An in-memory
    variant (useful for unit-testing without touching the filesystem) only
    needs to implement these five methods.
    """

    @abstractmethod
    def load_json(self, path: str, default: Any = None) -> Any:
        """Load and return JSON data from *path*; return *default* on error."""

    @abstractmethod
    def save_json(self, path: str, data: Any) -> None:
        """Serialise *data* to JSON and persist it at *path*."""

    @abstractmethod
    def save_session(self, session_state) -> None:
        """Persist a ``SessionState`` object to durable storage."""

    @abstractmethod
    def load_session(self, session_id: str):
        """Restore a ``SessionState`` from storage. Returns ``None`` if absent."""

    @abstractmethod
    def list_sessions(self) -> List[str]:
        """Return the IDs of all persisted sessions."""

    def __str__(self) -> str:
        return f"{self.__class__.__name__}()"

    def __repr__(self) -> str:
        return self.__str__()


# ══════════════════════════════════════════════════════════════════════════════
#  BaseLogger
# ══════════════════════════════════════════════════════════════════════════════

class BaseLogger(ABC):
    """
    Abstract logging interface.

    Decouples the chat engine from the concrete log format (JSONL file,
    database, in-memory list for tests, …).
    """

    @abstractmethod
    def log_turn(self, user_text: str, reply: str, state) -> None:
        """Append a complete user → assistant turn to the log."""

    @abstractmethod
    def get_logs(
        self,
        session_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Return recent log records.

        If *session_id* is given only records for that session are included.
        At most *limit* records are returned (newest first).
        """

    @abstractmethod
    def __len__(self) -> int:
        """Return the total number of log records in the backing store."""

    @abstractmethod
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over all log records in chronological order."""

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(records={len(self)})"

    def __repr__(self) -> str:
        return self.__str__()


# ══════════════════════════════════════════════════════════════════════════════
#  BaseApiClient
# ══════════════════════════════════════════════════════════════════════════════

class BaseApiClient(ABC):
    """
    Abstract LLM API interface.

    Concrete implementations may target DeepSeek, OpenAI, a local LLM, or
    a deterministic stub for testing — all are drop-in replacements.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the backend API endpoint is reachable."""

    @abstractmethod
    def send_request(
        self,
        messages: List[dict],
        temperature: float = 0.6,
        max_tokens: int = 300,
    ) -> str:
        """
        Send a chat-completion request and return the assistant's reply text.

        On failure returns a string prefixed with ``'[ERR'`` rather than
        raising, so callers never need to guard against API exceptions in
        normal conversation flow.
        """

    def __str__(self) -> str:
        return f"{self.__class__.__name__}()"

    def __repr__(self) -> str:
        return self.__str__()
