import asyncio
import os
import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from hives.careers.app import app
from core import db
from hives.careers.accounts import hash_password, verify_password, same_origin, throttle, token_hash


class AccountSecurityTests(unittest.TestCase):
    def test_salted_password_hashes(self):
        a = hash_password("a-long-test-password")
        b = hash_password("a-long-test-password")
        self.assertNotEqual(a, b)
        self.assertNotIn("a-long-test-password", a)
        self.assertTrue(verify_password("a-long-test-password", a))
        self.assertFalse(verify_password("wrong-password", a))
        self.assertFalse(verify_password("wrong-password", "invalid hash"))

    def test_cross_origin_account_changes_are_rejected(self):
        with TestClient(app) as client:
            result = client.post("/api/account/login", json={"username": "test", "password": "test-password"}, headers={"Origin": "https://untrusted.example"})
            self.assertEqual(result.status_code, 403)
            self.assertEqual(result.headers["cache-control"], "no-store")


class AccountThrottleTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_rate_limit(self):
        conn = AsyncMock()
        conn.fetchval.return_value = 11
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("testclient", 123), "scheme": "http", "server": ("testserver", 80)})
        with self.assertRaises(HTTPException) as raised:
            await throttle(conn, request, "login", "example")
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.headers["Retry-After"], "900")


@unittest.skipUnless(os.getenv("CAREERS_DB_TEST") == "1", "requires opt-in local Postgres")
class AccountLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.names = ["test_" + uuid4().hex[:20], "test_" + uuid4().hex[:20]]
        self.a, self.b = TestClient(app), TestClient(app)
        self.a.__enter__(); self.b.__enter__()
        asyncio.run(self.cleanup_attempts())

    async def cleanup_attempts(self):
        conn = await db.connect()
        try:
            from hives.careers.accounts import initialize
            await initialize(conn)
            keys = [token_hash("register:testclient:"), *(token_hash("login:testclient:" + n) for n in self.names)]
            await conn.execute("DELETE FROM career_auth_attempts WHERE key=ANY($1::text[])", keys)
        finally:
            await conn.close()

    def tearDown(self):
        async def cleanup():
            conn = await db.connect()
            try:
                await conn.execute("DELETE FROM career_accounts WHERE username=ANY($1::text[])", self.names)
            finally:
                await conn.close()
            await self.cleanup_attempts()
        asyncio.run(cleanup())
        self.a.__exit__(None, None, None); self.b.__exit__(None, None, None)

    def test_account_profile_preferences_applications_isolation_and_logout(self):
        secret = "a-strong-test-password"
        result = self.a.post("/api/account/register", json={"username": self.names[0], "password": secret})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIn("HttpOnly", result.headers["set-cookie"])
        self.assertIn("SameSite=lax", result.headers["set-cookie"])
        self.assertNotIn("password", result.json())
        original_token = self.a.cookies.get("hivework_session")
        state = self.a.put("/api/account/state", json={"profile": {"major": "Finance", "skills": [{"skill": "Excel", "evidence": "Budget project"}]}, "preferences": {"career_field": "finance", "location": "Boston", "student_year": "first", "opportunity_type": "program", "program_status": "watch"}, "revision": 0})
        self.assertEqual(state.status_code, 200, state.text)
        self.assertEqual(state.json()["revision"], 1)
        stale = self.a.put("/api/account/state", json={"profile": {}, "preferences": {}, "revision": 0})
        self.assertEqual(stale.status_code, 409)
        saved = self.a.put("/api/account/applications/greenhouse:example:123", json={"status": "applied"})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(self.a.put("/api/account/applications/program:nreip",json={"status":"saved"}).status_code,200)
        self.assertEqual(self.b.post("/api/account/register", json={"username": self.names[1], "password": secret}).status_code, 200)
        other = self.b.get("/api/account/session").json()
        self.assertEqual(other["profile"], {})
        self.assertEqual(other["applications"], {})
        session = self.a.get("/api/account/session").json()
        self.assertEqual(session["profile"]["major"], "Finance")
        self.assertEqual(session["preferences"]["location"], "Boston")
        self.assertEqual(session["preferences"]["student_year"], "first")
        self.assertEqual(session["preferences"]["program_status"], "watch")
        self.assertEqual(session["applications"]["program:nreip"], "saved")
        self.assertEqual(session["applications"]["greenhouse:example:123"], "applied")
        self.assertEqual(self.a.post("/api/account/logout").status_code, 200)
        self.assertIsNone(self.a.get("/api/account/session").json()["user"])
        self.assertEqual(self.a.put("/api/account/state", json={"profile": {}, "preferences": {}, "revision": 1}).status_code, 401)
        self.assertEqual(self.a.post("/api/account/login", json={"username": self.names[0], "password": "wrong-password"}).status_code, 401)
        login = self.a.post("/api/account/login", json={"username": self.names[0].upper(), "password": secret})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["profile"]["major"], "Finance")
        self.assertNotEqual(self.a.cookies.get("hivework_session"), original_token)
        self.assertEqual(self.a.post("/api/account/register", json={"username": self.names[0], "password": secret}).status_code, 409)
