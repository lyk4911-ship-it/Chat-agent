import hashlib
import hmac
import sys
import os
from dataclasses import dataclass

# Allow import of abstractions from the chatagent root directory
_root = os.path.dirname(os.path.dirname(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from abstractions import BaseUser


@dataclass
class UserAccount(BaseUser):
    """
    Persistent user identity with salted SHA-256 password hashing.

    Extends ``BaseUser`` (abstract interface) and uses Python's ``@dataclass``
    decorator for clean field declaration and auto-generated ``__init__`` and
    ``__eq__`` (field-by-field value comparison).

    OOP features demonstrated:
      • Inheritance    : implements ``BaseUser`` (abstract base class)
      • @dataclass     : auto __init__ and __repr__ from field declarations
      • __post_init__  : constructor-time validation (non-empty id/username)
      • __str__        : human-readable — password fields are NEVER exposed
      • __hash__       : entity identity keyed on user_id
      • Static methods : stateless helpers that operate only on their arguments
    """

    user_id: str
    username: str
    password_salt: str
    password_hash: str

    def __post_init__(self) -> None:
        """Validate fields immediately after dataclass construction."""
        if not self.user_id.strip():
            raise ValueError("UserAccount.user_id must not be empty.")
        if not self.username.strip():
            raise ValueError("UserAccount.username must not be empty.")

    # ── Magic methods ──────────────────────────────────────────────────────

    def __str__(self) -> str:
        """Human-readable summary — credential fields are never exposed."""
        return f"UserAccount(id={self.user_id!r}, username={self.username!r})"

    def __hash__(self) -> int:
        """Entity hash: two accounts with the same user_id are the same user."""
        return hash(self.user_id)

    # ── Password helpers ───────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """Return the SHA-256 hex digest of ``salt:password``."""
        payload = f"{salt}:{password}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Return ``True`` if *password* matches the stored hash."""
        candidate = self.hash_password(password, self.password_salt)
        return hmac.compare_digest(candidate, self.password_hash or "")

    # ── BaseUser abstract method implementation ────────────────────────────

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary (includes hashed credential fields)."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "password_salt": self.password_salt,
            "password_hash": self.password_hash,
        }
