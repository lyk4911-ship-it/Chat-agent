import os
from collections import OrderedDict
from typing import Optional

from admin_monitor import AdminMonitor
from api_client import ApiClient
from chat_session import ChatSession
from log_manager import LogManager
from storage_manager import StorageManager

try:
    from agent_rules import ConversationPolicy
except ImportError:
    ConversationPolicy = None


class ApplicationServices:
    """Container for shared service objects used by every entrypoint."""

    def __init__(
        self,
        api_client: ApiClient,
        storage: StorageManager,
        log_manager: LogManager,
        monitor: AdminMonitor,
        policy: Optional["ConversationPolicy"] = None,
    ):
        self.api_client = api_client
        self.storage = storage
        self.log_manager = log_manager
        self.monitor = monitor
        self.policy = policy

    @classmethod
    def from_env(
        cls,
        storage_path: str = "data",
        log_file: str = "logs/session.jsonl",
    ) -> "ApplicationServices":
        """Build the canonical object graph for the OOP application."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
        model = os.getenv("OPENAI_MODEL") or "deepseek-chat"

        api_client = ApiClient(api_key=api_key, endpoint=base_url, model=model)
        storage = StorageManager(storage_path=storage_path)
        log_manager = LogManager(log_file=log_file)
        monitor = AdminMonitor(api_client, storage, log_manager)
        policy = ConversationPolicy() if ConversationPolicy is not None else None
        return cls(api_client, storage, log_manager, monitor, policy)

    def create_session(self, session_id: str) -> ChatSession:
        """Create a session wired to the shared service graph."""
        return ChatSession(
            session_id=session_id,
            api_client=self.api_client,
            storage=self.storage,
            log_manager=self.log_manager,
            policy=self.policy,
        )


class ChatSessionRegistry:
    """LRU-backed manager for API-owned chat sessions."""

    def __init__(self, services: ApplicationServices, max_sessions: int = 100):
        self.services = services
        self.max_sessions = max_sessions
        self._sessions: OrderedDict[str, ChatSession] = OrderedDict()

    def get_or_create(self, session_id: str) -> ChatSession:
        """Return a cached ChatSession or create one through the service container."""
        if session_id in self._sessions:
            self._sessions.move_to_end(session_id)
            return self._sessions[session_id]

        session = self.services.create_session(session_id)
        self._sessions[session_id] = session
        self._sessions.move_to_end(session_id)
        if len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)
        return session

    def reset(self, session_id: str) -> None:
        """Reset a managed session if it exists."""
        if session_id in self._sessions:
            self._sessions[session_id].reset()
