import http.client
import os
import sys
import tempfile
import threading
import time
import http.server
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BASE_URL, TEST_PORT, login_and_get_client, http_get


def _start_server():
    os.environ['PM_DB_PATH'] = os.path.join(tempfile.gettempdir(), f'test_branding_{int(time.time())}.db')
    import server.db as db_module
    db_module.DB_PATH = os.environ['PM_DB_PATH']
    db_module.BACKUP_DIR = os.path.join(os.path.dirname(db_module.DB_PATH), 'backups')
    from server import Handler, db_init
    db_init()
    srv = http.server.ThreadingHTTPServer((BASE_URL, TEST_PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    return srv


class TestBrandingAndPlans(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.server_close()
        time.sleep(0.1)

    def setUp(self):
        self.cookie = login_and_get_client(TEST_PORT)

    def test_login_page_uses_generic_branding(self):
        status, body = http_get('/login', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('物业收费管理系统', body)
        self.assertNotIn('金莎国际', body)

    def test_plan_pages_are_accessible(self):
        expected = {
            '/commercial_license': '授权设计',
            '/cloud_deployment_plan': '云端部署方案',
            '/license_status': '授权状态',
            '/first_run_guide': '首次使用引导',
        }
        for path, text in expected.items():
            status, body = http_get(path, self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn(text, body)
