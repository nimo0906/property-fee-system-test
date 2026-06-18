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


    def test_tenant_admin_console_filters_own_accounts(self):
        client = self._client('system_admin')
        for username, role_code in [
            ('tenant_cashier_alpha', 'cashier'),
            ('tenant_cashier_beta', 'cashier'),
            ('tenant_finance_alpha', 'finance'),
        ]:
            created = client.post('/api/users', json={'username': username, 'role_code': role_code})
            self.assertEqual(created.status_code, 200)
        beta_id = next(item['id'] for item in client.get('/api/users').json()['items'] if item['username'] == 'tenant_cashier_beta')
        client.post(f'/api/users/{beta_id}/active', json={'is_active': False})

        keyword = client.get('/backoffice/tenant-admin?q=finance')
        self.assertEqual(keyword.status_code, 200)
        self.assertIn('tenant_finance_alpha', keyword.text)
        self.assertNotIn('tenant_cashier_alpha', keyword.text)

        role_filtered = client.get('/backoffice/tenant-admin?role_code=cashier')
        self.assertIn('tenant_cashier_alpha', role_filtered.text)
        self.assertIn('tenant_cashier_beta', role_filtered.text)
        self.assertNotIn('tenant_finance_alpha', role_filtered.text)

        inactive = client.get('/backoffice/tenant-admin?is_active=0')
        self.assertIn('tenant_cashier_beta', inactive.text)
        self.assertNotIn('tenant_cashier_alpha', inactive.text)
        self.assertIn('筛选本公司账号', inactive.text)

    def test_non_admin_cannot_open_tenant_admin_console(self):
        client = self._client('cashier')
        page = client.get('/backoffice/tenant-admin')
        self.assertEqual(page.status_code, 403)


if __name__ == '__main__':
    unittest.main()
