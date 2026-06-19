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

    def test_backoffice_home_shows_first_run_guide_for_empty_tenant(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        for text in [
            '首次使用向导',
            '空库启动',
            '第 1 步：确认项目',
            '第 2 步：导入/录入收费对象',
            '第 3 步：配置收费项目',
            '第 4 步：生成并审核账单',
            '第 5 步：登记收款',
            '第 6 步：查看报表和导出',
            '/backoffice/imports',
            '/backoffice/charge-targets',
            '/backoffice/fee-types',
            '/backoffice/bills',
            '/backoffice/payments',
            '/backoffice/reports',
            '当前租户和项目隔离',
        ]:
            self.assertIn(text, page.text)

    def test_backoffice_home_requires_login(self):
        client = TestClient(create_app())
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 401)


if __name__ == '__main__':
    unittest.main()
