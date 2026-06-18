import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasDeployPages(unittest.TestCase):
    def _client(self, role_code='system_admin'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '部署物业',
            'project_name': '部署项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_deploy_checklist(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('云端上线', page.text)
        self.assertIn('/backoffice/deploy-checklist', page.text)

    def test_deploy_checklist_page_shows_vps_assets_and_commands(self):
        client = self._client('finance')
        page = client.get('/backoffice/deploy-checklist')
        self.assertEqual(page.status_code, 200)
        html = page.text
        for text in [
            'VPS 上线操作清单',
            'scripts/saas_preflight_check.py',
            'scripts/saas_acceptance_check.py',
            'docker compose up -d',
            'deploy/nginx/property-saas.conf',
            'deploy/systemd/property-saas.service',
            'scripts/saas_backup.sh',
            'scripts/saas_restore.sh --verify-metadata',
            '/var/lib/property-saas/tenants',
            '/var/lib/property-saas/system',
            'HTTPS',
            '127.0.0.1:8000',
            '部署资产',
            'PASS',
        ]:
            self.assertIn(text, html)
        self.assertNotIn('POSTGRES_PASSWORD=', html)
        self.assertNotIn('APP_SECRET_KEY=', html)
        self.assertNotIn('真实密码', html)

    def test_deploy_checklist_requires_login(self):
        client = TestClient(create_app())
        page = client.get('/backoffice/deploy-checklist')
        self.assertEqual(page.status_code, 401)


if __name__ == '__main__':
    unittest.main()
