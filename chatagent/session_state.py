# session_state.py - SessionState class for tracking conversation state
# -*- coding: utf-8 -*-

import datetime as dt
from copy import deepcopy
from typing import Any, Dict, List, Optional

from exceptions import InvalidStateError

# Allowed values for validated properties
_VALID_RISK_FLAGS: frozenset = frozenset({"green", "yellow", "red"})
_VALID_MODES: frozenset = frozenset({"emotion", "info", "career", "risk"})


class SessionState:
    """
    Tracks the psychological profile and conversation state for a single session.

    Encapsulates all mutable state that evolves turn-by-turn.
    Two fields are exposed as validated @property attributes:
      • risk_flags      — must be "green" | "yellow" | "red"
      • conversation_mode — must be "emotion" | "info" | "career" | "risk"

    OOP features demonstrated:
      • Encapsulation  : private backing stores (_risk_flags, _conversation_mode)
      • @property      : validated setters with descriptive error messages
      • __str__ / __repr__ : human-readable display vs. programmer debugging
      • __eq__ / __hash__  : entity equality (same session_id → same entity)
      • __bool__           : truthy when the session has at least one turn
    """

    def __init__(self, session_id: str):
        self.session_id: str = session_id

        # Initialise updated_at FIRST so _touch() is safe in any setter
        self.updated_at: str = dt.datetime.now().isoformat(timespec="seconds")

        self.goal: Optional[str] = None
        self.problem_category: Optional[str] = None
        self.state_keywords: List[str] = []
        self.severity_score: Optional[float] = None
        self.time_available_min: Optional[float] = None
        self.constraints: Dict[str, Any] = deepcopy({
            "speech_ok": None,
            "public_env": None,
            "health_limits": [],
            "resources": [],
        })

        # Validated properties — set via backing stores to skip setter overhead
        # during construction (defaults are guaranteed valid)
        self._risk_flags: str = "green"
        self._conversation_mode: str = "emotion"

        self.phase: str = "rapport"
        self.turns: int = 0
        self.current_strategy: Optional[Dict[str, Any]] = None
        self.last_plan: Optional[Dict[str, Any]] = None
        self.suppress_questions_remaining: int = 0
        self.assistant_question_streak: int = 0
        self._last_micro_turn: Optional[int] = None
        self.last_proactive_unix: Optional[float] = None

    # ──────────────────────────────────────────────────────────────────────────
    # Validated properties
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def risk_flags(self) -> str:
        """Risk level: ``"green"`` | ``"yellow"`` | ``"red"``."""
        return self._risk_flags

    @risk_flags.setter
    def risk_flags(self, value: str) -> None:
        if value not in _VALID_RISK_FLAGS:
            raise InvalidStateError(
                f"risk_flags must be one of {sorted(_VALID_RISK_FLAGS)}, "
                f"got {value!r}"
            )
        self._risk_flags = value
        if hasattr(self, "updated_at"):
            self._touch()

    @property
    def conversation_mode(self) -> str:
        """Active mode: ``"emotion"`` | ``"info"`` | ``"career"`` | ``"risk"``."""
        return self._conversation_mode

    @conversation_mode.setter
    def conversation_mode(self, value: str) -> None:
        if value not in _VALID_MODES:
            raise InvalidStateError(
                f"conversation_mode must be one of {sorted(_VALID_MODES)}, "
                f"got {value!r}"
            )
        self._conversation_mode = value
        if hasattr(self, "updated_at"):
            self._touch()

    # ──────────────────────────────────────────────────────────────────────────
    # Magic methods
    # ──────────────────────────────────────────────────────────────────────────

    def __str__(self) -> str:
        """Human-readable summary for logging and display."""
        return (
            f"Session {self.session_id[:8]} | "
            f"turns={self.turns} | risk={self._risk_flags} | "
            f"mode={self._conversation_mode} | "
            f"goal={self.goal or '(none)'!r}"
        )

    def __repr__(self) -> str:
        return (
            f"SessionState(id={self.session_id!r}, turns={self.turns}, "
            f"risk={self._risk_flags!r}, mode={self._conversation_mode!r})"
        )

    def __bool__(self) -> bool:
        """``True`` when the session has had at least one turn of conversation."""
        return self.turns > 0

    def __eq__(self, other: object) -> bool:
        """
        Entity equality: two ``SessionState`` objects are the same entity if
        they share the same ``session_id`` (regardless of current state).
        """
        if not isinstance(other, SessionState):
            return NotImplemented
        return self.session_id == other.session_id

    def __hash__(self) -> int:
        """Hash by ``session_id`` so sessions can be stored in sets/dicts."""
        return hash(self.session_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _touch(self) -> None:
        """Refresh the last-updated timestamp after any state mutation."""
        self.updated_at = dt.datetime.now().isoformat(timespec="seconds")

    # ──────────────────────────────────────────────────────────────────────────
    # Mutation methods
    # ──────────────────────────────────────────────────────────────────────────

    def update(self, topic: Optional[str] = None, summary: Optional[str] = None) -> None:
        """Update key state fields and refresh the timestamp."""
        if topic is not None:
            self.goal = topic
        if summary is not None and summary not in self.state_keywords:
            self.state_keywords.append(summary)
        self._touch()

    def apply_patch(self, patch: Dict[str, Any]) -> None:
        """
        Incrementally update state from an LLM-extracted patch dict.
        Only overwrites fields that carry a non-null value in the patch.
        Invalid values for validated properties are silently skipped.
        """
        if not isinstance(patch, dict):
            return
        for k in ("goal", "problem_category", "severity_score", "time_available_min"):
            if k in patch and patch[k] not in (None, "", []):
                setattr(self, k, patch[k])

        # Validated property — guard against malformed LLM output
        if "risk_flags" in patch and patch["risk_flags"] in _VALID_RISK_FLAGS:
            self._risk_flags = patch["risk_flags"]

        if "state_keywords" in patch and isinstance(patch["state_keywords"], list):
            add = [x for x in patch["state_keywords"] if x and isinstance(x, str)]
            combined = list(dict.fromkeys(self.state_keywords + add))
            self.state_keywords = combined[-20:]

        c = patch.get("constraints")
        if isinstance(c, dict):
            for ck in ("speech_ok", "public_env"):
                if ck in c and c[ck] not in (None, ""):
                    self.constraints[ck] = c[ck]
            for ck in ("health_limits", "resources"):
                if ck in c and isinstance(c[ck], list):
                    combined = list(dict.fromkeys(
                        (self.constraints.get(ck) or []) + [x for x in c[ck] if x]
                    ))
                    self.constraints[ck] = combined[-20:]

        self._touch()

    def to_rule_context(self) -> Dict[str, Any]:
        """Return the subset of state used by conversation policy rules."""
        return {
            "risk_flags": self._risk_flags,
            "conversation_mode": self._conversation_mode,
            "suppress_questions_remaining": self.suppress_questions_remaining,
            "assistant_question_streak": self.assistant_question_streak,
            "_last_micro_turn": self._last_micro_turn,
            "turns": self.turns,
        }

    def increment_turns(self) -> int:
        """Advance the session turn counter and return the new value."""
        self.turns += 1
        self._touch()
        return self.turns

    def set_conversation_mode(self, mode: str) -> None:
        """Persist the active conversation mode (validates via property)."""
        if mode in _VALID_MODES:
            self._conversation_mode = mode
            self._touch()

    def set_current_strategy(self, strategy: Optional[Dict[str, Any]]) -> None:
        """Store the currently selected intervention strategy."""
        self.current_strategy = deepcopy(strategy) if strategy else None
        self._touch()

    def remember_plan(self, strategy_id: str) -> None:
        """Record the last plan-oriented strategy handed to the assistant."""
        self.last_plan = {
            "strategy_id": strategy_id,
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.phase = "followup"
        self._touch()

    def request_question_suppression(self, minimum_turns: int = 4) -> None:
        """Suppress follow-up questions for at least *minimum_turns* future turns."""
        self.suppress_questions_remaining = max(
            minimum_turns, int(self.suppress_questions_remaining or 0)
        )
        self._touch()

    def consume_question_suppression(self) -> None:
        """Decrease the remaining question-suppression counter by one turn."""
        if int(self.suppress_questions_remaining or 0) > 0:
            self.suppress_questions_remaining -= 1
            self._touch()

    def record_assistant_reply(self, reply: str) -> None:
        """Update question-streak tracking based on the latest assistant reply."""
        text = reply or ""
        question_count = text.count("？") + text.count("?")
        if question_count >= 1 and len(text) < 800:
            self.assistant_question_streak += 1
        else:
            self.assistant_question_streak = 0
        self._touch()

    def can_add_micro_intervention(self, cooldown_turns: int = 2) -> bool:
        """Return ``True`` if enough turns have passed since the last micro-intervention."""
        if self._last_micro_turn is None:
            return True
        return self.turns - int(self._last_micro_turn) >= cooldown_turns

    def mark_micro_intervention_used(self) -> None:
        """Record the turn when a micro-intervention was appended."""
        self._last_micro_turn = self.turns
        self._touch()

    def can_send_proactive(self, now: float, cooldown_sec: float) -> bool:
        """Return ``True`` if a proactive message may be sent right now."""
        if self.turns < 1:
            return False
        if self.last_proactive_unix is None:
            return True
        return (now - float(self.last_proactive_unix)) >= cooldown_sec

    def record_proactive_message(self, sent_at: float) -> None:
        """Store the timestamp of the latest proactive message."""
        self.last_proactive_unix = sent_at
        self._touch()

    # ──────────────────────────────────────────────────────────────────────────
    # Serialisation
    # ──────────────────────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialise full state to a plain dictionary."""
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "problem_category": self.problem_category,
            "state_keywords": self.state_keywords,
            "severity_score": self.severity_score,
            "time_available_min": self.time_available_min,
            "constraints": deepcopy(self.constraints),
            "risk_flags": self._risk_flags,
            "phase": self.phase,
            "turns": self.turns,
            "current_strategy": self.current_strategy,
            "last_plan": self.last_plan,
            "conversation_mode": self._conversation_mode,
            "suppress_questions_remaining": self.suppress_questions_remaining,
            "assistant_question_streak": self.assistant_question_streak,
            "_last_micro_turn": self._last_micro_turn,
            "last_proactive_unix": self.last_proactive_unix,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SessionState":
        """Restore a ``SessionState`` from a serialised dictionary."""
        s = SessionState(session_id=data.get("session_id", ""))
        for k in (
            "goal", "problem_category", "state_keywords", "severity_score",
            "time_available_min", "phase", "turns",
            "current_strategy", "last_plan",
            "suppress_questions_remaining", "assistant_question_streak",
            "_last_micro_turn", "last_proactive_unix", "updated_at",
        ):
            if k in data:
                setattr(s, k, data[k])
        # Validated properties: bypass setter's _touch on restore
        if "risk_flags" in data and data["risk_flags"] in _VALID_RISK_FLAGS:
            s._risk_flags = data["risk_flags"]
        if "conversation_mode" in data and data["conversation_mode"] in _VALID_MODES:
            s._conversation_mode = data["conversation_mode"]
        if "constraints" in data and isinstance(data["constraints"], dict):
            s.constraints = deepcopy(data["constraints"])
        return s
