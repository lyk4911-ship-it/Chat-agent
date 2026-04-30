# response_service.py - ResponseService class for generating chat replies
# -*- coding: utf-8 -*-

import json
import re
import random
from typing import Any, Dict, List, Optional

from api_client import ApiClient
from session_state import SessionState


class ResponseService:
    """
    Generates assistant replies using the LLM API.
    Selects the best intervention strategy from the strategy library,
    and applies post-processing rules to keep responses natural and non-intrusive.
    """

    STRATEGY_PICK_SYS = (
        "You are a counseling strategy selection assistant. Choose the most suitable intervention strategy from the strategy library based on the user's profile.\n"
        'Output exactly one strict JSON line: {"strategy_id": "...", "why": ["..."], "confidence": 0.0-1.0}\n'
        "Requirements: base your decision strictly on the profile and candidate strategy fields; do not invent conversation facts.\n"
    )

    CHAT_SYS = (
        "You are a calm, thoughtful conversational assistant, like a reliable friend. Prioritize emotional attunement instead of pushing the user to answer you.\n"
        "Tone: natural spoken English, not customer service style or textbook style. Do not overuse empathy templates.\n"
        "Length: usually 2-5 sentences, favor concise phrasing like instant messaging.\n"
        "[Question Discipline] Default to no questions, especially in emotional support turns. Do not throw the burden back to the user.\n"
    )

    PLAN_SYS = (
        "You are a micro-action assistant with a close-friend style. Answer using the [Profile] and [Selected Strategy].\n"
        "1) Start with 2-4 sentences that give decision dimensions and trade-off criteria.\n"
        "2) Then provide 1-2 tiny steps, each prefixed with '·', each doable in <=2 minutes, in plain conversational language.\n"
        "3) If questions are allowed, end with one gentle question; otherwise close with a statement.\n"
        "Do not diagnose and do not label the user.\n"
    )

    FALLBACK_REPLIES = [
        "I am here. You can keep going.",
        "Take a breath first. No need to figure everything out right now.",
    ]

    def __init__(self, api_client: ApiClient, strategies: List[Dict[str, Any]]):
        self.api_client: ApiClient = api_client
        self.strategies: List[Dict[str, Any]] = strategies

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def select_strategy(self, state: SessionState) -> Optional[Dict[str, Any]]:
        """
        Ask the LLM to pick the most suitable strategy for the current session state.
        Returns a dict with strategy_id, why, confidence; or None on failure.
        """
        candidates = self._preselect(state, k=12)
        if not candidates:
            return None
        cand_text = self._format_strategies(candidates)
        persona = {k: getattr(state, k, None)
                   for k in ("goal", "problem_category", "state_keywords",
                              "severity_score", "time_available_min",
                              "constraints", "risk_flags")}
        prompt = (
            f"[Profile]{json.dumps(persona, ensure_ascii=False)}\n"
            f"[Candidate Strategies]\n{cand_text}\n\n"
            "Please choose the single best-fitting strategy_id for the current turn."
        )
        raw = self.api_client.send_request(
            [{"role": "system", "content": self.STRATEGY_PICK_SYS},
             {"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=160
        )
        dec = self._safe_json(raw)
        if not dec.get("strategy_id"):
            return None
        import datetime as dt
        return {
            "strategy_id": dec["strategy_id"],
            "why": dec.get("why") if isinstance(dec.get("why"), list) else [],
            "confidence": float(dec.get("confidence") or 0.0),
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------
    # Response generation
    # ------------------------------------------------------------------

    def generate_response(self, messages: List[dict], state: SessionState,
                          mode: str = "emotion", should_ask: bool = False,
                          intent: str = "chat") -> str:
        """
        Generate a reply for the current turn.
        Uses plan mode when intent=='plan', chat mode otherwise.
        """
        if intent == "plan":
            return self._plan_reply(messages, state, should_ask)
        return self._chat_reply(messages, state, mode, should_ask)

    def fallback_response(self) -> str:
        """Return a safe fallback reply when API is unavailable."""
        return random.choice(self.FALLBACK_REPLIES)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _chat_reply(self, messages: List[dict], state: SessionState,
                    mode: str, should_ask: bool) -> str:
        brief = {
            "goal": state.goal,
            "problem_category": state.problem_category,
            "severity": state.severity_score,
            "keywords": (state.state_keywords or [])[:6],
        }
        ask_line = (
            "[Output Requirement] If truly necessary, ask at most one high-quality follow-up question; otherwise do not ask."
            if should_ask
            else "[Output Requirement] Do not solicit a response from the user. It is acceptable to validate and hold space without pushing the conversation forward."
        )
        system = "\n\n".join([
            self.CHAT_SYS,
            f"[Profile Hint - reference only]\n{json.dumps(brief, ensure_ascii=False)}",
            ask_line,
        ])
        msgs = [{"role": "system", "content": system}] + messages
        raw = self.api_client.send_request(msgs, temperature=0.6, max_tokens=220)
        return self._postprocess(raw, should_ask)

    def _plan_reply(self, messages: List[dict], state: SessionState,
                    should_ask: bool) -> str:
        strategy_id = (state.current_strategy or {}).get("strategy_id")
        chosen = next((s for s in self.strategies
                       if s.get("strategy_id") == strategy_id), None)
        chosen_prompt = {
            "strategy_id": (chosen or {}).get("strategy_id"),
            "duration_min": (chosen or {}).get("duration_min"),
            "safety_level": (chosen or {}).get("safety_level"),
            "evidence_level": (chosen or {}).get("evidence_level"),
        }
        persona = {k: getattr(state, k, None)
                   for k in ("goal", "problem_category", "state_keywords",
                              "severity_score", "time_available_min",
                              "constraints", "risk_flags")}
        ask_line = (
            "[This Turn] If you need a closing line, use at most one gentle question."
            if should_ask
            else "[This Turn] Do not end with a question mark or rhetorical question."
        )
        system = self.PLAN_SYS + "\n" + ask_line
        prompt = (
            f"[Profile]{json.dumps(persona, ensure_ascii=False)}\n"
            f"[Selected Strategy]{json.dumps(chosen_prompt, ensure_ascii=False)}\n"
            "Based on the dialogue history and the information above, generate the final user-facing reply."
        )
        msgs = [{"role": "system", "content": system}] + messages + \
               [{"role": "user", "content": prompt}]
        raw = self.api_client.send_request(msgs, temperature=0.55, max_tokens=220)
        return self._postprocess(raw, should_ask)

    def _preselect(self, state: SessionState, k: int = 12) -> List[Dict[str, Any]]:
        scored = []
        for r in self.strategies:
            sc = self._match_score(r, state)
            if sc > -999:
                scored.append((sc, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        seen, out = set(), []
        for _, r in scored:
            nm = r.get("name", "")
            if nm and nm not in seen:
                seen.add(nm)
                out.append(r)
            if len(out) >= k:
                break
        return out

    @staticmethod
    def _match_score(row: Dict[str, Any], state: SessionState) -> int:
        c = state.constraints or {}
        if c.get("public_env") or c.get("speech_ok") is False:
            if "voice" in (row.get("delivery_mode") or "").lower():
                return -999
        for h in (c.get("health_limits") or []):
            if h and h in (row.get("contraindications") or ""):
                return -999
        score = 0
        cat_map = {
            "physiological regulation": "emotion",
            "attention allocation": "attention",
            "cognitive change": "cognition",
            "task structuring": "behavior",
            "emotion induction": "emotion",
            "environment regulation": "emotion",
            "social regulation": "social",
            "metacognition": "cognition",
        }
        mapped = cat_map.get((row.get("category") or "").lower(), "general")
        if state.problem_category and mapped == state.problem_category:
            score += 3
        for kw in (state.state_keywords or []):
            for f in ("name", "target_state", "notes"):
                if kw and kw in (row.get(f) or ""):
                    score += 1
        if state.time_available_min:
            try:
                if float(row.get("duration_min", 99)) <= float(state.time_available_min) + 0.5:
                    score += 2
            except Exception:
                pass
        return score

    @staticmethod
    def _postprocess(reply: str, should_ask: bool) -> str:
        t = (reply or "").strip()
        if not should_ask:
            t = t.replace("？", ".").replace("?", ".")
            t = re.sub(r"[.]{2,}", ".", t)
        return t.strip() or "I am here. You can keep going."

    @staticmethod
    def _format_strategies(rows: List[Dict[str, Any]]) -> str:
        return "\n".join(
            f"- id={r.get('strategy_id')} | duration_min={r.get('duration_min')} | "
            f"safety={r.get('safety_level')} | evidence={r.get('evidence_level')}"
            for r in rows
        ) or "(no candidate strategies)"

    @staticmethod
    def _safe_json(text: str) -> Dict[str, Any]:
        try:
            m = re.search(r"\{.*\}", text, flags=re.S)
            return json.loads(m.group(0) if m else "{}")
        except Exception:
            return {}

    def __repr__(self) -> str:
        return (f"ResponseService(api_client={self.api_client!r}, "
                f"strategies={len(self.strategies)})")
