import os
from dataclasses import dataclass

from application.auth_service import AuthService
from application.chat_service import ChatService
from application.monitor_service import MonitorService
from application.session_service import SessionService
from infrastructure.runtime import RuntimeContainer
from infrastructure.user_repository import UserRepository
from storage_manager import StorageManager


@dataclass
class AppContext:
    runtime: RuntimeContainer
    user_repo: UserRepository
    auth_service: AuthService
    chat_service: ChatService
    session_service: SessionService
    monitor_service: MonitorService


def build_context() -> AppContext:
    runtime = RuntimeContainer(storage_path="data", log_file="logs/session.jsonl")
    user_repo = UserRepository(StorageManager(storage_path="data"), user_index_file=os.path.join("data", "users.json"))
    auth_service = AuthService(user_repo)
    chat_service = ChatService(runtime=runtime, user_repo=user_repo, tester_token=(os.getenv("TESTER_TOKEN") or "").strip())
    session_service = SessionService(user_repo=user_repo, runtime=runtime)
    monitor_service = MonitorService(runtime=runtime)
    return AppContext(
        runtime=runtime,
        user_repo=user_repo,
        auth_service=auth_service,
        chat_service=chat_service,
        session_service=session_service,
        monitor_service=monitor_service,
    )

