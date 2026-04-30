# exceptions.py - Custom exception hierarchy for MindChat
# -*- coding: utf-8 -*-
"""
Structured exception tree so callers can catch at any level of specificity.

Each custom exception also inherits its corresponding built-in type so that
existing route-level handlers (which catch ValueError / LookupError /
PermissionError) continue to work unchanged.
"""


class ChatBotError(Exception):
    """Root exception for all application-level errors."""

    def __init__(self, message: str = "", code: str = ""):
        super().__init__(message)
        self.code = code

    def __str__(self) -> str:
        base = super().__str__()
        # Use getattr: subclasses that inherit a built-in first (e.g.
        # UserNotFoundError(LookupError, AuthError)) may have their __init__
        # resolved to the built-in's, which skips setting self.code.
        code = getattr(self, "code", "")
        return f"[{code}] {base}" if code else base

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"


# ── Authentication / authorisation ────────────────────────────────────────

class AuthError(ChatBotError):
    """Base class for all authentication and authorisation failures."""


class UserAlreadyExistsError(ValueError, AuthError):
    """Raised when registering a username that is already taken."""


class UserNotFoundError(LookupError, AuthError):
    """Raised when a requested user account does not exist."""


class PasswordError(PermissionError, AuthError):
    """Raised when the supplied password does not match the stored hash."""


# ── Session management ─────────────────────────────────────────────────────

class SessionError(ChatBotError):
    """Base class for all session-related errors."""


class SessionNotFoundError(LookupError, SessionError):
    """Raised when a session_id is not found in storage or the registry."""


class SessionOwnershipError(PermissionError, SessionError):
    """Raised when a user attempts to access a session they do not own."""


# ── Domain / state validation ──────────────────────────────────────────────

class InvalidStateError(ValueError, ChatBotError):
    """Raised when a domain field receives a value outside its allowed set."""


# ── Persistence ────────────────────────────────────────────────────────────

class StorageError(IOError, ChatBotError):
    """Raised when a persistence read/write operation fails unexpectedly."""


# ── API communication ──────────────────────────────────────────────────────

class ApiError(RuntimeError, ChatBotError):
    """Base class for errors returned by the LLM API."""


class RateLimitError(ApiError):
    """Raised when the LLM API returns HTTP 429 (Too Many Requests)."""
