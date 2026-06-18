import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasPasswordLoginFlow(unittest.TestCase):
    def test_reset_password_requires_staff_to_login_with_new_password_and_change_it(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = TestClient(create_app(database_url=db_url))
            login = admin.post('/api/auth/login', json={
                'tenant_name': '密码物业',
                'project_name': '密码项目',
                'username': 'admin',
                'role_code': 'system_admin',
            })
            self.assertEqual(login.status_code, 200)
            created = admin.post('/api/users', json={'username': 'cashier_secure', 'role_code': 'cashier'})
            self.assertEqual(created.status_code, 200)
            user_id = created.json()['item']['id']
            reset = admin.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'Temp-pass-2026'})
            self.assertEqual(reset.status_code, 200)

            staff = TestClient(create_app(database_url=db_url))
            no_password = staff.post('/api/auth/login', json={
                'tenant_name': '密码物业',
                'project_name': '密码项目',
                'username': 'cashier_secure',
                'role_code': 'cashier',
            })
            self.assertEqual(no_password.status_code, 401)
            wrong = staff.post('/api/auth/login', json={
                'tenant_name': '密码物业',
                'project_name': '密码项目',
                'username': 'cashier_secure',
                'role_code': 'cashier',
                'password': 'wrong-password',
            })
            self.assertEqual(wrong.status_code, 401)

            ok = staff.post('/api/auth/login', json={
                'tenant_name': '密码物业',
                'project_name': '密码项目',
                'username': 'cashier_secure',
                'role_code': 'cashier',
                'password': 'Temp-pass-2026',
            })
            self.assertEqual(ok.status_code, 200)
            self.assertTrue(ok.json()['must_change_password'])
            me = staff.get('/api/auth/me')
            self.assertEqual(me.status_code, 200)
            self.assertTrue(me.json()['must_change_password'])
            blocked = staff.get('/api/charge-targets')
            self.assertEqual(blocked.status_code, 403)

            changed = staff.post('/api/auth/change-password', json={
                'old_password': 'Temp-pass-2026',
                'new_password': 'New-pass-2026',
            })
            self.assertEqual(changed.status_code, 200)
            self.assertFalse(changed.json()['must_change_password'])
            allowed = staff.get('/api/charge-targets')
            self.assertEqual(allowed.status_code, 200)

            fresh = TestClient(create_app(database_url=db_url))
            old_login = fresh.post('/api/auth/login', json={
                'tenant_name': '密码物业',
                'project_name': '密码项目',
                'username': 'cashier_secure',
                'role_code': 'cashier',
                'password': 'Temp-pass-2026',
            })
            self.assertEqual(old_login.status_code, 401)
            new_login = fresh.post('/api/auth/login', json={
                'tenant_name': '密码物业',
                'project_name': '密码项目',
                'username': 'cashier_secure',
                'role_code': 'cashier',
                'password': 'New-pass-2026',
            })
            self.assertEqual(new_login.status_code, 200)
            self.assertFalse(new_login.json()['must_change_password'])

            repo = create_saas_repository(db_url)
            logs = repo.list_audit_logs(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            actions = [row['action'] for row in logs]
            self.assertIn('user.password_reset', actions)
            self.assertIn('user.password_change', actions)
            self.assertNotIn('Temp-pass-2026', str(logs))
            self.assertNotIn('New-pass-2026', str(logs))
            repo.close()


if __name__ == '__main__':
    unittest.main()
