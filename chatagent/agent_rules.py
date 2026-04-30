# agent_rules.py - Conversation mode classification and question gating rules
# -*- coding: utf-8 -*-

import json
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from session_state import SessionState

StateLike = Union[SessionState, Dict[str, Any]]


class ConversationPolicy:
    """Policy object that encapsulates conversational rule decisions."""

    RISK_PATTERNS = [
        r"don't want to live", r"end my life", r"suicide", r"self[- ]harm",
        r"kill myself", r"want to die", r"can't go on", r"go die", r"die",
    ]

    CAREER_KEYWORDS = [
        "career", "major", "offer", "switch job", "job change", "resume",
        "cv", "career planning", "direction", "which one", "should i",
        "phd", "graduate school", "study abroad", "internship", "industry",
        "role", "position",
    ]

    INFO_KEYWORDS = [
        "what is", "meaning", "how to", "official website", "register",
        "deadline", "process", "requirements", "score", "reference book",
        "subjects", "syllabus", "link", "where to find", "announcement",
    ]

    NO_QUESTION_PHRASES = [
        "don't ask me", "stop asking", "no questions", "just tell me",
        "be direct", "say it directly", "give me more", "don't interrupt",
        "don't circle around", "just answer", "you can just answer",
    ]

    MICRO_TRIGGERS: List[Tuple[str, str]] = [
        (r"popular|trending|everyone is", "Popular and suitable are often different. Decide what matters most to you before chasing trends."),
        (r"burnout|rat race|competition", "Sometimes the pressure comes from the environment, not from what you truly want."),
        (r"don't know what i want|lost|no direction", "Direction usually gets clearer after trying a few small experiments, not from one perfect decision."),
        (r"too much information|overwhelmed|doomscroll", "When information overload hits, pick one question to solve tonight. That usually works better than more scrolling."),
        (r"others say|they all", "Other people's standards can be useful input, but your final decision should fit your own constraints and goals."),
    ]

    def __init__(self, rules_path: str = "emotion_rules.json", micro_probability: float = 0.45):
        self.rules_path = rules_path
        self.micro_probability = micro_probability
        self._rules_cache: Optional[Dict[str, Any]] = None

    def load_emotion_rules(self) -> Dict[str, Any]:
        """Load optional rule overrides from disk."""
        if self._rules_cache is not None:
            return self._rules_cache
        if not os.path.exists(self.rules_path):
            self._rules_cache = {}
            return self._rules_cache
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                self._rules_cache = json.load(f)
        except Exception:
            self._rules_cache = {}
        return self._rules_cache

    @staticmethod
    def _get_state_value(state: StateLike, key: str, default: Any = None) -> Any:
        if isinstance(state, SessionState):
            return getattr(state, key, default)
        return state.get(key, default)

    @staticmethod
    def _set_state_value(state: StateLike, key: str, value: Any) -> None:
        if isinstance(state, SessionState):
            setattr(state, key, value)
            state._touch()
            return
        state[key] = value

    def classify_mode(self, user_text: str, state: StateLike) -> str:
        """Rule-based conversation mode classification."""
        text = (user_text or "").strip()
        if not text:
            return self._get_state_value(state, "conversation_mode", "emotion") or "emotion"

        for pattern in self.RISK_PATTERNS:
            if re.search(pattern, text):
                return "risk"
        if self._get_state_value(state, "risk_flags") == "red":
            return "risk"

        if any(keyword in text for keyword in self.CAREER_KEYWORDS):
            return "career"

        if any(keyword in text for keyword in self.INFO_KEYWORDS) and len(text) < 160:
            if not any(k in text for k in ["sad", "anxious", "can't sleep", "overwhelmed", "stress", "cry", "depressed"]):
                return "info"

        rules = self.load_emotion_rules()
        extra_career = (rules.get("career_keywords") or []) if isinstance(rules, dict) else []
        if extra_career and any(keyword in text for keyword in extra_career):
            return "career"

        return "emotion"

    def user_requests_no_questions(self, user_text: str) -> bool:
        """Whether the user explicitly asks the assistant not to question them."""
        text = (user_text or "").strip()
        return any(phrase in text for phrase in self.NO_QUESTION_PHRASES)

    def should_ask_question(
        self,
        user_text: str,
        state: StateLike,
        mode: str,
        response_plan: Optional[str] = None,
    ) -> bool:
        """Only allow questions when they materially improve the next turn."""
        del response_plan
        if self._get_state_value(state, "suppress_questions_remaining", 0) > 0:
            return False
        if self.user_requests_no_questions(user_text):
            return False

        text = (user_text or "").strip()

        if mode == "info" and len(text) < 200:
            return False
        if mode == "career":
            return bool(re.search(r"or|which is better|pick one|which one|A or B", text, flags=re.I))
        if mode in ("risk", "emotion"):
            return False
        if int(self._get_state_value(state, "assistant_question_streak", 0)) >= 1:
            return False
        return False

    def _pick_micro_from_rules(self, user_text: str) -> Optional[str]:
        """Combine built-in micro-interventions with optional JSON overrides."""
        text = user_text or ""
        rules = self.load_emotion_rules()
        extra = rules.get("micro_triggers") if isinstance(rules, dict) else None
        pairs: List[Tuple[str, str]] = list(self.MICRO_TRIGGERS)
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, dict) and item.get("pattern") and item.get("line"):
                    pairs.append((str(item["pattern"]), str(item["line"])))

        for pattern, line in pairs:
            try:
                if re.search(pattern, text):
                    return line
            except re.error:
                continue
        return None

    def maybe_add_micro_intervention(
        self,
        user_text: str,
        mode: str,
        draft_reply: str,
        state: StateLike,
    ) -> str:
        """Append a lightweight micro-intervention when the rules allow it."""
        if mode == "info" and len((user_text or "").strip()) < 100:
            if not re.search(r"lost|stuck|don't know", user_text or "", flags=re.I):
                return draft_reply

        if isinstance(state, SessionState) and not state.can_add_micro_intervention():
            return draft_reply

        last_turn = self._get_state_value(state, "_last_micro_turn")
        current_turn = int(self._get_state_value(state, "turns", 0))
        if last_turn is not None and current_turn - int(last_turn) < 2:
            return draft_reply

        line = self._pick_micro_from_rules(user_text)
        if not line:
            return draft_reply
        if line[:12] in (draft_reply or ""):
            return draft_reply
        if random.random() > self.micro_probability:
            return draft_reply

        if isinstance(state, SessionState):
            state.mark_micro_intervention_used()
        else:
            state["_last_micro_turn"] = current_turn
        return (draft_reply or "").rstrip() + "\n" + line

    @staticmethod
    def mode_system_addon(mode: str) -> str:
        """Extra system prompt content describing the active conversation mode."""
        mapping = {
            "info": "[Mode: Information Support] Prioritize direct facts and actionable steps. Avoid over-questioning and avoid turning this into therapy.",
            "career": "[Mode: Career/Decision Support] Start with a decision framework (dimensions, criteria, trade-offs), then give a small action plan. Do not jump into long task lists.",
            "emotion": "[Mode: Emotional Support] Focus on listening and validating feelings. Avoid pushing follow-up questions or forcing task-oriented steps.",
            "risk": "[Mode: High-Risk Support] Safety comes first. Keep language calm, avoid preaching, and avoid probing for unnecessary details.",
        }
        return mapping.get(mode, mapping["emotion"])

    @staticmethod
    def listening_mode_addon() -> str:
        """Prompt addon for extra listening-oriented turns."""
        return (
            "[Listening Companion] Focus on understanding first, not immediate advice. "
            "If the user is mainly venting, do not force a big summary or lecture."
        )

    def apply_user_suppression_trigger(self, state: StateLike, user_text: str) -> None:
        """Raise the no-question suppression counter when the user asks for direct output."""
        if not self.user_requests_no_questions(user_text):
            return
        if isinstance(state, SessionState):
            state.request_question_suppression()
            return
        state["suppress_questions_remaining"] = max(
            4, int(state.get("suppress_questions_remaining", 0))
        )

    def apply_suppression_after_reply(self, state: StateLike) -> None:
        """Decrease the suppression counter after an assistant reply."""
        if isinstance(state, SessionState):
            state.consume_question_suppression()
            return
        remaining = int(state.get("suppress_questions_remaining", 0))
        if remaining > 0:
            state["suppress_questions_remaining"] = remaining - 1

    def update_assistant_question_streak(self, state: StateLike, reply: str) -> None:
        """Update question-streak tracking based on the assistant reply."""
        if isinstance(state, SessionState):
            state.record_assistant_reply(reply)
            return
        content = reply or ""
        question_count = content.count("？") + content.count("?")
        if question_count >= 1 and len(content) < 800:
            state["assistant_question_streak"] = int(state.get("assistant_question_streak", 0)) + 1
        else:
            state["assistant_question_streak"] = 0

    def finalize_reply(
        self,
        user_text: str,
        mode: str,
        draft_reply: str,
        state: SessionState,
    ) -> str:
        """Finalize a reply after generation and update policy-owned state."""
        reply = self.maybe_add_micro_intervention(user_text, mode, draft_reply, state)
        self.update_assistant_question_streak(state, reply)
        self.apply_suppression_after_reply(state)
        return reply


