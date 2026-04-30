# tests/test_unit.py - Unit tests for all core OOP classes
# -*- coding: utf-8 -*-
"""
Run from the chatagent/ directory:
    python -m pytest tests/test_unit.py -v

Or directly:
    python tests/test_unit.py
"""

import os
import sys
import tempfile
import time
import unittest

# ── Path setup: make chatagent/ importable without installing as a package ──
_here     = os.path.dirname(__file__)             # chatagent/tests/
_chatagent = os.path.dirname(_here)               # chatagent/
if _chatagent not in sys.path:
    sys.path.insert(0, _chatagent)

from message       import Message
from session_state import SessionState
from user          import User
from domain.user   import UserAccount
from domain.session import SessionMeta
from storage_manager import StorageManager
from log_manager   import LogManager
from agent_rules   import ConversationPolicy
from exceptions    import (
    InvalidStateError, UserAlreadyExistsError, UserNotFoundError,
    PasswordError, ChatBotError,
)
from abstractions  import BaseStorage, BaseLogger, BaseApiClient, BaseUser


# ══════════════════════════════════════════════════════════════════════════════
#  Message
# ══════════════════════════════════════════════════════════════════════════════

class TestMessage(unittest.TestCase):

    def _make(self, sender="user", content="hello", ts="2026-01-01T10:00:00"):
        return Message("sess-1", sender, content, timestamp=ts)

    def test_creation_stores_fields(self):
        m = self._make()
        self.assertEqual(m.session_id, "sess-1")
        self.assertEqual(m.sender, "user")
        self.assertEqual(m.content, "hello")
        self.assertEqual(m.timestamp, "2026-01-01T10:00:00")

    def test_to_dict_keys(self):
        m = self._make()
        d = m.to_dict()
        self.assertIn("role", d)
        self.assertIn("content", d)
        self.assertIn("ts", d)
        self.assertEqual(d["role"], "user")

    def test_from_dict_roundtrip(self):
        m = self._make()
        m2 = Message.from_dict(m.to_dict())
        self.assertEqual(m2.sender, m.sender)
        self.assertEqual(m2.content, m.content)
        self.assertEqual(m2.timestamp, m.timestamp)

    def test_eq_same_fields(self):
        m1 = self._make()
        m2 = self._make()
        self.assertEqual(m1, m2)

    def test_eq_different_content(self):
        m1 = self._make(content="hello")
        m2 = self._make(content="world")
        self.assertNotEqual(m1, m2)

    def test_hash_consistency(self):
        m1 = self._make()
        m2 = self._make()
        self.assertEqual(hash(m1), hash(m2))
        s = {m1, m2}
        self.assertEqual(len(s), 1)

    def test_lt_chronological(self):
        m_early = self._make(ts="2026-01-01T09:00:00")
        m_late  = self._make(ts="2026-01-01T11:00:00")
        self.assertLess(m_early, m_late)
        self.assertGreater(m_late, m_early)

    def test_sorted(self):
        msgs = [
            self._make(ts="2026-01-01T12:00:00"),
            self._make(ts="2026-01-01T08:00:00"),
            self._make(ts="2026-01-01T10:00:00"),
        ]
        ordered = sorted(msgs)
        self.assertEqual(ordered[0].timestamp, "2026-01-01T08:00:00")
        self.assertEqual(ordered[-1].timestamp, "2026-01-01T12:00:00")

    def test_str_truncates_long_content(self):
        m = self._make(content="A" * 80)
        s = str(m)
        self.assertIn("[user]", s)
        self.assertIn("...", s)

    def test_str_short_content(self):
        m = self._make(content="Hi")
        self.assertIn("Hi", str(m))

    def test_default_timestamp_set(self):
        m = Message("s", "user", "content")
        self.assertTrue(m.timestamp)  # non-empty


