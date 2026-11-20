"""Tests for workBee email subscription and drop alert digest engine."""
import unittest
from unittest.mock import patch, AsyncMock
from hives.careers.subscriptions import subscribe, digest_preview, SubscribeRequest
from fastapi import HTTPException


class SubscriptionTests(unittest.IsolatedAsyncioTestCase):

    async def test_invalid_email_raises_422(self):
        req = SubscribeRequest(email="not-an-email")
        with self.assertRaises(HTTPException) as ctx:
            await subscribe(req)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("valid email", ctx.exception.detail)

    async def test_valid_email_subscribes_successfully(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        with patch("hives.careers.subscriptions.connection") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_conn
            mock_ctx.return_value.__aexit__.return_value = None

            req = SubscribeRequest(email="Student@University.edu", target_term="summer-2027")
            res = await subscribe(req)
            self.assertTrue(res["ok"])
            self.assertEqual(res["email"], "student@university.edu")
            self.assertIn("Subscribed!", res["message"])
            mock_conn.execute.assert_called_once()
            args = mock_conn.execute.call_args[0]
            self.assertIn("INSERT INTO career_subscriptions", args[0])
            self.assertEqual(args[1], "student@university.edu")

    async def test_digest_preview_generates_featured_drops(self):
        mock_jobs = [
            {
                "id": "gh:apple:123",
                "title": "Software Engineering Intern",
                "company": "Apple",
                "location": "Cupertino, CA",
                "open": True,
                "first_seen": "2026-11-15T00:00:00Z",
                "apply_url": "https://jobs.apple.com/123",
                "workplace": "onsite",
            },
            {
                "id": "gh:google:456",
                "title": "Data Science Fellow",
                "company": "Google",
                "location": "New York, NY",
                "open": True,
                "first_seen": "2026-11-16T00:00:00Z",
                "apply_url": "https://careers.google.com/456",
                "workplace": "hybrid",
            }
        ]
        with patch("hives.careers.catalog.cache", return_value=mock_jobs):
            digest = await digest_preview()
            self.assertTrue(digest["ok"])
            self.assertIn("workBee Weekly", digest["digest_title"])
            self.assertEqual(len(digest["featured_drops"]), 2)
            self.assertEqual(digest["featured_drops"][0]["company"], "Apple")
            self.assertTrue(digest["featured_drops"][0]["is_fresh"])


if __name__ == "__main__":
    unittest.main()
