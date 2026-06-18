import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasBackofficeHealthSummary(unittest.TestCase):
    def _client(self, role_code='platform_admin'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '健康物业',
            'project_name': '健康项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_platform_home_shows_system_health_summary(self):
        client = self._client('platform_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        html = page.text
        self.assertIn('系统健康', html)
        self.assertIn('部署资产 PASS', html)
        self.assertIn('端口本机绑定 PASS', html)
        self.assertIn('备份恢复脚本 PASS', html)
        self.assertIn('HTTPS', html)
        self.assertIn('/backoffice/deploy-checklist', html)

    def test_tenant_admin_home_does_not_show_platform_health_summary(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('系统健康', page.text)
        self.assertNotIn('部署资产 PASS', page.text)


if __name__ == '__main__':
    unittest.main()
