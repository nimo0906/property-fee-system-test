import json
import os
import tempfile
import unittest
from pathlib import Path

from server.commercial_config import read_setup_config, save_setup_config, should_force_first_run
from server.license_status import read_license_status


class TestCommercialReadinessHelpers(unittest.TestCase):
    def test_first_run_config_saves_generic_customer_setup(self):
        with tempfile.TemporaryDirectory() as td:
            data = save_setup_config({
                'company_name': '通用物业公司',
                'project_name': '示例项目',
                'default_billing_cycle': 'quarterly',
                'default_property_rate': '3.50',
                'enable_commercial_billing': 'on',
            }, td)
            self.assertTrue(data['initialized'])
            loaded = read_setup_config(td)
            self.assertEqual(loaded['company_name'], '通用物业公司')
            self.assertEqual(loaded['project_name'], '示例项目')
            self.assertEqual(loaded['default_billing_cycle'], 'quarterly')
            self.assertTrue(loaded['enable_commercial_billing'])
            self.assertTrue(Path(loaded['setup_file']).exists())

    def test_uninitialized_logged_in_user_is_forced_to_first_run(self):
        old = os.environ.get('PM_ENFORCE_FIRST_RUN')
        os.environ['PM_ENFORCE_FIRST_RUN'] = '1'
        try:
            with tempfile.TemporaryDirectory() as td:
                self.assertTrue(should_force_first_run('/', {'role': 'admin'}, td))
                self.assertFalse(should_force_first_run('/first_run_guide', {'role': 'admin'}, td))
                save_setup_config({'company_name': 'A', 'project_name': 'B'}, td)
                self.assertFalse(should_force_first_run('/', {'role': 'admin'}, td))
        finally:
            if old is None:
                os.environ.pop('PM_ENFORCE_FIRST_RUN', None)
            else:
                os.environ['PM_ENFORCE_FIRST_RUN'] = old

    def test_expired_annual_license_is_blocking(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'license' / 'license.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                'status': 'active',
                'edition': '正式商业版',
                'customer_name': '授权客户',
                'license_model': 'annual',
                'device_limit': 3,
                'offline_grace_days': 7,
                'expires_at': '2000-01-01',
                'license_key': 'PBMS-REAL-EXPIRED-0001',
            }, ensure_ascii=False), encoding='utf-8')
            status = read_license_status(td)
            self.assertEqual(status['status_label'], '已过期')
            self.assertTrue(status['access_blocked'])
            self.assertEqual(status['license_model_label'], '按年授权')
            self.assertEqual(status['device_limit'], 3)
            self.assertEqual(status['offline_grace_days'], 7)

class TestCommercialReadinessHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import http.server
        import threading
        import time
        from tests.conftest import BASE_URL, TEST_PORT
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_env = {k: os.environ.get(k) for k in ('PM_DB_PATH', 'PM_DATA_DIR', 'PM_ENFORCE_FIRST_RUN')}
        os.environ['PM_DATA_DIR'] = cls.tmp.name
        os.environ['PM_DB_PATH'] = os.path.join(cls.tmp.name, 'database', 'property.db')
        os.environ['PM_ENFORCE_FIRST_RUN'] = '1'
        Path(os.environ['PM_DB_PATH']).parent.mkdir(parents=True, exist_ok=True)
        import server.db as db_module
        db_module.DB_PATH = os.environ['PM_DB_PATH']
        db_module.BACKUP_DIR = os.path.join(cls.tmp.name, 'backups')
        from server import Handler, db_init
        db_init()
        cls.server = http.server.ThreadingHTTPServer((BASE_URL, TEST_PORT), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        import time
        cls.server.server_close()
        time.sleep(0.1)
        for k, v in cls.old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import server.db as db_module
        fallback_db = os.environ.get('PM_DB_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'property.db')
        Path(fallback_db).parent.mkdir(parents=True, exist_ok=True)
        db_module.DB_PATH = fallback_db
        db_module.BACKUP_DIR = os.environ.get('PM_BACKUP_DIR') or os.path.join(os.path.dirname(fallback_db), 'backups')
        cls.tmp.cleanup()

    def test_first_run_save_unblocks_home(self):
        from tests.conftest import TEST_PORT, login_and_get_client, http_get, http_post
        license_path = Path(self.tmp.name) / 'license' / 'license.json'
        if license_path.exists():
            license_path.unlink()
        save_setup_config({'company_name': '', 'project_name': '', 'initialized': False}, self.tmp.name)
        cookie = login_and_get_client(TEST_PORT)
        status, body = http_get('/', cookie, TEST_PORT)
        self.assertEqual(status, 302)
        status, body = http_get('/first_run_guide', cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('初始化配置', body)
        status, _, loc = http_post('/first_run_setup', {
            'company_name': '正式商业客户',
            'project_name': '通用项目',
            'default_billing_cycle': 'annual',
            'default_property_rate': '4.20',
            'enable_commercial_billing': 'on',
            'enable_meter_reading': 'on',
        }, cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/first_run_guide', loc)
        status, home = http_get('/', cookie, TEST_PORT)
        self.assertEqual(status, 200)

    def test_expired_license_blocks_after_login(self):
        from tests.conftest import TEST_PORT, login_and_get_client, http_get
        save_setup_config({'company_name': '正式商业客户', 'project_name': '通用项目'}, self.tmp.name)
        license_path = Path(self.tmp.name) / 'license' / 'license.json'
        license_path.parent.mkdir(parents=True, exist_ok=True)
        license_path.write_text(json.dumps({
            'status': 'active',
            'edition': '正式商业版',
            'license_model': 'annual',
            'device_limit': 3,
            'offline_grace_days': 7,
            'expires_at': '2000-01-01',
            'license_key': 'PBMS-EXPIRED-HTTP-0001',
        }, ensure_ascii=False), encoding='utf-8')
        cookie = login_and_get_client(TEST_PORT)
        status, body = http_get('/', cookie, TEST_PORT)
        self.assertEqual(status, 302)
        status, license_body = http_get('/license_status', cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('已过期', license_body)
        self.assertIn('到期后不能进入系统', license_body)
