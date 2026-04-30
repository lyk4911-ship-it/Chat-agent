from typing import Any, Dict, List

from infrastructure.runtime import RuntimeContainer


class MonitorService:
    """Admin-facing monitoring/report use-cases."""

    def __init__(self, runtime: RuntimeContainer):
        self.runtime = runtime

    def list_sessions(self) -> List[Dict[str, Any]]:
        return self.runtime.list_active_sessions()

    def high_risk_sessions(self) -> List[Dict[str, Any]]:
        return self.runtime.list_high_risk_sessions()

    def report(self, session_id: str) -> str:
        return self.runtime.generate_report(session_id)

    def emergency_report(self, session_id: str) -> str:
        return self.runtime.generate_emergency_report(session_id)

    def reset(self, session_id: str) -> None:
        self.runtime.reset_session(session_id)

