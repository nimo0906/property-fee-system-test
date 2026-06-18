import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasChangePasswordPages(unittest.TestCase):
    def test_staff_can_open_and_submit_change_password_page_when_required(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = TestClient(create_app(database_url=db_url))
            login = admin.post('/api/auth/login', json={
                'tenant_name': '改密物业',
                'project_name': '改密项目',
                'username': 'admin',
                'role_code': 'system_admin',
            })
            self.assertEqual(login.status_code, 200)
            created = admin.post('/api/users', json={'username': 'cashier_change', 'role_code': 'cashier'})
            self.assertEqual(created.status_code, 200)
            user_id = created.json()['item']['id']
            reset = admin.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'Temp-pass-2026'})
            self.assertEqual(reset.status_code, 200)

            staff = TestClient(create_app(database_url=db_url))
            logged_in = staff.post('/api/auth/login', json={
                'tenant_name': '改密物业',
                'project_name': '改密项目',
                'username': 'cashier_change',
                'role_code': 'cashier',
                'password': 'Temp-pass-2026',
            })
            self.assertEqual(logged_in.status_code, 200)
            self.assertTrue(logged_in.json()['must_change_password'])

            page = staff.get('/backoffice/change-password')
            self.assertEqual(page.status_code, 200)
            self.assertIn('修改个人密码', page.text)
            self.assertIn('当前账号', page.text)
            self.assertIn('cashier_change', page.text)

            changed = staff.post('/backoffice/change-password', data={
                'old_password': 'Temp-pass-2026',
                'new_password': 'New-pass-2026',
            }, follow_redirects=False)
            self.assertEqual(changed.status_code, 303)
            self.assertIn('/backoffice', changed.headers['location'])
            me = staff.get('/api/auth/me')
            self.assertEqual(me.status_code, 200)
            self.assertFalse(me.json()['must_change_password'])


    def test_required_password_change_redirects_backoffice_to_change_password_page(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = TestClient(create_app(database_url=db_url))
            self.assertEqual(admin.post('/api/auth/login', json={
                'tenant_name': '改密物业3',
                'project_name': '改密项目3',
                'username': 'admin',
                'role_code': 'system_admin',
            }).status_code, 200)
            created = admin.post('/api/users', json={'username': 'cashier_redirect', 'role_code': 'cashier'})
            user_id = created.json()['item']['id']
            admin.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'Temp-pass-2026'})

            staff = TestClient(create_app(database_url=db_url))
            self.assertEqual(staff.post('/api/auth/login', json={
                'tenant_name': '改密物业3',
                'project_name': '改密项目3',
                'username': 'cashier_redirect',
                'role_code': 'cashier',
                'password': 'Temp-pass-2026',
            }).status_code, 200)

            blocked = staff.get('/backoffice', follow_redirects=False)
            self.assertEqual(blocked.status_code, 303)
            self.assertEqual(blocked.headers['location'], '/backoffice/change-password')

    def test_wrong_old_password_stays_on_change_password_page(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = TestClient(create_app(database_url=db_url))
            self.assertEqual(admin.post('/api/auth/login', json={
                'tenant_name': '改密物业2',
                'project_name': '改密项目2',
                'username': 'admin',
                'role_code': 'system_admin',
            }).status_code, 200)
            created = admin.post('/api/users', json={'username': 'cashier_wrong', 'role_code': 'cashier'})
            user_id = created.json()['item']['id']
            admin.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'Temp-pass-2026'})

            staff = TestClient(create_app(database_url=db_url))
            self.assertEqual(staff.post('/api/auth/login', json={
                'tenant_name': '改密物业2',
                'project_name': '改密项目2',
                'username': 'cashier_wrong',
                'role_code': 'cashier',
                'password': 'Temp-pass-2026',
            }).status_code, 200)

            changed = staff.post('/backoffice/change-password', data={
                'old_password': 'wrong-old-password',
                'new_password': 'New-pass-2026',
            })
            self.assertEqual(changed.status_code, 401)
            self.assertIn('原密码不正确', changed.text)


if __name__ == '__main__':
    unittest.main()
