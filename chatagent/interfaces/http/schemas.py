from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    text: str = ""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    allow_show_report: bool = False
    tester_token: Optional[str] = None
    proactive_ping: bool = False


class ChatResponse(BaseModel):
    reply: str
    state: Dict[str, Any]
    session_id: str
    reply_ts: str
    proactive_skipped: bool = False


class AuthRequest(BaseModel):
    username: str
    password: str


class UserSessionItem(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str


class AuthResponse(BaseModel):
    username: str
    user_id: str
    session_id: str
    state: Dict[str, Any]
    history: List[Dict[str, Any]]
    sessions: List[UserSessionItem]
    is_new_user: bool = False


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    state: Dict[str, Any]
    history: List[Dict[str, Any]]


class AdminSessionSummary(BaseModel):
    session_id: str
    risk_flags: str
    turns: int
    goal: Optional[str]
    updated_at: Optional[str]