# ══════════════════════════════════════════════════════════════════════════════
#  SessionState
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionState(unittest.TestCase):

    def test_default_values(self):
        s = SessionState("abc")
        self.assertEqual(s.session_id, "abc")
        self.assertEqual(s.risk_flags, "green")
        self.assertEqual(s.conversation_mode, "emotion")
        self.assertEqual(s.turns, 0)
        self.assertFalse(bool(s))          # __bool__: 0 turns → falsy

    def test_bool_true_after_turns(self):
        s = SessionState("abc")
        s.increment_turns()
        self.assertTrue(bool(s))

    def test_risk_flags_valid(self):
        s = SessionState("x")
        for v in ("green", "yellow", "red"):
            s.risk_flags = v
            self.assertEqual(s.risk_flags, v)

    def test_risk_flags_invalid_raises(self):
        s = SessionState("x")
        with self.assertRaises((InvalidStateError, ValueError)):
            s.risk_flags = "orange"

    def test_conversation_mode_valid(self):
        s = SessionState("x")
        for v in ("emotion", "info", "career", "risk"):
            s.conversation_mode = v
            self.assertEqual(s.conversation_mode, v)

    def test_conversation_mode_invalid_raises(self):
        s = SessionState("x")
        with self.assertRaises((InvalidStateError, ValueError)):
            s.conversation_mode = "unknown"

    def test_apply_patch_basic(self):
        s = SessionState("x")
        s.apply_patch({"goal": "reduce stress", "risk_flags": "yellow"})
        self.assertEqual(s.goal, "reduce stress")
        self.assertEqual(s.risk_flags, "yellow")

    def test_apply_patch_invalid_risk_ignored(self):
        s = SessionState("x")
        s.apply_patch({"risk_flags": "purple"})  # invalid → ignored
        self.assertEqual(s.risk_flags, "green")

    def test_apply_patch_keywords_accumulate(self):
        s = SessionState("x")
        s.apply_patch({"state_keywords": ["anxiety", "work"]})
        s.apply_patch({"state_keywords": ["work", "sleep"]})
        self.assertIn("anxiety", s.state_keywords)
        self.assertIn("sleep", s.state_keywords)
        self.assertEqual(s.state_keywords.count("work"), 1)  # deduplicated

    def test_to_dict_from_dict_roundtrip(self):
        s = SessionState("roundtrip")
        s.apply_patch({"goal": "test", "risk_flags": "yellow"})
        s.increment_turns()
        d = s.to_dict()
        s2 = SessionState.from_dict(d)
        self.assertEqual(s2.session_id, s.session_id)
        self.assertEqual(s2.risk_flags, "yellow")
        self.assertEqual(s2.turns, 1)
        self.assertEqual(s2.goal, "test")

    def test_eq_same_session_id(self):
        s1 = SessionState("shared")
        s2 = SessionState("shared")
        self.assertEqual(s1, s2)

    def test_eq_different_session_id(self):
        self.assertNotEqual(SessionState("a"), SessionState("b"))

    def test_hash_in_set(self):
        s1 = SessionState("dup")
        s2 = SessionState("dup")
        self.assertEqual(len({s1, s2}), 1)

    def test_str_contains_session_id(self):
        s = SessionState("my-session-id")
        self.assertIn("my-sessi", str(s))

    def test_can_send_proactive(self):
        s = SessionState("x")
        s.increment_turns()
        now = time.time()
        self.assertTrue(s.can_send_proactive(now, cooldown_sec=60))
        s.record_proactive_message(now)
        self.assertFalse(s.can_send_proactive(now + 10, cooldown_sec=60))
        self.assertTrue(s.can_send_proactive(now + 61, cooldown_sec=60))

    def test_question_suppression(self):
        s = SessionState("x")
        s.request_question_suppression(3)
        self.assertEqual(s.suppress_questions_remaining, 3)
        s.consume_question_suppression()
        self.assertEqual(s.suppress_questions_remaining, 2)

    def test_micro_intervention_cooldown(self):
        s = SessionState("x")
        s.increment_turns()
        self.assertTrue(s.can_add_micro_intervention())
        s.mark_micro_intervention_used()
        self.assertFalse(s.can_add_micro_intervention(cooldown_turns=2))
        s.increment_turns(); s.increment_turns()
        self.assertTrue(s.can_add_micro_intervention(cooldown_turns=2))


# ══════════════════════════════════════════════════════════════════════════════
#  User
# ══════════════════════════════════════════════════════════════════════════════

