import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasUserSelfProtection(unittest.TestCase):
    def test_admin_cannot_disable_own_account_from_api_or_page(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            login = client.post('/api/auth/login', json={
                'tenant_name': '自保护物业',
                'project_name': '自保护项目',
                'username': 'system_admin',
                'role_code': 'system_admin',
            })
            self.assertEqual(login.status_code, 200)
            current = client.get('/api/users').json()['items'][0]
            self.assertEqual(current['username'], 'system_admin')

            api_disabled = client.post(f"/api/users/{current['id']}/active", json={'is_active': False})
            self.assertEqual(api_disabled.status_code, 403)

            page_disabled = client.post(
                f"/backoffice/users/{current['id']}/active",
                data={'is_active': '0'},
                follow_redirects=False,
            )
            self.assertEqual(page_disabled.status_code, 403)

            repo = create_saas_repository(db_url)
            self.assertEqual(repo.get_user(current['id'])['is_active'], 1)
            still_logged_in = client.get('/api/auth/me')
            self.assertEqual(still_logged_in.status_code, 200)
            repo.close()


if __name__ == '__main__':
    unittest.main()
