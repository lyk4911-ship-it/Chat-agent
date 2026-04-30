from typing import List

from fastapi import APIRouter, HTTPException

from interfaces.http.dependencies import AppContext
from interfaces.http.schemas import CreateSessionRequest, SessionHistoryResponse, UserSessionItem


def build_session_router(ctx: AppContext) -> APIRouter:
    router = APIRouter(tags=["sessions"])

    @router.get("/users/{user_id}/sessions", response_model=List[UserSessionItem])
    async def list_user_sessions(user_id: str):
        try:
            rows = ctx.session_service.list_user_sessions(user_id)
            return [UserSessionItem(**r) for r in rows]
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.post("/users/{user_id}/sessions/new", response_model=SessionHistoryResponse)
    async def create_user_session(user_id: str, req: CreateSessionRequest):
        try:
            session_id = ctx.session_service.create_session(user_id, title=req.title)
            bundle = ctx.session_service.session_history(user_id, session_id)
            return SessionHistoryResponse(**bundle)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.get("/users/{user_id}/sessions/{session_id}/history", response_model=SessionHistoryResponse)
    async def get_session_history(user_id: str, session_id: str):
        try:
            bundle = ctx.session_service.session_history(user_id, session_id)
            return SessionHistoryResponse(**bundle)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

    return router