class TestUser(unittest.TestCase):

    def test_default_role_user(self):
        u = User("u1", "alice")
        self.assertEqual(u.role, "user")
        self.assertFalse(u.is_admin())
        self.assertFalse(u.can_view_report())

    def test_admin_role(self):
        u = User("u2", "bob", role="admin")
        self.assertTrue(u.is_admin())
        self.assertTrue(u.can_view_report())

    def test_counselor_role(self):
        u = User("u3", "carol", role="counselor")
        self.assertTrue(u.is_admin())

    def test_invalid_role_raises(self):
        with self.assertRaises((InvalidStateError, ValueError)):
            User("u4", "dave", role="superuser")

    def test_role_setter_validates(self):
        u = User("u5", "eve")
        with self.assertRaises((InvalidStateError, ValueError)):
            u.role = "hacker"

    def test_touch_updates_last_active(self):
        u = User("u6", "frank")
        self.assertIsNone(u.last_active)
        u.touch()
        self.assertIsNotNone(u.last_active)

    def test_eq_same_user_id(self):
        u1 = User("same", "alice")
        u2 = User("same", "alice-clone")
        self.assertEqual(u1, u2)

    def test_eq_different_user_id(self):
        self.assertNotEqual(User("a", "x"), User("b", "x"))

    def test_hash_set(self):
        u1 = User("dup", "alice")
        u2 = User("dup", "alice")
        self.assertEqual(len({u1, u2}), 1)

    def test_str_shows_username_and_role(self):
        u = User("u", "gina", role="counselor")
        s = str(u)
        self.assertIn("gina", s)
        self.assertIn("counselor", s)

    def test_to_dict_from_dict_roundtrip(self):
        u = User("uid", "henry", role="admin")
        u.touch()
        d = u.to_dict()
        u2 = User.from_dict(d)
        self.assertEqual(u2.user_id, "uid")
        self.assertEqual(u2.role, "admin")

    def test_user_is_base_user(self):
        u = User("x", "y")
        self.assertIsInstance(u, BaseUser)


# ══════════════════════════════════════════════════════════════════════════════
#  UserAccount (domain)
# ══════════════════════════════════════════════════════════════════════════════

class TestUserAccount(unittest.TestCase):

    def _make(self, uid="u1", username="alice", password="secret"):
        salt = "salt123"
        return UserAccount(
            user_id=uid,
            username=username,
            password_salt=salt,
            password_hash=UserAccount.hash_password(password, salt),
        )

    def test_hash_is_deterministic(self):
        h1 = UserAccount.hash_password("pw", "salt")
        h2 = UserAccount.hash_password("pw", "salt")
        self.assertEqual(h1, h2)

    def test_hash_differs_with_different_salt(self):
        h1 = UserAccount.hash_password("pw", "salt1")
        h2 = UserAccount.hash_password("pw", "salt2")
        self.assertNotEqual(h1, h2)

    def test_verify_correct_password(self):
        acc = self._make(password="correct")
        self.assertTrue(acc.verify_password("correct"))

    def test_verify_wrong_password(self):
        acc = self._make(password="correct")
        self.assertFalse(acc.verify_password("wrong"))

    def test_post_init_rejects_empty_user_id(self):
        with self.assertRaises(ValueError):
            UserAccount(user_id="  ", username="alice",
                        password_salt="s", password_hash="h")

    def test_post_init_rejects_empty_username(self):
        with self.assertRaises(ValueError):
            UserAccount(user_id="u1", username="",
                        password_salt="s", password_hash="h")

    def test_str_hides_credentials(self):
        acc = self._make()
        s = str(acc)
        self.assertNotIn("salt123", s)
        self.assertIn("alice", s)

    def test_hash_entity(self):
        a1 = self._make(uid="same")
        a2 = self._make(uid="same", username="other")
        self.assertEqual(hash(a1), hash(a2))

    def test_is_base_user(self):
        acc = self._make()
        self.assertIsInstance(acc, BaseUser)

    def test_to_dict(self):
        acc = self._make()
        d = acc.to_dict()
        self.assertIn("user_id", d)
        self.assertIn("password_hash", d)


# ══════════════════════════════════════════════════════════════════════════════
#  SessionMeta (domain)
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionMeta(unittest.TestCase):

    def _make(self, updated="2026-01-01T10:00:00"):
        return SessionMeta("sid1", "My chat", "2026-01-01T09:00:00", updated)

    def test_str(self):
        s = str(self._make())
        self.assertIn("My chat", s)

    def test_lt_ordering(self):
        old = self._make(updated="2026-01-01T08:00:00")
        new = self._make(updated="2026-01-01T12:00:00")
        self.assertLess(old, new)
        self.assertGreater(new, old)

    def test_sorted(self):
        metas = [
            self._make(updated="2026-01-03T00:00:00"),
            self._make(updated="2026-01-01T00:00:00"),
            self._make(updated="2026-01-02T00:00:00"),
        ]
        ordered = sorted(metas)
        self.assertEqual(ordered[0].updated_at, "2026-01-01T00:00:00")
        self.assertEqual(ordered[-1].updated_at, "2026-01-03T00:00:00")


