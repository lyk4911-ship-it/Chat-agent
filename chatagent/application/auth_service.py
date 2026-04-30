from typing import Any, Dict

from exceptions import UserAlreadyExistsError, UserNotFoundError, PasswordError
from infrastructure.user_repository import UserRepository


class AuthService:
    """
    Use-cases for user registration and login.

    Validates input, delegates persistence to ``UserRepository``, and raises
    domain-specific exceptions (``UserAlreadyExistsError``, ``UserNotFoundError``,
    ``PasswordError``) so callers can catch at any level of granularity.
    Each custom exception also inherits the corresponding built-in type so
    existing HTTP route handlers require no changes.
    """

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def register(self, username: str, password: str) -> Dict[str, Any]:
        if len(username.strip()) < 2:
            raise ValueError("Username must be at least 2 characters.")
        if len(password.strip()) < 4:
            raise ValueError("Password must be at least 4 characters.")
        return self.user_repo.register(
            username=username.strip(),
            password=password.strip(),
        )

    def login(self, username: str, password: str) -> Dict[str, Any]:
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise ValueError("Username and password must not be empty.")
        return self.user_repo.login(username=username, password=password)
