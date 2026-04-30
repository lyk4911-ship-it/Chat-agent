from typing import Any, Dict, List

from application_services import ApplicationServices, ChatSessionRegistry


class RuntimeContainer:
    """Runtime composition root for legacy chat engine services."""

    def __init__(self, storage_path: str = "data", log_file: str = "logs/session.jsonl"):
        self.services = ApplicationServices.from_env(storage_path=storage_path, log_file=log_file)
        self.registry = ChatSessionRegistry(self.services, max_sessions=100)

    def get_or_create_session(self, session_id: str):
        return self.registry.get_or_create(session_id)

    def reset_session(self, session_id: str) -> None:
        self.registry.reset(session_id)

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        return self.services.monitor.list_active_sessions()

    def list_high_risk_sessions(self) -> List[Dict[str, Any]]:
        return self.services.monitor.get_high_risk_sessions()

    def generate_report(self, session_id: str) -> str:
        return self.services.monitor.generate_report(session_id)

    def generate_emergency_report(self, session_id: str) -> str:
        return self.services.monitor.generate_emergency_report(session_id)

    def get_logs(self, session_id: str, limit: int = 120) -> List[Dict[str, Any]]:
        return self.services.log_manager.get_logs(session_id=session_id, limit=limit)

