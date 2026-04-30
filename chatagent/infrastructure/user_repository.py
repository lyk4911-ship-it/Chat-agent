import datetime as dt
import os
import uuid
from typing import Any, Dict, List, Optional

from domain.user import UserAccount
from domain.session import SessionMeta
from exceptions import UserAlreadyExistsError, UserNotFoundError, PasswordError
from storage_manager import StorageManager


class UserRepository:
    """Persistent user/session metadata repository backed by JSON."""

    def __init__(self, storage: StorageManager, user_index_file: str = os.path.join("data", "users.json")):
        self.storage = storage
        self.user_index_file = user_index_file

    @staticmethod
    def _now_iso() -> str:
        return dt.datetime.now().isoformat(timespec="seconds")

    def _load_index(self) -> Dict[str, Any]:
        data = self.storage.load_json(
            self.user_index_file,
            default={"by_username": {}, "users": {}},
        )
        if not isinstance(data, dict):
            return {"by_username": {}, "users": {}}
        if not isinstance(data.get("by_username"), dict):
            data["by_username"] = {}
        if not isinstance(data.get("users"), dict):
            data["users"] = {}
        return data

    def _save_index(self, index_data: Dict[str, Any]) -> None:
        self.storage.save_json(self.user_index_file, index_data)

    def _ensure_sessions(self, user_record: Dict[str, Any]) -> List[Dict[str, Any]]:
        sessions = user_record.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
            user_record["sessions"] = sessions
        cleaned: List[Dict[str, Any]] = []
        for row in sessions:
            if not isinstance(row, dict):
                continue
            session_id = (row.get("session_id") or "").strip()
            if not session_id:
                continue
            cleaned.append({
                "session_id": session_id,
                "title": (row.get("title") or "New conversation").strip() or "New conversation",
                "created_at": row.get("created_at") or self._now_iso(),
                "updated_at": row.get("updated_at") or row.get("created_at") or self._now_iso(),
            })
        user_record["sessions"] = cleaned
        return cleaned

    def _to_session_meta(self, rows: List[Dict[str, Any]]) -> List[SessionMeta]:
        ordered = sorted(rows, key=lambda item: item.get("updated_at") or "", reverse=True)
        return [SessionMeta(**row) for row in ordered]

    def _get_user_record_by_username(self, index_data: Dict[str, Any], username: str) -> Optional[Dict[str, Any]]:
        user_id = index_data.get("by_username", {}).get(username.lower())
        if not isinstance(user_id, str):
            return None
        user = index_data.get("users", {}).get(user_id)
        if not isinstance(user, dict):
            return None
        self._ensure_sessions(user)
        return user

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        index_data = self._load_index()
        user = index_data.get("users", {}).get(user_id)
        if not isinstance(user, dict):
            return None
        self._ensure_sessions(user)
        return user

    def register(self, username: str, password: str) -> Dict[str, Any]:
        index_data = self._load_index()
        if self._get_user_record_by_username(index_data, username):
            raise UserAlreadyExistsError("用户已存在，请换一个用户名。")

        now = self._now_iso()
        user_id = str(uuid.uuid4())[:8]
        first_session_id = f"user-{user_id}-{str(uuid.uuid4())[:8]}"
        salt = str(uuid.uuid4())
        account = UserAccount(
            user_id=user_id,
            username=username,
            password_salt=salt,
            password_hash=UserAccount.hash_password(password, salt),
        )
        record = {
            "user_id": account.user_id,
            "username": account.username,
            "password_salt": account.password_salt,
            "password_hash": account.password_hash,
            "created_at": now,
            "last_login": now,
            "sessions": [{
                "session_id": first_session_id,
                "title": "New conversation",
                "created_at": now,
                "updated_at": now,
            }],
        }
        index_data["users"][user_id] = record
        index_data["by_username"][username.lower()] = user_id
        self._save_index(index_data)
        return record

    def login(self, username: str, password: str) -> Dict[str, Any]:
        index_data = self._load_index()
        record = self._get_user_record_by_username(index_data, username)
        if record is None:
            raise UserNotFoundError("用户不存在，请先注册。")
        account = UserAccount(
            user_id=record.get("user_id") or "",
            username=record.get("username") or username,
            password_salt=record.get("password_salt") or "",
            password_hash=record.get("password_hash") or "",
        )
        if not account.password_hash:
            raise ValueError("该用户尚未初始化密码，请注册新用户。")
        if not account.verify_password(password):
            raise PasswordError("用户名或密码错误。")

        record["last_login"] = self._now_iso()
        sessions = self._ensure_sessions(record)
        if not sessions:
            sid = f"user-{account.user_id}-{str(uuid.uuid4())[:8]}"
            self.touch_session(account.user_id, sid)
            index_data = self._load_index()
            record = index_data["users"][account.user_id]
        self._save_index(index_data)
        return record

    def list_sessions(self, user_id: str) -> List[SessionMeta]:
        user = self.get_user(user_id)
        if not user:
            return []
        return self._to_session_meta(self._ensure_sessions(user))

    def owns_session(self, user_id: str, session_id: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        sessions = self._ensure_sessions(user)
        return any(item.get("session_id") == session_id for item in sessions)

    def touch_session(self, user_id: str, session_id: str, latest_user_text: str = "", title: Optional[str] = None) -> None:
        index_data = self._load_index()
        user = index_data.get("users", {}).get(user_id)
        if not isinstance(user, dict):
            return
        sessions = self._ensure_sessions(user)
        now = self._now_iso()
        row = None
        for item in sessions:
            if item["session_id"] == session_id:
                row = item
                break
        if row is None:
            row = {
                "session_id": session_id,
                "title": "New conversation",
                "created_at": now,
                "updated_at": now,
            }
            sessions.append(row)

        custom_title = (title or "").strip()
        if custom_title:
            row["title"] = custom_title[:48]
        user_text = (latest_user_text or "").strip()
        if user_text and row.get("title", "New conversation") == "New conversation":
            row["title"] = user_text[:36]
        row["updated_at"] = now
        user["sessions"] = sorted(sessions, key=lambda item: item.get("updated_at") or "", reverse=True)
        self._save_index(index_data)

    def create_session(self, user_id: str, title: Optional[str] = None) -> str:
        session_id = f"user-{user_id}-{str(uuid.uuid4())[:8]}"
        self.touch_session(user_id, session_id, title=title)
        return session_id

