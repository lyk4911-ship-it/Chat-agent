from fastapi import APIRouter, HTTPException

from interfaces.http.dependencies import AppContext
from interfaces.http.schemas import AuthRequest, AuthResponse, UserSessionItem


def build_auth_router(ctx: AppContext) -> APIRouter:
    router = APIRouter(tags=["auth"])

    def _auth_payload(record: dict, is_new_user: bool) -> AuthResponse:
        sessions = ctx.session_service.list_user_sessions(record["user_id"])
        active_sid = sessions[0]["session_id"]
        history_bundle = ctx.session_service.session_history(record["user_id"], active_sid)
        return AuthResponse(
            username=record.get("username") or "",
            user_id=record.get("user_id") or "",
            session_id=active_sid,
            state=history_bundle["state"],
            history=history_bundle["history"],
            sessions=[UserSessionItem(**s) for s in sessions],
            is_new_user=is_new_user,
        )

    @router.post("/auth/register", response_model=AuthResponse)
    async def register(req: AuthRequest):
        try:
            record = ctx.auth_service.register(req.username, req.password)
            return _auth_payload(record, is_new_user=True)
        except ValueError as e:
            msg = str(e)
            if "已存在" in msg:
                raise HTTPException(status_code=409, detail=msg)
            raise HTTPException(status_code=400, detail=msg)

    @router.post("/auth/login", response_model=AuthResponse)
    async def login(req: AuthRequest):
        try:
            record = ctx.auth_service.login(req.username, req.password)
            return _auth_payload(record, is_new_user=False)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return router

