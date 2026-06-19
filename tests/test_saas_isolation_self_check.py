import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasIsolationSelfCheck(unittest.TestCase):
    def _login(self, client, role_code='system_admin'):
        response = client.post('/api/auth/login', json={
            'tenant_name': '自检物业',
            'project_name': '自检项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)

    def test_self_check_api_reports_all_business_boundaries(self):
        client = TestClient(create_app())
        self._login(client, 'system_admin')
        response = client.post('/api/isolation/self-check')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'pass')
        self.assertEqual(data['checked_scope'], 'current_tenant_project')
        names = [item['name'] for item in data['checks']]
        for name in ['收费对象', '账单', '收款', '导入文件', '审计日志']:
            self.assertIn(name, names)
        self.assertTrue(all(item['status'] == 'pass' for item in data['checks']))
        self.assertNotIn('POSTGRES_PASSWORD=', str(data))
        self.assertNotIn('APP_SECRET_KEY=', str(data))
        self.assertNotIn('A栋', str(data))

    def test_persistent_self_check_cleans_up_canary_tenant_data(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            app = create_app(database_url=db_url)
            client = TestClient(app)
            self._login(client, 'system_admin')
            response = client.post('/api/isolation/self-check')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'pass')
            repo = app.state.repository
            leaked = [t for t in repo.list_tenants() if '隔离自检金丝雀' in t['name']]
            self.assertEqual(leaked, [])

    def test_self_check_page_has_button_and_latest_result_placeholder(self):
        client = TestClient(create_app())
        self._login(client, 'finance')
        page = client.get('/backoffice/data-boundaries')
        self.assertEqual(page.status_code, 200)
        for text in [
            '租户隔离自动自检',
            '/api/isolation/self-check',
            '一键检查当前租户是否能越权读取其他租户数据',
            '收费对象、账单、收款、导入文件、审计日志',
        ]:
            self.assertIn(text, page.text)

    def test_self_check_requires_login(self):
        client = TestClient(create_app())
        response = client.post('/api/isolation/self-check')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
