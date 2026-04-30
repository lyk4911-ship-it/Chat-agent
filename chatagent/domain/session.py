from dataclasses import dataclass


@dataclass
class SessionMeta:
    """
    Value object representing session metadata (title, timestamps).

    As a dataclass ``@dataclass`` provides ``__init__`` and ``__repr__``
    automatically.  We add the remaining magic methods required for
    sorting, display, and set membership.

    OOP features demonstrated:
      • @dataclass     : auto-generated __init__, __repr__, __eq__, __hash__
                         (frozen=False keeps mutability; eq=True gives __eq__)
      • __str__        : concise human-readable one-liner
      • __lt__ / __le__: chronological ordering by updated_at so sorted()
                         returns sessions newest-first
    """

    session_id: str
    title: str
    created_at: str
    updated_at: str

    def __str__(self) -> str:
        """Concise one-liner: title and last-updated time."""
        return f"[{self.session_id[:8]}] {self.title!r} (updated {self.updated_at})"

    def __lt__(self, other: "SessionMeta") -> bool:
        """
        Chronological ordering: older sessions compare less than newer ones.
        ``sorted(sessions)`` therefore returns oldest-first.
        Use ``sorted(sessions, reverse=True)`` for newest-first.
        """
        if not isinstance(other, SessionMeta):
            return NotImplemented
        return self.updated_at < other.updated_at

    def __le__(self, other: "SessionMeta") -> bool:
        if not isinstance(other, SessionMeta):
            return NotImplemented
        return self.updated_at <= other.updated_at

    def __gt__(self, other: "SessionMeta") -> bool:
        if not isinstance(other, SessionMeta):
            return NotImplemented
        return self.updated_at > other.updated_at

    def __ge__(self, other: "SessionMeta") -> bool:
        if not isinstance(other, SessionMeta):
            return NotImplemented
        return self.updated_at >= other.updated_at
