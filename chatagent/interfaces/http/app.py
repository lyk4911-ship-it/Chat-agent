import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from interfaces.http.dependencies import build_context
from interfaces.http.routes_auth import build_auth_router
from interfaces.http.routes_chat import build_chat_router
from interfaces.http.routes_monitor import build_monitor_router
from interfaces.http.routes_sessions import build_session_router


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(title="Chat Box API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    ctx = build_context()
    tester_token = (os.getenv("TESTER_TOKEN") or "").strip()

    @app.get("/", response_class=HTMLResponse)
    async def root():
        ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "ui", "chatbox.html")
        ui_path = os.path.normpath(ui_path)
        if not os.path.exists(ui_path):
            legacy_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "chatbox.html")
            ui_path = os.path.normpath(legacy_path)
        if not os.path.exists(ui_path):
            return "<h2>Chat Box</h2><p>chatbox.html not found.</p>"
        with open(ui_path, encoding="utf-8") as f:
            return f.read()

    app.include_router(build_auth_router(ctx))
    app.include_router(build_chat_router(ctx))
    app.include_router(build_session_router(ctx))
    app.include_router(build_monitor_router(ctx, tester_token=tester_token))
    return app

