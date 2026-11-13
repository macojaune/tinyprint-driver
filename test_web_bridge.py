"""Optional API integration checks. Run with TINYPOS_PATH and requirements-web installed."""
import asyncio
import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image
from web_bridge import BridgeRuntime


class RuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_mosaic_and_legacy_operations_share_one_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = BridgeRuntime(directory)
            active = maximum = 0
            async def operation():
                nonlocal active, maximum
                active += 1
                maximum = max(active, maximum)
                await asyncio.sleep(.01)
                active -= 1
                return 0
            await asyncio.gather(runtime.transmit(operation), runtime.transmit(operation))
            self.assertEqual(maximum, 1)
            self.assertIsNone(runtime.active)


@unittest.skipUnless(os.getenv('TINYPOS_PATH'), 'Set TINYPOS_PATH for optional TinyPOS API checks')
class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from web_bridge import build_app
        cls.directory = tempfile.TemporaryDirectory()
        cls.app = build_app(os.environ['TINYPOS_PATH'], cls.directory.name, 'test-device')
        cls.client = TestClient(cls.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.directory.cleanup()

    def setUp(self):
        self.client.cookies.clear()

    def login(self):
        with patch('server.routes.web.get_admin_username', return_value='test-admin'), patch('server.routes.web.get_admin_password', return_value='test-password'):
            response = self.client.post('/login', data={'username':'test-admin','password':'test-password'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('driver_session', self.client.cookies)

    def photo(self):
        data = io.BytesIO()
        Image.new('RGB', (256, 160), 'white').save(data, format='PNG')
        return data.getvalue()

    def prepare(self):
        response = self.client.post('/api/internal/bands/prepare', files={'file':('test.png', self.photo(), 'image/png')}, data={'count':2})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_anonymous_and_forged_upstream_cookie_are_denied(self):
        for cookie in (None, 'admin_authenticated'):
            if cookie:
                self.client.cookies.set('tinypos_session', cookie)
            response = self.client.get('/api/internal/bands/does-not-exist', follow_redirects=False)
            self.assertIn(response.status_code, (307,401))

    def test_classic_internal_api_requires_the_additional_session_too(self):
        self.client.cookies.set('tinypos_session','admin_authenticated')
        with patch('server.routes.internal_api.get_system_printer_status',AsyncMock(return_value={'status':'offline'})):
            self.assertEqual(self.client.get('/api/internal/status',follow_redirects=False).status_code,401)

    def test_prepare_preview_zip_and_native_layout_without_bluetooth(self):
        self.login()
        with patch('web_bridge.driver.connect', side_effect=AssertionError('Preview attempted BLE')):
            series = self.prepare()
            self.assertEqual(series['count'], 2)
            self.assertEqual(series['size_mm'], [96,60])
            self.assertEqual(series['settings']['energy'],8000)
            prefix = '/api/internal/bands/'+series['id']
            self.assertEqual(self.client.get(prefix+'/preview').headers['content-type'],'image/png')
            self.assertEqual(self.client.get(prefix+'/download').content[:2],b'PK')
            page = self.client.get('/photo-bands')
            self.assertEqual(page.status_code,200)
            self.assertIn('Atelier photo en bandes',page.text)
            self.assertIn('navbar',page.text)

    def test_reject_bad_image_invalid_params_and_cross_origin(self):
        self.login()
        self.assertEqual(self.client.post('/api/internal/bands/prepare',files={'file':('bad.png',b'not an image')}).status_code,422)
        self.assertEqual(self.client.post('/api/internal/bands/prepare',files={'file':('test.png',self.photo())},data={'count':0}).status_code,422)
        self.assertEqual(self.client.post('/api/internal/bands/prepare',headers={'Origin':'https://untrusted.example'},files={'file':('test.png',self.photo())}).status_code,403)

    def test_interrupted_series_exposes_progress_after_restart(self):
        import json
        from web_bridge import driver
        self.login()
        series = self.prepare()
        folder = self.app.state.bands.folder(series['id'])
        driver.save_state(folder,dict(done=[1],failed=2))
        (folder/'job.json').write_text(json.dumps({'status':'sending'}))
        result = self.client.get('/api/internal/bands/'+series['id']).json()
        self.assertEqual(result['status'],'interrupted')
        self.assertEqual(result['done'],[1])
        self.assertEqual(result['direction'],'vertical')

    def test_resume_passes_resume_flag_and_cancel_stops_waiting_job(self):
        self.login()
        series = self.prepare()
        async def waiting_send(args, images, folder):
            self.assertTrue(args.resume)
            await asyncio.sleep(20)
        with patch('web_bridge.driver.print_series',side_effect=waiting_send):
            prefix = '/api/internal/bands/'+series['id']
            self.assertEqual(self.client.post(prefix+'/print?resume=true').status_code,202)
            self.assertEqual(self.client.post(prefix+'/cancel').status_code,200)
            self.assertEqual(self.client.get(prefix).json()['status'],'cancelled')
            self.assertNotIn(series['id'],self.app.state.bands.tasks)

    def test_print_calls_shared_driver_and_persists_progress(self):
        from web_bridge import driver
        self.login()
        series = self.prepare()
        async def fake_send(args, images, folder):
            self.assertEqual(args.energy,8000)
            self.assertEqual(args.row_delay,.014)
            self.assertEqual(len(images),2)
            driver.save_state(folder,dict(done=[1,2],failed=None))
            return 0
        with patch('web_bridge.driver.print_series',side_effect=fake_send) as transmit:
            prefix = '/api/internal/bands/'+series['id']
            self.assertEqual(self.client.post(prefix+'/print').status_code,202)
            deadline = time.monotonic()+2
            while time.monotonic()<deadline:
                result=self.client.get(prefix).json()
                if result['status']=='sent': break
                time.sleep(.01)
            self.assertEqual(result['status'],'sent')
            self.assertEqual(result['done'],[1,2])
            self.assertEqual(transmit.call_count,1)