# ══════════════════════════════════════════════════════════════════════════════
#  StorageManager
# ══════════════════════════════════════════════════════════════════════════════

class TestStorageManager(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.storage = StorageManager(storage_path=self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_save_and_load_json(self):
        path = os.path.join(self._tmpdir.name, "test.json")
        self.storage.save_json(path, {"key": "value"})
        data = self.storage.load_json(path)
        self.assertEqual(data["key"], "value")

    def test_load_missing_returns_default(self):
        result = self.storage.load_json("/nonexistent/path.json", default=42)
        self.assertEqual(result, 42)

    def test_save_and_load_session(self):
        s = SessionState("test-sess")
        s.apply_patch({"goal": "unit-test", "risk_flags": "yellow"})
        self.storage.save_session(s)
        loaded = self.storage.load_session("test-sess")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.goal, "unit-test")
        self.assertEqual(loaded.risk_flags, "yellow")

    def test_load_nonexistent_session_returns_none(self):
        self.assertIsNone(self.storage.load_session("no-such-id"))

    def test_list_sessions(self):
        for sid in ("a", "b", "c"):
            self.storage.save_session(SessionState(sid))
        ids = self.storage.list_sessions()
        self.assertIn("a", ids)
        self.assertIn("c", ids)

    def test_len(self):
        self.assertEqual(len(self.storage), 0)
        self.storage.save_session(SessionState("s1"))
        self.assertEqual(len(self.storage), 1)
        self.storage.save_session(SessionState("s2"))
        self.assertEqual(len(self.storage), 2)

    def test_contains_true(self):
        self.storage.save_session(SessionState("present"))
        self.assertIn("present", self.storage)

    def test_contains_false(self):
        self.assertNotIn("absent", self.storage)

    def test_is_base_storage(self):
        self.assertIsInstance(self.storage, BaseStorage)

    def test_str(self):
        s = str(self.storage)
        self.assertIn("StorageManager", s)
        self.assertIn("sessions=0", s)


# ══════════════════════════════════════════════════════════════════════════════
#  LogManager
# ══════════════════════════════════════════════════════════════════════════════

class TestLogManager(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        log_path = os.path.join(self._tmpdir.name, "test.jsonl")
        self.log = LogManager(log_file=log_path)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _state(self, sid="s1"):
        return SessionState(sid)

    def test_log_turn_and_get_logs(self):
        state = self._state()
        self.log.log_turn("hello", "hi there", state)
        logs = self.log.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["user"], "hello")
        self.assertEqual(logs[0]["reply"], "hi there")

    def test_get_logs_filtered_by_session(self):
        s1 = self._state("sess-A")
        s2 = self._state("sess-B")
        self.log.log_turn("msg-A", "rep-A", s1)
        self.log.log_turn("msg-B", "rep-B", s2)
        only_a = self.log.get_logs(session_id="sess-A")
        self.assertEqual(len(only_a), 1)
        self.assertEqual(only_a[0]["user"], "msg-A")

    def test_len(self):
        self.assertEqual(len(self.log), 0)
        self.log.log_turn("a", "b", self._state())
        self.assertEqual(len(self.log), 1)
        self.log.log_turn("c", "d", self._state())
        self.assertEqual(len(self.log), 2)

    def test_iter(self):
        self.log.log_turn("x", "y", self._state())
        self.log.log_turn("p", "q", self._state())
        records = list(self.log)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["user"], "x")

    def test_get_logs_limit(self):
        for i in range(10):
            self.log.log_turn(f"u{i}", f"r{i}", self._state())
        limited = self.log.get_logs(limit=3)
        self.assertEqual(len(limited), 3)

    def test_log_message(self):
        m = Message("s1", "user", "test content")
        self.log.log_message(m)
        logs = self.log.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["content"], "test content")

    def test_is_base_logger(self):
        self.assertIsInstance(self.log, BaseLogger)

    def test_str(self):
        s = str(self.log)
        self.assertIn("LogManager", s)
        self.assertIn("records=0", s)


# ══════════════════════════════════════════════════════════════════════════════
#  ConversationPolicy
# ══════════════════════════════════════════════════════════════════════════════

