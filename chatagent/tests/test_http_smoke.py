import uuid
import unittest

from fastapi.testclient import TestClient

from chatagent.api_server import app


class HttpSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.username = f"smoke_{uuid.uuid4().hex[:6]}"
        self.password = "pass1234"

    def test_register_login_chat_session_flow(self):
        r = self.client.post("/auth/register", json={"username": self.username, "password": self.password})
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        user_id = payload["user_id"]
        session_id = payload["session_id"]

        duplicate = self.client.post("/auth/register", json={"username": self.username, "password": self.password})
        self.assertEqual(duplicate.status_code, 409)

        chat = self.client.post("/chat", json={"text": "hello", "user_id": user_id, "session_id": session_id})
        self.assertEqual(chat.status_code, 200)
        self.assertTrue("reply_ts" in chat.json())

        create = self.client.post(f"/users/{user_id}/sessions/new", json={"title": "new"})
        self.assertEqual(create.status_code, 200)
        new_sid = create.json()["session_id"]

        history = self.client.get(f"/users/{user_id}/sessions/{new_sid}/history")
        self.assertEqual(history.status_code, 200)

        blocked = self.client.post("/chat", json={"text": "x", "user_id": user_id, "session_id": "user-hack-123"})
        self.assertEqual(blocked.status_code, 403)


if __name__ == "__main__":
    unittest.main()

