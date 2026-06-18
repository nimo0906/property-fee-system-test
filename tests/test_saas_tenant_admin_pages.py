import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasTenantAdminPages(unittest.TestCase):
    def _client(self, role_code='system_admin', database_url=None):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '租户控制台物业',
            'project_name': '租户控制台项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_tenant_admin_console_for_tenant_admin(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('租户管理员', page.text)
        self.assertIn('/backoffice/tenant-admin', page.text)

    def test_finance_cannot_see_tenant_admin_console_link(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('href="/backoffice/tenant-admin"', page.text)

    def test_tenant_admin_console_connects_account_management_actions(self):
        client = self._client('system_admin')
        created = client.post('/api/users', json={'username': 'tenant_cashier', 'role_code': 'cashier'})
        self.assertEqual(created.status_code, 200)
        page = client.get('/backoffice/tenant-admin')
        self.assertEqual(page.status_code, 200)
        html = page.text
        self.assertIn('租户管理员控制台', html)
        self.assertIn('本公司账号列表', html)
        self.assertIn('tenant_cashier', html)
        self.assertIn('停用账号', html)
        self.assertIn('重置密码', html)
        self.assertIn('/backoffice/users', html)
        self.assertIn('客户数据隔离', html)
        self.assertNotIn('平台全局视图', html)

    def test_non_admin_cannot_open_tenant_admin_console(self):
        client = self._client('cashier')
        page = client.get('/backoffice/tenant-admin')
        self.assertEqual(page.status_code, 403)


if __name__ == '__main__':
    unittest.main()
