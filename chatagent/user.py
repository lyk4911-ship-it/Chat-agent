# user.py - User class for user identity and permission management
# -*- coding: utf-8 -*-

import datetime as dt
from typing import Optional

from abstractions import BaseUser
from exceptions import InvalidStateError

_VALID_ROLES: frozenset = frozenset({"user", "admin", "counselor"})


class User(BaseUser):
    """
    Represents an authenticated user of the counseling system.

    Stores identity information and access permissions.  Inherits from
    ``BaseUser`` (abstract interface) so that any component accepting a
    ``BaseUser`` can also accept a plain ``User`` without knowing about
    the heavier ``UserAccount`` (password-hash) variant.

    OOP features demonstrated:
      • Inheritance    : extends ``BaseUser`` ABC, implements abstract contract
      • @property      : ``role`` setter validates against allowed values
      • Encapsulation  : ``_role`` backing store; external code uses property
      • __str__        : concise display-friendly format
      • __repr__       : unambiguous programmer format
      • __eq__         : entity equality (same user_id → same user)
      • __hash__       : consistent with __eq__
    """

    def __init__(self, user_id: str, username: str, role: str = "user"):
        self._user_id: str = user_id
        self._username: str = username
        self._role: str = "user"          # set via property for validation
        self.role = role                  # calls setter
        self.created_at: str = dt.datetime.now().isoformat(timespec="seconds")
        self.last_active: Optional[str] = None

    # ──────────────────────────────────────────────────────────────────────────
    # BaseUser contract — expose user_id and username as properties
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def user_id(self) -> str:
        """Unique user identifier (read-only after construction)."""
        return self._user_id

    @property
    def username(self) -> str:
        """Display name (read-only after construction)."""
        return self._username

    # ──────────────────────────────────────────────────────────────────────────
    # Validated property
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def role(self) -> str:
        """User role: ``"user"`` | ``"admin"`` | ``"counselor"``."""
        return self._role

    @role.setter
    def role(self, value: str) -> None:
        if value not in _VALID_ROLES:
            raise InvalidStateError(
                f"role must be one of {sorted(_VALID_ROLES)}, got {value!r}"
            )
        self._role = value

    # ──────────────────────────────────────────────────────────────────────────
    # Permission helpers
    # ──────────────────────────────────────────────────────────────────────────

    def is_admin(self) -> bool:
        """Return ``True`` if the user has admin or counselor privileges."""
        return self._role in ("admin", "counselor")

    def can_view_report(self) -> bool:
        """Only admins and counselors may access the /show report endpoint."""
        return self.is_admin()

    def touch(self) -> None:
        """Update the last-active timestamp to now."""
        self.last_active = dt.datetime.now().isoformat(timespec="seconds")

    # ──────────────────────────────────────────────────────────────────────────
    # Magic methods
    # ──────────────────────────────────────────────────────────────────────────

    def __str__(self) -> str:
        """Human-readable display: ``username (role)``."""
        return f"{self._username} ({self._role})"

    def __repr__(self) -> str:
        return f"User(id={self._user_id!r}, role={self._role!r})"

    def __eq__(self, other: object) -> bool:
        """
        Entity equality: two ``User`` objects refer to the same person when
        their ``user_id`` values match, regardless of mutable fields like role.
        """
        if not isinstance(other, User):
            return NotImplemented
        return self._user_id == other._user_id

    def __hash__(self) -> int:
        """Hash by ``user_id`` so users can be stored in sets / dict keys."""
        return hash(self._user_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Serialisation (BaseUser contract)
    # ──────────────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "role": self._role,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }

    @staticmethod
    def from_dict(data: dict) -> "User":
        u = User(
            user_id=data.get("user_id", ""),
            username=data.get("username", ""),
            role=data.get("role", "user"),
        )
        u.created_at = data.get("created_at", u.created_at)
        u.last_active = data.get("last_active")
        return u
