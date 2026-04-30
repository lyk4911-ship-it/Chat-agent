# chat_session.py - ChatSession class: main controller for one counseling session
# -*- coding: utf-8 -*-

import os
import json
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from message import Message
from session_state import SessionState
from api_client import ApiClient
from state_tracker import StateTracker
from response_service import ResponseService
from log_manager import LogManager
from storage_manager import StorageManager

try:
    from agent_rules import ConversationPolicy
    _RULES_OK = True
except ImportError:
    ConversationPolicy = None
    _RULES_OK = False

PROACTIVE_MARKER = "__PROACTIVE__"
PROACTIVE_COOLDOWN_SEC = float(os.getenv("PROACTIVE_COOLDOWN_SEC") or 180)
STRATEGY_REFRESH_EVERY = int(os.getenv("STRATEGY_REFRESH_EVERY") or 3)
HISTORY_TURNS_KEEP = int(os.getenv("HISTORY_TURNS_KEEP") or 10)

PROACTIVE_FALLBACKS = [
    "How have you been lately? Want to talk?",
    "No rush. I am here with you.",
    "We can keep going anytime.",
]

PROACTIVE_QC_DENY = [
    "as an AI", "language model", "please note", "reminder", "need help", "professional",
    "psychological counseling", "advice", "dear user", "below", "first", "then", "finally",
]