_DEFAULT_POLICY = ConversationPolicy()


def load_emotion_rules(path: str = "emotion_rules.json") -> Dict[str, Any]:
    """Legacy function wrapper for rule loading."""
    if path != _DEFAULT_POLICY.rules_path:
        return ConversationPolicy(rules_path=path).load_emotion_rules()
    return _DEFAULT_POLICY.load_emotion_rules()


def classify_conversation_mode(user_text: str, state: StateLike) -> str:
    return _DEFAULT_POLICY.classify_mode(user_text, state)


def user_requests_no_questions(user_text: str) -> bool:
    return _DEFAULT_POLICY.user_requests_no_questions(user_text)


def should_ask_question(
    user_text: str,
    state: StateLike,
    mode: str,
    response_plan: Optional[str] = None,
) -> bool:
    return _DEFAULT_POLICY.should_ask_question(user_text, state, mode, response_plan)


def maybe_add_micro_intervention(
    user_text: str,
    mode: str,
    draft_reply: str,
    state: StateLike,
) -> str:
    return _DEFAULT_POLICY.maybe_add_micro_intervention(user_text, mode, draft_reply, state)


def mode_system_addon(mode: str) -> str:
    return _DEFAULT_POLICY.mode_system_addon(mode)


def listening_mode_addon() -> str:
    return _DEFAULT_POLICY.listening_mode_addon()


def apply_user_suppression_trigger(state: StateLike, user_text: str) -> None:
    _DEFAULT_POLICY.apply_user_suppression_trigger(state, user_text)


def apply_suppression_after_reply(state: StateLike) -> None:
    _DEFAULT_POLICY.apply_suppression_after_reply(state)


def update_assistant_question_streak(state: StateLike, reply: str) -> None:
    _DEFAULT_POLICY.update_assistant_question_streak(state, reply)


def count_question_like_in_assistant(state: Dict[str, Any]) -> int:
    """Roughly detect whether the last assistant turn is question-heavy."""
    history = state.get("_history") or []
    if len(history) < 2:
        return 0
    last = history[-1]
    if last.get("role") != "assistant":
        return 0
    content = last.get("content") or ""
    question_count = content.count("？") + content.count("?")
    return 1 if question_count >= 1 else 0
