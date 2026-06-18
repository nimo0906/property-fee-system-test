import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasAuditLogPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None, tenant_name='审计物业', project_name='审计项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_audit_log_page(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/audit-logs', page.text)

    def test_audit_log_page_lists_current_tenant_actions_without_password_plaintext(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = self._client('system_admin', database_url=db_url)
            created = admin.post('/api/users', json={'username': 'cashier_audit', 'role_code': 'cashier'})
            self.assertEqual(created.status_code, 200)
            reset = admin.post(f"/api/users/{created.json()['item']['id']}/reset-password", json={'new_password': 'secret-temp-password'})
            self.assertEqual(reset.status_code, 200)

            page = admin.get('/backoffice/audit-logs')
            self.assertEqual(page.status_code, 200)
            self.assertIn('审计日志', page.text)
            self.assertIn('user.password_reset', page.text)
            self.assertIn('cashier_audit', page.text)
            self.assertNotIn('secret-temp-password', page.text)

    def test_executive_can_view_audit_logs_readonly(self):
        client = self._client('executive')
        page = client.get('/backoffice/audit-logs')
        self.assertEqual(page.status_code, 200)
        self.assertIn('审计日志', page.text)
        self.assertIn('只读', page.text)

    def test_audit_log_page_is_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin_a = self._client('system_admin', database_url=db_url, tenant_name='A审计物业', project_name='A审计项目')
            created = admin_a.post('/api/users', json={'username': 'a_cashier', 'role_code': 'cashier'})
            self.assertEqual(created.status_code, 200)
            admin_a.post(f"/api/users/{created.json()['item']['id']}/active", json={'is_active': False})

            admin_b = self._client('system_admin', database_url=db_url, tenant_name='B审计物业', project_name='B审计项目')
            page_b = admin_b.get('/backoffice/audit-logs')
            self.assertEqual(page_b.status_code, 200)
            self.assertIn('审计日志', page_b.text)
            self.assertNotIn('a_cashier', page_b.text)
            self.assertNotIn('user.disable', page_b.text)


if __name__ == '__main__':
    unittest.main()