class TestConversationPolicy(unittest.TestCase):

    def setUp(self):
        self.policy = ConversationPolicy()

    def _state(self, **kw):
        s = SessionState("p")
        for k, v in kw.items():
            # Use private backing stores to bypass property setters
            if k == "risk_flags":
                s._risk_flags = v
            elif k == "conversation_mode":
                s._conversation_mode = v
            else:
                setattr(s, k, v)
        return s

    def test_classify_mode_risk_pattern(self):
        s = self._state()
        mode = self.policy.classify_mode("I want to die", s)
        self.assertEqual(mode, "risk")

    def test_classify_mode_career(self):
        s = self._state()
        mode = self.policy.classify_mode("should I switch jobs?", s)
        self.assertEqual(mode, "career")

    def test_classify_mode_emotion_default(self):
        s = self._state()
        mode = self.policy.classify_mode("I feel so tired today", s)
        self.assertEqual(mode, "emotion")

    def test_classify_mode_info(self):
        s = self._state()
        mode = self.policy.classify_mode("what is the meaning of anxiety?", s)
        self.assertEqual(mode, "info")

    def test_user_requests_no_questions_true(self):
        self.assertTrue(
            self.policy.user_requests_no_questions("stop asking me questions")
        )

    def test_user_requests_no_questions_false(self):
        self.assertFalse(
            self.policy.user_requests_no_questions("I feel lonely today")
        )

    def test_should_ask_question_suppressed(self):
        s = self._state()
        s.request_question_suppression(4)
        result = self.policy.should_ask_question("tell me more", s, "career")
        self.assertFalse(result)

    def test_finalize_reply_updates_streak(self):
        s = self._state()
        self.policy.finalize_reply("hello", "emotion", "I see.", s)
        self.assertEqual(s.assistant_question_streak, 0)

    def test_apply_suppression_trigger(self):
        s = self._state()
        self.policy.apply_user_suppression_trigger(s, "just tell me directly")
        self.assertGreater(s.suppress_questions_remaining, 0)

    def test_mode_system_addon_returns_string(self):
        for mode in ("emotion", "info", "career", "risk"):
            addon = ConversationPolicy.mode_system_addon(mode)
            self.assertIsInstance(addon, str)
            self.assertTrue(len(addon) > 0)


# ══════════════════════════════════════════════════════════════════════════════
#  Custom exceptions
# ══════════════════════════════════════════════════════════════════════════════

class TestExceptions(unittest.TestCase):

    def test_hierarchy(self):
        from exceptions import (
            AuthError, UserAlreadyExistsError, UserNotFoundError,
            PasswordError, SessionError, SessionNotFoundError,
            SessionOwnershipError, InvalidStateError,
        )
        # Each custom error is-a ChatBotError
        self.assertTrue(issubclass(AuthError, ChatBotError))
        self.assertTrue(issubclass(UserAlreadyExistsError, AuthError))
        self.assertTrue(issubclass(SessionNotFoundError, SessionError))

    def test_backward_compat_value_error(self):
        # UserAlreadyExistsError inherits ValueError — old catch still works
        err = UserAlreadyExistsError("already exists")
        self.assertIsInstance(err, ValueError)

    def test_backward_compat_lookup_error(self):
        err = UserNotFoundError("not found")
        self.assertIsInstance(err, LookupError)

    def test_backward_compat_permission_error(self):
        err = PasswordError("wrong password")
        self.assertIsInstance(err, PermissionError)

    def test_code_field(self):
        err = ChatBotError("oops", code="E001")
        self.assertIn("E001", str(err))

    def test_repr(self):
        err = UserNotFoundError("test")
        self.assertIn("UserNotFoundError", repr(err))


# ══════════════════════════════════════════════════════════════════════════════
#  Abstractions (ABC enforcement)
# ══════════════════════════════════════════════════════════════════════════════

class TestAbstractions(unittest.TestCase):

    def test_base_storage_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            BaseStorage()  # type: ignore

    def test_base_logger_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            BaseLogger()   # type: ignore

    def test_base_api_client_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            BaseApiClient()  # type: ignore

    def test_base_user_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            BaseUser()  # type: ignore

    def test_storage_manager_is_abstract_base(self):
        from storage_manager import StorageManager
        self.assertTrue(issubclass(StorageManager, BaseStorage))

    def test_log_manager_is_abstract_base(self):
        self.assertTrue(issubclass(LogManager, BaseLogger))

    def test_api_client_is_abstract_base(self):
        from api_client import ApiClient
        self.assertTrue(issubclass(ApiClient, BaseApiClient))

    def test_user_is_base_user(self):
        from user import User
        self.assertTrue(issubclass(User, BaseUser))

    def test_user_account_is_base_user(self):
        from domain.user import UserAccount
        self.assertTrue(issubclass(UserAccount, BaseUser))


if __name__ == "__main__":
    unittest.main(verbosity=2)
