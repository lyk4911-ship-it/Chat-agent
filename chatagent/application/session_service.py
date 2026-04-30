from typing import Any, Dict, List, Optional

from exceptions import UserNotFoundError, SessionOwnershipError
from infrastructure.runtime import RuntimeContainer
from infrastructure.user_repository import UserRepository


class SessionService:
    """Use-cases around user session management and history retrieval."""

    def __init__(self, user_repo: UserRepository, runtime: RuntimeContainer):
        self.user_repo = user_repo
        self.runtime = runtime

    def list_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        sessions = self.user_repo.list_sessions(user_id)
        if not sessions:
            raise UserNotFoundError(f"User '{user_id}' does not exist.")
        return [s.__dict__ for s in sessions]

    def create_session(self, user_id: str, title: Optional[str] = None) -> str:
        if not self.user_repo.get_user(user_id):
            raise UserNotFoundError(f"User '{user_id}' does not exist.")
        return self.user_repo.create_session(user_id, title=title)

    def session_history(
        self, user_id: str, session_id: str, limit_turns: int = 80
    ) -> Dict[str, Any]:
        if not self.user_repo.get_user(user_id):
            raise UserNotFoundError(f"User '{user_id}' does not exist.")
        if not self.user_repo.owns_session(user_id, session_id):
            raise SessionOwnershipError(
                f"Session '{session_id}' does not belong to user '{user_id}'."
            )
        session = self.runtime.get_or_create_session(session_id)
        logs = self.runtime.get_logs(session_id=session_id, limit=limit_turns)
        history: List[Dict[str, Any]] = []
        for rec in logs:
            user_text  = (rec.get("user")  or "").strip()
            reply_text = (rec.get("reply") or "").strip()
            if user_text:
                history.append({"role": "user",      "content": user_text,  "ts": rec.get("ts")})
            if reply_text:
                history.append({"role": "assistant", "content": reply_text, "ts": rec.get("ts")})
        return {
            "session_id": session_id,
            "state": session.state.to_dict(),
            "history": history,
        }
