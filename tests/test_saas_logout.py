import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasLogout(unittest.TestCase):
    def _client(self):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '退出物业',
            'project_name': '退出项目',
            'username': 'admin',
            'role_code': 'system_admin',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_exposes_logout_action(self):
        client = self._client()
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('退出登录', page.text)
        self.assertIn('/api/auth/logout', page.text)

    def test_logout_destroys_session_and_clears_cookie(self):
        client = self._client()
        me_before = client.get('/api/auth/me')
        self.assertEqual(me_before.status_code, 200)
        logout = client.post('/api/auth/logout')
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.json()['ok'], True)
        self.assertIn('session_id', logout.headers.get('set-cookie', ''))
        me_after = client.get('/api/auth/me')
        self.assertEqual(me_after.status_code, 401)
        backoffice = client.get('/backoffice')
        self.assertEqual(backoffice.status_code, 401)

    def test_logout_requires_existing_session(self):
        client = TestClient(create_app())
        logout = client.post('/api/auth/logout')
        self.assertEqual(logout.status_code, 401)


if __name__ == '__main__':
    unittest.main()
