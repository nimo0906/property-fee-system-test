import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasBackofficePages(unittest.TestCase):
    def _client(self, role_code='system_admin'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '首页物业',
            'project_name': '首页项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_user_management_for_admin(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('SaaS 员工后台', page.text)
        self.assertIn('首页物业', page.text)
        self.assertIn('首页项目', page.text)
        self.assertIn('账号管理', page.text)
        self.assertIn('/backoffice/users', page.text)

    def test_backoffice_home_hides_user_management_link_for_finance(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('SaaS 员工后台', page.text)
        self.assertIn('财务', page.text)
        self.assertIn('账号管理仅管理员可用', page.text)
        self.assertNotIn('href="/backoffice/users"', page.text)

    def test_backoffice_home_requires_login(self):
        client = TestClient(create_app())
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 401)


if __name__ == '__main__':
    unittest.main()
