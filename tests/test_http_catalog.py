import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aiohttp.test_utils import TestClient, TestServer

class HttpCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_add_public_picker_and_pack(self):
        with tempfile.TemporaryDirectory() as store:
            os.environ['WEB_STORAGE_DIR'] = store
            os.environ['WEB_ADMIN_PASSWORD'] = 'test-password'
            import web_server as server
            client = TestClient(TestServer(server.make_app()))
            await client.start_server()
            try:
                row = {'tuong': 'Toro', 'skin': 'Skin HTTP test', 'id': '10509'}
                r = await client.post('/api/admin/notice/catalog', json=row)
                self.assertEqual(r.status, 401)
                r = await client.post('/api/admin/notice/login', json={'password': 'test-password'})
                self.assertEqual(r.status, 200)
                r = await client.post('/api/admin/notice/catalog', json=row)
                self.assertEqual(r.status, 200, await r.text())
                r = await client.get('/api/hero-skins?hero=Toro')
                self.assertEqual(r.headers['Cache-Control'], 'no-store')
                self.assertIn('10509', [s['id'] for s in (await r.json())['skins']])
                r = await client.post('/api/admin/notice/site/packages', json={'name': 'HTTP pack', 'count': 1, 'kind': 'fixed', 'selections': [row]})
                self.assertEqual(r.status, 200, await r.text())
                pack = (await r.json())['quick_packages'][-1]
                r = await client.post('/api/quick-picks', json={'mode': 'package', 'package_id': pack['id']})
                self.assertEqual(r.status, 200, await r.text())
                self.assertEqual((await r.json())['selections'], [row])
                r = await client.post('/api/admin/notice/catalog', json=row)
                self.assertEqual(r.status, 400)
            finally:
                await client.close()
