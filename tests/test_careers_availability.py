import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from dashboard.app import app
from hives.careers import availability as module
from hives.careers.matching import Profile, match

EMPLOYER = {'name': 'Example', 'source': 'greenhouse', 'board': 'example'}
JOB = {'id': 'greenhouse:example:123', 'source': 'greenhouse', 'board': 'example', 'description': '', 'company': 'Example'}


class AvailabilityTests(unittest.TestCase):
    def test_freshness_and_failed_checks_do_not_claim_closed(self):
        now = datetime.now(timezone.utc)
        job = {**JOB, 'last_seen': now.isoformat()}
        self.assertEqual(module.availability(job, now=now)['state'], 'listed')
        self.assertEqual(module.availability(job, {'error': 'Timeout'}, now)['state'], 'unavailable')
        job['last_seen'] = (now-timedelta(hours=1)).isoformat()
        self.assertEqual(module.availability(job, now=now)['state'], 'stale')
        self.assertEqual(module.availability({**job, 'source': 'simplify'}, now=now)['state'], 'community')
        self.assertEqual(module.availability({**job, 'open': False}, now=now)['state'], 'removed')
        self.assertEqual(module.availability({**JOB, 'last_seen': 'bad'}, now=now)['state'], 'stale')

    def test_saved_verification_expires_and_newer_snapshot_wins(self):
        now = datetime.now(timezone.utc)
        verification = {'state': 'removed', 'checked_at': now.isoformat()}
        job = {**JOB, 'last_seen': (now-timedelta(minutes=1)).isoformat(), 'verification': verification}
        self.assertEqual(module.availability(job, now=now)['state'], 'removed')
        self.assertEqual(module.availability({**job, 'last_seen': (now+timedelta(seconds=1)).isoformat()}, now=now+timedelta(seconds=2))['state'], 'listed')
        self.assertEqual(module.availability(job, now=now+timedelta(hours=1))['state'], 'stale')

    def test_weighted_explanation_and_unverified_evidence(self):
        result = match({'description': 'Requirements\nPython and SQL required\nPreferred\nReact preferred'}, Profile(skills='Python\nReact | Built a website'))
        self.assertEqual(result['score'], 60)
        self.assertEqual(result['breakdown']['earned_weight'], 3)
        self.assertEqual(result['breakdown']['total_weight'], 5)
        self.assertEqual(result['breakdown']['required'], {'matched': 1, 'total': 2})
        self.assertEqual(result['breakdown']['missing_required'], ['SQL'])
        self.assertEqual(result['breakdown']['self_reported'], 1)

    def test_verification_endpoint_uses_stored_job_only(self):
        with TestClient(app) as client, patch('hives.careers.api.store.get_job', new=AsyncMock(return_value=JOB)), patch('hives.careers.api.verify', new=AsyncMock(return_value={'state': 'listed', 'checked_at': datetime.now(timezone.utc).isoformat()})) as verify, patch('hives.careers.api.store.save_verification', new=AsyncMock()) as save:
            r = client.post('/api/careers/verify', json={'job_id': JOB['id'], 'url': 'http://localhost/private'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['cache-control'], 'no-store')
            verify.assert_awaited_once_with(JOB)
            save.assert_awaited_once_with(JOB['id'], r.json())
        with TestClient(app) as client, patch('hives.careers.api.store.get_job', new=AsyncMock(return_value=None)):
            self.assertEqual(client.post('/api/careers/verify', json={'job_id': 'missing'}).status_code, 404)


class LiveVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        module._CACHE.clear()

    async def test_feed_membership_and_board_cache(self):
        with patch.object(module, 'employers', return_value=[EMPLOYER]), patch.object(module, 'fetch_board', new=AsyncMock(return_value=[JOB])) as fetch:
            self.assertEqual((await module.verify(JOB))['state'], 'listed')
            self.assertEqual((await module.verify({**JOB, 'id': 'missing'}))['state'], 'removed')
            self.assertEqual(fetch.await_count, 1)

    async def test_source_failure_is_unknown_and_does_not_close(self):
        with patch.object(module, 'employers', return_value=[EMPLOYER]), patch.object(module, 'fetch_board', new=AsyncMock(side_effect=httpx.ReadTimeout('timeout'))):
            self.assertEqual((await module.verify(JOB))['state'], 'unavailable')

    async def test_community_is_never_employer_verified_and_unknown_boards_do_not_fetch(self):
        community = {**JOB, 'source': 'simplify'}
        with patch.object(module, 'employers', return_value=[{**EMPLOYER, 'source': 'simplify'}]), patch.object(module, 'fetch_board', new=AsyncMock(return_value=[community])) as fetch:
            self.assertEqual((await module.verify(community))['state'], 'community')
            self.assertEqual((await module.verify({**JOB, 'board': 'untrusted'}))['state'], 'unsupported')
            self.assertEqual(fetch.await_count, 1)
