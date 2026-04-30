from typing import List, Optional

from fastapi import APIRouter, HTTPException

from interfaces.http.dependencies import AppContext
from interfaces.http.schemas import AdminSessionSummary


def build_monitor_router(ctx: AppContext, tester_token: str) -> APIRouter:
    router = APIRouter(tags=["monitor"])
    expected = (tester_token or "").strip()

    def _authorized(token: Optional[str]) -> bool:
        if not expected:
            return True
        return (token or "").strip() == expected

    @router.get("/sessions", response_model=List[AdminSessionSummary])
    async def list_sessions():
        rows = ctx.monitor_service.list_sessions()
        return [AdminSessionSummary(**row) for row in rows]

    @router.get("/sessions/high-risk")
    async def high_risk_sessions():
        return ctx.monitor_service.high_risk_sessions()

    @router.get("/sessions/{session_id}/report")
    async def session_report(session_id: str, tester_token: Optional[str] = None):
        if not _authorized(tester_token):
            raise HTTPException(status_code=403, detail="Unauthorized")
        return {"report": ctx.monitor_service.report(session_id)}

    @router.get("/sessions/{session_id}/emergency")
    async def emergency_report(session_id: str, tester_token: Optional[str] = None):
        if not _authorized(tester_token):
            raise HTTPException(status_code=403, detail="Unauthorized")
        return {"report": ctx.monitor_service.emergency_report(session_id)}

    @router.delete("/sessions/{session_id}")
    async def reset_session(session_id: str):
        ctx.monitor_service.reset(session_id)
        return {"status": "reset", "session_id": session_id}

    return router

