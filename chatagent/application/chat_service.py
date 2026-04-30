import datetime as dt
from typing import Any, Dict, Optional

from exceptions import UserNotFoundError, SessionOwnershipError
from infrastructure.runtime import RuntimeContainer
from infrastructure.user_repository import UserRepository


class ChatService:
    """
    Core chat orchestration use-case.

    Validates ownership, delegates to the session engine, and raises
    domain-specific exceptions on access violations.
    """

    PROACTIVE_MARKER = "__PROACTIVE__"

    def __init__(
        self,
        runtime: RuntimeContainer,
        user_repo: UserRepository,
        tester_token: str = "",
    ):
        self.runtime = runtime
        self.user_repo = user_repo
        self.tester_token = (tester_token or "").strip()

    @staticmethod
    def now_iso() -> str:
        return dt.datetime.now().isoformat(timespec="seconds")

    def _allow_show(
        self, allow_show_report: bool, tester_token: Optional[str]
    ) -> bool:
        if not allow_show_report:
            return False
        if not self.tester_token:
            return True
        return (tester_token or "").strip() == self.tester_token

    def send(
        self,
        text: str,
        session_id: str,
        user_id: Optional[str] = None,
        proactive_ping: bool = False,
        allow_show_report: bool = False,
        tester_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        session_id = (session_id or "").strip()
        if not session_id:
            raise ValueError("session_id must not be empty.")

        uid = (user_id or "").strip()
        if uid:
            if not self.user_repo.get_user(uid):
                raise UserNotFoundError(f"User '{uid}' does not exist.")
            if not self.user_repo.owns_session(uid, session_id):
                raise SessionOwnershipError(
                    f"Session '{session_id}' does not belong to user '{uid}'."
                )

        session = self.runtime.get_or_create_session(session_id)
        user_text = self.PROACTIVE_MARKER if proactive_ping else (text or "")
        reply = session.send_message(
            user_text,
            allow_show_report=self._allow_show(allow_show_report, tester_token),
        )

        if uid:
            self.user_repo.touch_session(
                uid, session_id, latest_user_text=(text or "")
            )

        return {
            "reply": reply,
            "state": session.state.to_dict(),
            "session_id": session_id,
            "reply_ts": self.now_iso(),
            "proactive_skipped": bool(proactive_ping and not reply),
        }
