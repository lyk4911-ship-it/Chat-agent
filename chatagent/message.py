# message.py - Message class representing a single chat message
# -*- coding: utf-8 -*-

import datetime as dt
from typing import Optional


class Message:
    """
    Represents a single message in a conversation (value object).

    As a value object, two messages are considered equal when every field
    matches — making ``Message`` safe to use in sets and as dict keys.

    OOP features demonstrated:
      • Encapsulation  : all fields set at construction; immutable after creation
      • __str__        : concise human-readable format (role: content)
      • __repr__       : unambiguous programmer format for debugging
      • __eq__         : value equality (all fields compared)
      • __hash__       : consistent with __eq__ so messages work in sets/dicts
      • __lt__         : chronological ordering by timestamp (enables sort())
    """

    def __init__(self, session_id: str, sender: str, content: str,
                 timestamp: Optional[str] = None):
        self.session_id: str = session_id
        self.sender: str = sender          # "user" or "assistant"
        self.content: str = content
        self.timestamp: str = (
            timestamp
            if timestamp is not None
            else dt.datetime.now().isoformat(timespec="seconds")
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Magic methods
    # ──────────────────────────────────────────────────────────────────────────

    def __str__(self) -> str:
        """Human-readable one-liner: ``[role] content (truncated to 60 chars)``."""
        preview = self.content if len(self.content) <= 60 else self.content[:57] + "..."
        return f"[{self.sender}] {preview}"

    def __repr__(self) -> str:
        return (
            f"Message(sender={self.sender!r}, "
            f"content={self.content[:30]!r}, "
            f"ts={self.timestamp!r})"
        )

    def __eq__(self, other: object) -> bool:
        """
        Value equality: two messages are identical when every field matches.
        This distinguishes ``Message`` (value object) from ``SessionState``
        (entity, compared only by ID).
        """
        if not isinstance(other, Message):
            return NotImplemented
        return (
            self.session_id == other.session_id
            and self.sender == other.sender
            and self.content == other.content
            and self.timestamp == other.timestamp
        )

    def __hash__(self) -> int:
        """Hash all fields so equal messages produce the same hash."""
        return hash((self.session_id, self.sender, self.content, self.timestamp))

    def __lt__(self, other: "Message") -> bool:
        """
        Chronological ordering by timestamp.
        Allows ``sorted(messages)`` to return messages in send order.
        """
        if not isinstance(other, Message):
            return NotImplemented
        return self.timestamp < other.timestamp

    def __le__(self, other: "Message") -> bool:
        if not isinstance(other, Message):
            return NotImplemented
        return self.timestamp <= other.timestamp

    # ──────────────────────────────────────────────────────────────────────────
    # Serialisation
    # ──────────────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise message to dictionary for storage / API use."""
        return {
            "role": self.sender,
            "content": self.content,
            "session_id": self.session_id,
            "ts": self.timestamp,
        }

    @staticmethod
    def from_dict(data: dict) -> "Message":
        """Deserialise a message from a dictionary."""
        return Message(
            session_id=data.get("session_id", ""),
            sender=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("ts"),
        )
