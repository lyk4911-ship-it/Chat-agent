import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from interfaces.http.dependencies import AppContext
from interfaces.http.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


def build_chat_router(ctx: AppContext) -> APIRouter:
    router = APIRouter(tags=["chat"])
    subscribers: List[asyncio.Queue] = []

    def _broadcast(update: Dict[str, Any]) -> None:
        for q in subscribers:
            try:
                q.put_nowait(update)
            except asyncio.QueueFull:
                pass

    @router.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest):
        try:
            result = ctx.chat_service.send(
                text=req.text,
                session_id=req.session_id or "",
                user_id=req.user_id,
                proactive_ping=req.proactive_ping,
                allow_show_report=req.allow_show_report,
                tester_token=req.tester_token,
            )
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("chat error")
            raise HTTPException(status_code=500, detail=str(e))

        _broadcast({
            "session_id": result["session_id"],
            "turns": result["state"].get("turns", 0),
            "risk_flags": result["state"].get("risk_flags", "green"),
            "last_user": (req.text or "")[:80],
            "last_reply": (result["reply"] or "")[:80],
        })
        return ChatResponse(**result)

    @router.get("/admin/stream")
    async def admin_stream():
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        subscribers.append(q)

        async def event_generator():
            try:
                while True:
                    data = await q.get()
                    import json as _json
                    yield f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                subscribers.remove(q)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return router

