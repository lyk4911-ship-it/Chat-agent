# admin_monitor.py - AdminMonitor class for backend session monitoring
# -*- coding: utf-8 -*-

import json
import os
from typing import Any, Dict, List, Optional

from api_client import ApiClient
from storage_manager import StorageManager
from log_manager import LogManager
from session_state import SessionState


class AdminMonitor:
    """
    Provides backend monitoring capabilities for administrators and counselors.
    Reads session data from StorageManager and generates summary reports
    via the LLM API. Supports listing active sessions and flagging risks.
    """

    REPORT_SYS = (
        "You are a counseling supervision assistant. Generate a structured report from the transcript and profile.\n"
        "Analyze only. Do not role-play dialogue, and do not fabricate facts not present in the conversation.\n"
        "The report must contain all five numbered sections:\n"
        "1. Main observed issues\n"
        "2. Emotional state and risk assessment\n"
        "3. Core concerns and goals\n"
        "4. Selected interventions and progress\n"
        "5. Follow-up recommendations\n"
    )

    EMERGENCY_SYS = (
        "You are a crisis assessment assistant. Based on the transcript excerpt and generated profile, output a concise crisis summary including:\n"
        "- key statements that triggered risk concern\n"
        "- current risk-level judgment\n"
        "- recommended immediate intervention steps\n"
        "Do not assume facts not present in the conversation."
    )

    def __init__(self, api_client: ApiClient, storage: StorageManager,
                 log_manager: LogManager):
        self.api_client: ApiClient = api_client
        self.storage: StorageManager = storage
        self.log_manager: LogManager = log_manager

    # ------------------------------------------------------------------
    # Session listing
    # ------------------------------------------------------------------

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Return a summary list of all saved sessions, sorted by risk level.
        Each entry includes session_id, risk_flags, turns, goal, and updated_at.
        """
        session_ids = self.storage.list_sessions()
        summaries = []
        for sid in session_ids:
            state = self.storage.load_session(sid)
            if state:
                summaries.append({
                    "session_id": sid,
                    "risk_flags": state.risk_flags,
                    "turns": state.turns,
                    "goal": state.goal,
                    "problem_category": state.problem_category,
                    "severity_score": state.severity_score,
                    "updated_at": state.updated_at,
                })
        # Sort: red first, then yellow, then green
        priority = {"red": 0, "yellow": 1, "green": 2}
        summaries.sort(key=lambda x: priority.get(x.get("risk_flags", "green"), 2))
        return summaries

    def get_high_risk_sessions(self) -> List[Dict[str, Any]]:
        """Return only sessions flagged as red or yellow risk."""
        return [s for s in self.list_active_sessions()
                if s.get("risk_flags") in ("red", "yellow")]

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self, session_id: str) -> str:
        """
        Generate a structured counselor report for the given session
        by reading the session log and calling the LLM.
        """
        state = self.storage.load_session(session_id)
        if not state:
            return f"[Error] Session '{session_id}' not found."

        logs = self.log_manager.get_logs(session_id=session_id, limit=120)
        transcript = self._logs_to_transcript(logs)

        tags = {
            "state_keywords": state.state_keywords,
            "goal": state.goal,
            "problem_category": state.problem_category,
            "severity_score": state.severity_score,
            "constraints": state.constraints,
            "risk_flags": state.risk_flags,
            "current_strategy": state.current_strategy,
            "last_plan": state.last_plan,
        }

        prompt = (
            f"[Full Conversation Transcript]\n{transcript}\n\n"
            f"[System Profile Tags]\n{json.dumps(tags, ensure_ascii=False)}\n\n"
            "Please output the report in the required five-section structure."
        )

        raw = self.api_client.send_request(
            [{"role": "system", "content": self.REPORT_SYS},
             {"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=900
        )
        raw = (raw or "").strip()

        # Validate five-part structure, retry once if malformed
        if not self._valid_report(raw):
            repair_sys = (
                self.REPORT_SYS +
                "\n\n[Important] Rewrite the report and strictly include sections 1 through 5. Do not omit any section."
            )
            raw2 = self.api_client.send_request(
                [{"role": "system", "content": repair_sys},
                 {"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=900
            )
            raw2 = (raw2 or "").strip()
            if self._valid_report(raw2):
                return raw2
            return "(Report format validation failed; raw output)\n\n" + raw[:800]

        return raw

    def generate_emergency_report(self, session_id: str) -> str:
        """Generate a concise emergency/crisis summary for a high-risk session."""
        state = self.storage.load_session(session_id)
        if not state:
            return f"[Error] Session '{session_id}' not found."

        logs = self.log_manager.get_logs(session_id=session_id, limit=80)
        transcript = self._logs_to_transcript(logs)

        persona = {
            "goal": state.goal,
            "problem_category": state.problem_category,
            "severity_score": state.severity_score,
            "time_available_min": state.time_available_min,
            "constraints": state.constraints,
            "state_keywords": state.state_keywords,
        }

        prompt = (
            f"[Dialogue Excerpt]\n{transcript}\n\n"
            f"[Generated Profile]\n{json.dumps(persona, ensure_ascii=False)}"
        )

        summary = self.api_client.send_request(
            [{"role": "system", "content": self.EMERGENCY_SYS},
             {"role": "user", "content": prompt}],
            temperature=0.4, max_tokens=420
        )

        lines = [
            "====== RED ALERT SUMMARY ======",
            f"Session ID : {session_id}",
            f"Risk Level : {state.risk_flags}",
            "",
            (summary or "").strip(),
            "",
            "[Profile Highlights]",
            json.dumps(persona, ensure_ascii=False),
            "====================================",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _logs_to_transcript(logs: List[Dict[str, Any]], max_chars: int = 8000) -> str:
        lines = []
        for rec in logs:
            if "user" in rec and "reply" in rec:
                lines.append(f"[user] {rec['user']}")
                lines.append(f"[assistant] {rec['reply']}")
            elif rec.get("sender") and rec.get("content"):
                lines.append(f"[{rec['sender']}] {rec['content']}")
        transcript = "\n".join(lines)
        if len(transcript) > max_chars:
            transcript = transcript[-max_chars:]
        return transcript

    @staticmethod
    def _valid_report(text: str) -> bool:
        """Check that the report contains all five required sections."""
        t = (text or "").strip()
        return all(f"{i}." in t for i in range(1, 6)) and (
            "observ" in t.lower() or "issue" in t.lower() or "problem" in t.lower()
        )

    def __str__(self) -> str:
        """Human-readable summary: active session count and high-risk count."""
        try:
            active = len(self.list_active_sessions())
            high_risk = len(self.get_high_risk_sessions())
        except Exception:
            active = high_risk = -1
        return (
            f"AdminMonitor(active_sessions={active}, "
            f"high_risk={high_risk})"
        )

    def __repr__(self) -> str:
        return f"AdminMonitor(storage={self.storage!r})"