class ChatSession:
    """
    Main controller for a single counseling chat session.
    Orchestrates message flow, state updates, strategy selection,
    and response generation. Composes all other service classes.

    Relationship summary:
        ChatSession 1--1 SessionState   (Composition)
        ChatSession 1--* Message        (Composition)
        ChatSession --> ResponseService (Association)
        ChatSession --> StateTracker    (Association)
        ChatSession --> LogManager      (Association)
        ChatSession --> StorageManager  (Dependency)

    OOP features demonstrated:
      • Composition   : owns SessionState and the Message list
      • __str__       : concise session summary
      • __repr__      : unambiguous programmer format
      • __len__       : ``len(session)`` → number of in-memory messages
      • __iter__      : ``for msg in session`` → iterate messages chronologically
      • __bool__      : truthy when at least one message has been exchanged
      • __contains__  : ``"keyword" in session`` → full-text search across messages
    """

    def __init__(
        self,
        session_id: str,
        api_client: ApiClient,
        storage: StorageManager,
        log_manager: LogManager,
        policy: Optional["ConversationPolicy"] = None,
    ):
        self.session_id: str = session_id
        self.api_client: ApiClient = api_client
        self.storage: StorageManager = storage
        self.log_manager: LogManager = log_manager
        self.policy: Optional["ConversationPolicy"] = policy if _RULES_OK else None

        # Load strategy & analysis data
        strategies = storage.load_strategies()
        analysis_lib = storage.load_analysis_lib()

        # Compose service objects
        self.state_tracker: StateTracker = StateTracker(api_client, analysis_lib)
        self.response_service: ResponseService = ResponseService(api_client, strategies)
        if self.policy is None and _RULES_OK:
            self.policy = ConversationPolicy()

        # Load or create session state
        loaded = storage.load_session(session_id)
        self.state: SessionState = loaded if loaded else SessionState(session_id)

        # In-memory message list for this session
        self._messages: List[Message] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def send_message(self, user_text: str, allow_show_report: bool = False) -> str:
        """
        Process one user message and return the assistant reply.
        This is the primary entry point called by the API layer.
        """
        user = (user_text or "").strip()

        # --- Built-in commands ---
        if user.lower() in ("/reset", "reset"):
            self.state = SessionState(self.session_id)
            self._messages.clear()
            return "Done. I cleared the profile. Where would you like to start?"

        if user.lower().startswith("/show"):
            if not allow_show_report:
                return "This command is for internal testing only and is not available to end users."
            return self._generate_report()

        # --- Proactive friend message ---
        if user == PROACTIVE_MARKER:
            reply, skipped = self._run_proactive_line()
            if skipped:
                return ""
            self._append("assistant", reply)
            return reply

        if not user:
            return "Say anything that is on your mind. I am listening."

        # --- Record user message ---
        self._append("user", user)
        if self.policy is not None:
            self.policy.apply_user_suppression_trigger(self.state, user)

        # --- Phase 1: Profile extraction (StateTracker) ---
        intent = self._analyze_user_turn(user)

        # --- Emergency risk handling ---
        if self.state.risk_flags == "red" or intent == "emergency":
            reply = self._emergency_reply()
            self._append("assistant", reply)
            self._persist()
            return reply

        # --- Turn accounting + mode ---
        mode, should_ask = self._decide_turn_policy(user)

        # --- Phase 2: Periodic strategy selection (ResponseService) ---
        self._refresh_strategy(intent)

        # --- Generate response ---
        reply = self._generate_assistant_reply(intent, mode, should_ask)

        # --- Policy-based finalization ---
        if self.policy is not None:
            reply = self.policy.finalize_reply(user, mode, reply, self.state)

        self._append("assistant", reply)
        self._persist()
        self.log_manager.log_turn(user, reply, self.state)
        return reply

    def get_history(self) -> List[Dict[str, Any]]:
        """Return conversation history as a list of dicts."""
        return [m.to_dict() for m in self._messages]

    def reset(self) -> None:
        """Clear session state and message history."""
        self.state = SessionState(self.session_id)
        self._messages.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, role: str, content: str) -> None:
        """Append a message to both the in-memory list and trim history."""
        msg = Message(self.session_id, role, content)
        self._messages.append(msg)
        # Keep only the last N turns in memory
        max_msgs = HISTORY_TURNS_KEEP * 2
        if len(self._messages) > max_msgs:
            self._messages = self._messages[-max_msgs:]

    def _to_api_messages(self) -> List[dict]:
        """Convert message list to OpenAI-compatible format."""
        return [{"role": m.sender, "content": m.content} for m in self._messages]

    def _analyze_user_turn(self, user_text: str) -> str:
        """Run profile extraction and merge the resulting patch into session state."""
        analysis = self.state_tracker.extract_state(
            self._to_api_messages(), self.state, user_text
        )
        patch = analysis.get("patch") if isinstance(analysis, dict) else None
        if isinstance(patch, dict):
            self.state.apply_patch(patch)
        return (analysis.get("intent") if isinstance(analysis, dict) else None) or "chat"

    def _decide_turn_policy(self, user_text: str) -> Tuple[str, bool]:
        """Advance turn accounting and decide the conversation policy for this turn."""
        self.state.increment_turns()
        if self.policy is None:
            return self.state.conversation_mode, False
        mode = self.policy.classify_mode(user_text, self.state)
        self.state.set_conversation_mode(mode)
        should_ask = self.policy.should_ask_question(user_text, self.state, mode)
        return mode, should_ask

    def _refresh_strategy(self, intent: str) -> None:
        """Update the session's currently selected strategy when needed."""
        has_profile = bool(
            self.state.state_keywords or
            self.state.problem_category or
            self.state.goal
        )
        needs_periodic_refresh = (
            STRATEGY_REFRESH_EVERY > 0 and
            has_profile and
            self.state.turns % STRATEGY_REFRESH_EVERY == 0
        )
        needs_plan_selection = intent == "plan" and not self.state.current_strategy
        if not (needs_periodic_refresh or needs_plan_selection):
            return
        try:
            current = self.response_service.select_strategy(self.state)
        except Exception:
            current = None
        if current:
            self.state.set_current_strategy(current)

    def _generate_assistant_reply(self, intent: str, mode: str, should_ask: bool) -> str:
        """Generate the assistant's reply for the current turn."""
        if self.api_client.is_available():
            reply = self.response_service.generate_response(
                self._to_api_messages(), self.state, mode, should_ask, intent
            )
        else:
            reply = self.response_service.fallback_response()

        if intent == "plan" and self.state.current_strategy:
            strategy_id = self.state.current_strategy.get("strategy_id")
            if strategy_id:
                self.state.remember_plan(strategy_id)
        return reply

    def _persist(self) -> None:
        """Save current state to disk."""
        try:
            self.storage.save_session(self.state)
        except Exception:
            pass

    def _emergency_reply(self) -> str:
        persona = {
            "risk_flags": self.state.risk_flags,
            "severity_score": self.state.severity_score,
            "goal": self.state.goal,
        }
        safe = (
            "It sounds like you are in deep distress, and there are clear risk signals.\n"
            "Please contact someone you trust, or your local crisis hotline / emergency services as soon as possible.\n"
            f"(Current profile: {json.dumps(persona, ensure_ascii=False)})"
        )
        return safe

    def _generate_report(self) -> str:
        """Generate a counselor-facing session report via the LLM."""
        transcript = "\n".join(
            f"[{m.sender}] {m.content}" for m in self._messages[-80:]
        )
        state_dict = self.state.to_dict()
        prompt = (
            f"[Conversation Transcript]\n{transcript}\n\n"
            f"[Profile]\n{json.dumps(state_dict, ensure_ascii=False)}\n\n"
            "Please output a structured counselor report with:\n"
            "1. Main observed issues\n"
            "2. Emotional state and risk assessment\n"
            "3. Core concerns and goals\n"
            "4. Selected intervention strategy\n"
            "5. Follow-up recommendations"
        )
        sys_msg = (
            "You are a counseling supervision assistant. Generate a structured report based on the transcript and profile. "
            "Analyze only. Do not role-play dialogue. Do not assume facts that are not present in the conversation."
        )
        return self.api_client.send_request(
            [{"role": "system", "content": sys_msg},
             {"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=900
        )

    def _run_proactive_line(self) -> Tuple[str, bool]:
        """Generate a short proactive 'friend' message."""
        now = time.time()
        if not self.state.can_send_proactive(now, PROACTIVE_COOLDOWN_SEC):
            return "", True
        transcript = "\n".join(
            f"[{m.sender}] {m.content}" for m in self._messages[-12:]
        )
        if len(transcript.strip()) < 12:
            return "", True

        sys_msg = (
            "You are the user's close friend. Based on the recent dialogue, output one warm proactive message only (max 20 words). "
            "No questions, no quotation marks, and no prefix labels."
        )
        try:
            raw = self.api_client.send_request(
                [{"role": "system", "content": sys_msg},
                 {"role": "user", "content": f"[Recent Dialogue]\n{transcript}"}],
                temperature=0.75, max_tokens=60
            )
            line = (raw or "").strip()
        except Exception:
            line = ""

        # QC
        if not self._proactive_ok(line):
            line = random.choice(PROACTIVE_FALLBACKS)

        self.state.record_proactive_message(now)
        return line, False

    @staticmethod
    def _proactive_ok(line: str) -> bool:
        if not line or len(line) < 4 or len(line) > 72:
            return False
        if "[ERR" in line or "http" in line.lower():
            return False
        if any(x in line for x in PROACTIVE_QC_DENY):
            return False
        if "？" in line or "?" in line:
            return False
        return True

    def __str__(self) -> str:
        """Human-readable session summary."""
        return (
            f"ChatSession {self.session_id[:8]} | "
            f"turns={self.state.turns} | "
            f"messages={len(self._messages)} | "
            f"risk={self.state.risk_flags}"
        )

    def __repr__(self) -> str:
        return f"ChatSession(id={self.session_id!r}, turns={self.state.turns})"

    def __len__(self) -> int:
        """Return the number of in-memory messages (user + assistant combined)."""
        return len(self._messages)

    def __iter__(self):
        """
        Iterate over in-memory messages in chronological order.

        Yields each ``Message`` object.  The list is already kept in order
        by ``_append``, so no extra sort is needed.
        """
        return iter(list(self._messages))

    def __bool__(self) -> bool:
        """``True`` when at least one message has been exchanged this session."""
        return len(self._messages) > 0

    def __contains__(self, item: object) -> bool:
        """
        Full-text membership test: ``"keyword" in session``.

        Returns ``True`` if *item* (str) appears as a substring in the content
        of any in-memory message, case-insensitively.
        """
        if not isinstance(item, str):
            return False
        needle = item.lower()
        return any(needle in m.content.lower() for m in self._messages)
