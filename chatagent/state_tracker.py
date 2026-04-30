# state_tracker.py - StateTracker class for extracting session state from dialogue
# -*- coding: utf-8 -*-

import json
import re
from typing import Any, Dict, List, Optional

from api_client import ApiClient
from session_state import SessionState


class StateTracker:
    """
    Uses the LLM API and an analysis library to extract and update
    the psychological profile (SessionState) from user messages.
    Simulates the counsellor's process of building a client profile.
    """

    ANALYSIS_SYS = (
        "You are a counseling profile-construction assistant. Your job is to infer user state from the dialogue and the analysis library, then build/update a profile.\n"
        "Output exactly one strict JSON line. No explanation.\n"
        'Output format:\n{"patch": { ... }, "intent": "chat|plan|emergency", '
        '"confidence": 0.0-1.0, "missing": ["field_name", ...]}\n'
        "Allowed patch fields: goal, problem_category, state_keywords[], severity_score(0-10), "
        "time_available_min, constraints:{speech_ok, public_env, health_limits[], resources[]}, "
        "risk_flags(green|yellow|red)\n"
        "Rules: fill only fields you are confident about; if uncertain, omit the field or set it to null.\n"
    )

    def __init__(self, api_client: ApiClient, analysis_lib: Dict[str, Any]):
        self.api_client: ApiClient = api_client
        self.analysis_lib: Dict[str, Any] = analysis_lib

    def extract_state(self, messages: List[dict], state: SessionState,
                      user_text: str) -> Dict[str, Any]:
        """
        Call the LLM to extract a state patch from the latest user message.
        Returns a dict with keys: patch, intent, confidence, missing.
        """
        lib_str = json.dumps(self.analysis_lib, ensure_ascii=False)
        if len(lib_str) > 6000:
            lib_str = lib_str[:6000] + "...(truncated)"

        state_summary = {k: getattr(state, k, None)
                         for k in ("goal", "problem_category", "state_keywords",
                                   "severity_score", "time_available_min",
                                   "constraints", "risk_flags", "phase")}

        prompt = (
            f"[Analysis Library]\n{lib_str}\n\n"
            f"[Current Profile State]\n{json.dumps(state_summary, ensure_ascii=False)}\n\n"
            f"[Dialogue History]\n{json.dumps(messages, ensure_ascii=False)}\n\n"
            f"[Latest User Message]\n{user_text}\n\n"
            "Please output JSON following the rules."
        )

        raw = self.api_client.send_request(
            [{"role": "system", "content": self.ANALYSIS_SYS},
             {"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=260
        )
        return self._safe_json(raw)

    def update_state_from_text(self, state: SessionState, messages: List[dict],
                               user_text: str) -> Dict[str, Any]:
        """
        High-level helper: extract patch and apply it to the state in place.
        Returns the full analysis result dict.
        """
        result = self.extract_state(messages, state, user_text)
        patch = result.get("patch") if isinstance(result, dict) else None
        if isinstance(patch, dict):
            state.apply_patch(patch)
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_json(text: str) -> Dict[str, Any]:
        try:
            m = re.search(r"\{.*\}", text, flags=re.S)
            return json.loads(m.group(0) if m else "{}")
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"StateTracker(api_client={self.api_client!r})"
