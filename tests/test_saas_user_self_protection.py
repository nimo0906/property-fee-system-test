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


    def test_admin_cannot_reset_own_password_from_admin_api_or_page(self):
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

            api_reset = client.post(
                f"/api/users/{current['id']}/reset-password",
                json={'new_password': 'self-reset-temp-pass'},
            )
            self.assertEqual(api_reset.status_code, 403)

            page_reset = client.post(
                f"/backoffice/users/{current['id']}/reset-password",
                data={'new_password': 'self-reset-page-pass'},
                follow_redirects=False,
            )
            self.assertEqual(page_reset.status_code, 403)

            repo = create_saas_repository(db_url)
            self.assertIsNone(repo.get_user(current['id'])['password_hash'])
            repo.close()


    def test_current_account_row_hides_admin_reset_and_disable_forms(self):
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

            page = client.get('/backoffice/users')
            self.assertEqual(page.status_code, 200)
            self.assertNotIn(f'/backoffice/users/{current["id"]}/reset-password', page.text)
            self.assertNotIn(f'/backoffice/users/{current["id"]}/active', page.text)
            self.assertIn('当前账号', page.text)
            self.assertIn('请使用个人改密入口', page.text)


    def test_admin_reset_password_rejects_short_temporary_password(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            login = client.post('/api/auth/login', json={
                'tenant_name': '重置短密物业',
                'project_name': '重置短密项目',
                'username': 'admin',
                'role_code': 'system_admin',
            })
            self.assertEqual(login.status_code, 200)
            created = client.post('/api/users', json={'username': 'cashier_short_reset', 'role_code': 'cashier'})
            user_id = created.json()['item']['id']

            api_reset = client.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'short'})
            self.assertEqual(api_reset.status_code, 400)

            page_reset = client.post(
                f'/backoffice/users/{user_id}/reset-password',
                data={'new_password': 'short'},
                follow_redirects=False,
            )
            self.assertEqual(page_reset.status_code, 400)
            self.assertIn('临时密码至少 8 位', page_reset.text)

            repo = create_saas_repository(db_url)
            self.assertIsNone(repo.get_user(user_id)['password_hash'])
            repo.close()


    def test_admin_reset_password_rejects_same_as_target_current_password(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            login = client.post('/api/auth/login', json={
                'tenant_name': '重置同密物业',
                'project_name': '重置同密项目',
                'username': 'admin',
                'role_code': 'system_admin',
            })
            self.assertEqual(login.status_code, 200)
            created = client.post('/api/users', json={'username': 'cashier_same_reset', 'role_code': 'cashier'})
            user_id = created.json()['item']['id']
            first_reset = client.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'Temp-pass-2026'})
            self.assertEqual(first_reset.status_code, 200)

            api_reset = client.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'Temp-pass-2026'})
            self.assertEqual(api_reset.status_code, 400)

            page_reset = client.post(
                f'/backoffice/users/{user_id}/reset-password',
                data={'new_password': 'Temp-pass-2026'},
                follow_redirects=False,
            )
            self.assertEqual(page_reset.status_code, 400)
            self.assertIn('临时密码不能与当前密码相同', page_reset.text)

            repo = create_saas_repository(db_url)
            project_id = repo.list_projects()[0]['id']
            logs = repo.list_audit_logs(repo.get_user(user_id)['tenant_id'], project_id)
            reset_logs = [row for row in logs if row['action'] == 'user.password_reset']
            self.assertEqual(len(reset_logs), 1)
            repo.close()


if __name__ == '__main__':
    unittest.main()
