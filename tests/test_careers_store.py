"""Optional real-Postgres lifecycle test: CAREERS_DB_TEST=1 python -m unittest discover -s tests."""
import os
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import patch
from uuid import uuid4

from core import db
from hives.careers import store


@unittest.skipUnless(os.getenv("CAREERS_DB_TEST") == "1", "requires opt-in local Postgres")
class StoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_change_close_reopen_and_failure(self):
        await store.initialize()
        employer = {"name": "Integration test", "source": "greenhouse", "board": "test_" + uuid4().hex}
        key = f"greenhouse:{employer['board']}"
        job = {"id": key + ":1", "title": "Test intern", "description": "Python", "role_type": "internship"}
        configured = patch("hives.careers.store.employers", return_value=[employer])
        configured.start()
        try:
            self.assertEqual((await store.save_snapshot(employer, [job]))[0]["kind"], "discovered")
            self.assertEqual(len((await store.catalog(current_only=True))["jobs"]),1)
            conn=await db.connect()
            try:await conn.execute("UPDATE career_jobs SET last_seen=now()-interval '31 minutes' WHERE id=$1",job['id'])
            finally:await conn.close()
            self.assertEqual((await store.catalog(current_only=True))["jobs"],[])
            self.assertEqual(len((await store.catalog())["jobs"]),1)
            self.assertEqual(await store.save_snapshot(employer, [job]), [])
            checked = datetime.now(timezone.utc)
            verification = {"state": "removed", "label": "No longer listed", "checked_at": checked.isoformat()}
            await store.save_verification(job["id"], verification)
            await store.save_verification(job["id"], {**verification, "state": "listed", "checked_at": (checked-timedelta(minutes=1)).isoformat()})
            self.assertEqual((await store.catalog())["jobs"][0]["verification"]["state"], "removed")
            self.assertTrue((await store.get_job(job["id"]))["open"])
            self.assertIsNone(await store.get_job(key + ":missing"))
            job = {**job, "description": "Python and SQL"}
            self.assertEqual((await store.save_snapshot(employer, [job]))[0]["kind"], "changed")
            await store.record_error(employer, "Feed unavailable")
            data = await store.catalog()
            self.assertIn(job["id"], [j["id"] for j in data["jobs"]])
            self.assertEqual(next(b for b in data["boards"] if b["key"] == key)["error"], "Feed unavailable")
            self.assertEqual((await store.save_snapshot(employer, []))[0]["kind"], "closed")
            self.assertNotIn(job["id"], [j["id"] for j in (await store.catalog())["jobs"]])
            self.assertEqual((await store.save_snapshot(employer, [job]))[0]["kind"], "reopened")
            self.assertIsNone(next(b for b in (await store.catalog())["boards"] if b["key"] == key)["error"])
        finally:
            configured.stop()
            # Delete only this test's uniquely named records.
            conn = await db.connect()
            try:
                await conn.execute("DELETE FROM career_jobs WHERE board_key=$1", key)
                await conn.execute("DELETE FROM career_boards WHERE key=$1", key)
            finally:
                await conn.close()


if __name__ == "__main__":
    unittest.main()
