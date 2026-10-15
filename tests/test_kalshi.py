import os
import unittest
import base64
from unittest.mock import patch

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from dashboard.app import app
from hives.kalshi import client


class DemoClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        client._cache = None
        client._retry_at = 0
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.env = patch.dict(os.environ, {
            'KALSHI_API_KEY_ID': 'test-key',
            'KALSHI_PRIVATE_KEY': self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_signing_pagination_and_cache(self):
        requests = []
        def handler(request):
            requests.append(request)
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.url.host, 'demo-api.kalshi.co')
            stamp = request.headers['KALSHI-ACCESS-TIMESTAMP']
            self.key.public_key().verify(base64.b64decode(request.headers['KALSHI-ACCESS-SIGNATURE']), (stamp+'GET'+request.url.path).encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
            endpoint = request.url.path.rsplit('/', 1)[-1]
            data = {'balance': {'balance': 9991, 'portfolio_value': 9}, 'orders': {'orders': []}, 'fills': {'fills': []}}
            if endpoint == 'positions':
                data[endpoint] = {'market_positions': [{'ticker': 'SECOND'}]} if request.url.params.get('cursor') else {'market_positions': [{'ticker': 'FIRST'}], 'cursor': 'next'}
            return httpx.Response(200, json=data[endpoint])
        real = httpx.AsyncClient
        with patch.object(client.httpx, 'AsyncClient', side_effect=lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
            data = await client.portfolio()
            self.assertEqual(len(data['positions']), 2)
            self.assertEqual(data['cash_cents'], 9991)
            self.assertIs(await client.portfolio(), data)
            self.assertEqual(len(requests), 5)

    async def test_rate_limit_backoff(self):
        real = httpx.AsyncClient
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429)
        with patch.object(client.httpx, 'AsyncClient', side_effect=lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
            for _ in range(2):
                with self.assertRaises(client.DemoUnavailable):
                    await client.portfolio()
        self.assertEqual(len(calls), 1)

    async def test_invalid_credentials_fail_without_leak(self):
        os.environ['KALSHI_PRIVATE_KEY'] = 'sensitive-invalid-key'
        with TestClient(app) as web:
            response = web.get('/api/kalshi/portfolio')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('sensitive-invalid-key', response.text)


if __name__ == '__main__':
    unittest.main()

class ReturnsTests(unittest.TestCase):
    def test_gains_losses_and_fractional_cost(self):
        positions = [{'market_exposure_dollars': '0.938600', 'fees_paid_dollars': '0.053300'}, {'market_exposure_dollars': '0.967200', 'fees_paid_dollars': '0.025800'}]
        result = client.open_position_returns(positions, 210)
        self.assertAlmostEqual(result['unrealized_pnl_cents'], 19.42)
        self.assertAlmostEqual(result['open_market_fees_cents'], 7.91)
        self.assertAlmostEqual(client.open_position_returns(positions, 180)['unrealized_pnl_cents'], -10.58)

    def test_missing_cost_is_not_zero(self):
        self.assertIsNone(client.open_position_returns([{}], 100)['unrealized_pnl_cents'])
        result = client.open_position_returns([], 0)
        self.assertEqual(result['unrealized_pnl_cents'], 0)
        self.assertIsNone(result['unrealized_return_percent'])
