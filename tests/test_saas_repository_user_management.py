import tempfile
import unittest
from pathlib import Path

from server.passwords import verify_password
from server.saas_repository import TenantScopeError, create_saas_repository


class TestSaasRepositoryUserManagement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = create_saas_repository(f"sqlite:///{Path(self.tmp.name) / 'saas.sqlite3'}")
        self.tenant = self.repo.create_tenant('A物业')
        self.project = self.repo.create_project(self.tenant['id'], 'A项目')
        self.repo.upsert_role('system_admin', '管理员')
        self.repo.upsert_role('platform_admin', '平台管理员')
        self.repo.upsert_role('finance', '财务')
        self.repo.upsert_role('cashier', '收费员')

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_create_staff_user_scoped_to_project(self):
        user = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'finance_a', 'finance')
        self.assertEqual(user['tenant_id'], self.tenant['id'])
        self.assertEqual(user['project_id'], self.project['id'])
        self.assertEqual(user['role_code'], 'finance')
        self.assertEqual(self.repo.list_users()[0]['username'], 'finance_a')

    def test_create_staff_user_requires_known_role(self):
        with self.assertRaises(ValueError):
            self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'ghost', 'owner')

    def test_create_staff_user_rejects_cross_tenant_project(self):
        other_tenant = self.repo.create_tenant('B物业')
        other_project = self.repo.create_project(other_tenant['id'], 'B项目')
        with self.assertRaises(TenantScopeError):
            self.repo.create_staff_user(self.tenant['id'], other_project['id'], 'bad', 'finance')

    def test_list_and_disable_users_are_tenant_scoped_and_audited(self):
        admin = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'admin', 'system_admin')
        user = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'cashier_a', 'cashier')
        other_tenant = self.repo.create_tenant('B物业')
        other_project = self.repo.create_project(other_tenant['id'], 'B项目')
        self.repo.create_staff_user(other_tenant['id'], other_project['id'], 'cashier_b', 'cashier')
        users = self.repo.list_users(self.tenant['id'])
        self.assertEqual({u['username'] for u in users}, {'admin', 'cashier_a'})
        disabled = self.repo.set_user_active(self.tenant['id'], user['id'], False, actor_user_id=admin['id'], project_id=self.project['id'])
        self.assertEqual(disabled['is_active'], 0)
        self.assertEqual(self.repo.get_user(user['id'])['is_active'], 0)
        logs = self.repo.list_audit_logs(self.tenant['id'], self.project['id'])
        disable_log = next(row for row in logs if row['action'] == 'user.disable')
        self.assertEqual(disable_log['detail']['target_username'], 'cashier_a')
        with self.assertRaises(TenantScopeError):
            self.repo.set_user_active(self.tenant['id'], 99999, False)

    def test_platform_admin_can_list_and_reset_all_tenant_users_with_target_audit(self):
        admin = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'tenant_admin', 'system_admin')
        other_tenant = self.repo.create_tenant('B物业')
        other_project = self.repo.create_project(other_tenant['id'], 'B项目')
        other_user = self.repo.create_staff_user(other_tenant['id'], other_project['id'], 'cashier_b', 'cashier')
        platform = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'platform_admin', 'platform_admin')

        users = self.repo.list_users_for_actor(platform)
        self.assertIn('cashier_b', {u['username'] for u in users})
        reset = self.repo.reset_user_password_for_actor(platform, other_user['id'], 'global-temp-pass')
        self.assertEqual(reset['user_id'], other_user['id'])
        self.assertTrue(verify_password('global-temp-pass', self.repo.get_user(other_user['id'])['password_hash']))
        logs = self.repo.list_audit_logs(other_tenant['id'], other_project['id'])
        reset_log = next(row for row in logs if row['action'] == 'user.password_reset')
        self.assertEqual(reset_log['detail']['scope'], 'platform')
        self.assertEqual(reset_log['detail']['actor_username'], 'platform_admin')
        self.assertNotIn('global-temp-pass', str(reset_log))

        with self.assertRaises(TenantScopeError):
            self.repo.reset_user_password_for_actor(admin, other_user['id'], 'blocked-pass')

    def test_reset_password_requires_same_tenant(self):
        user = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'finance_a', 'finance')
        other_tenant = self.repo.create_tenant('B物业')
        other_project = self.repo.create_project(other_tenant['id'], 'B项目')
        other_user = self.repo.create_staff_user(other_tenant['id'], other_project['id'], 'finance_b', 'finance')
        admin = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'admin', 'system_admin')
        result = self.repo.reset_user_password(admin['tenant_id'], user['id'], 'newpass')
        self.assertEqual(result['user_id'], user['id'])
        with self.assertRaises(TenantScopeError):
            self.repo.reset_user_password(self.tenant['id'], other_user['id'], 'badpass')

    def test_platform_admin_can_disable_cross_tenant_user_through_api(self):
        from fastapi.testclient import TestClient
        from server.saas_app import create_app

        db_url = f"sqlite:///{Path(self.tmp.name) / 'api_cross_tenant.sqlite3'}"
        platform = TestClient(create_app(database_url=db_url))
        login = platform.post('/api/auth/login', json={
            'tenant_name': '平台物业',
            'project_name': '平台项目',
            'username': 'platform_admin',
            'role_code': 'platform_admin',
        })
        self.assertEqual(login.status_code, 200)

        tenant_admin = TestClient(create_app(database_url=db_url))
        login = tenant_admin.post('/api/auth/login', json={
            'tenant_name': '客户物业',
            'project_name': '客户项目',
            'username': 'tenant_admin',
            'role_code': 'system_admin',
        })
        self.assertEqual(login.status_code, 200)
        created = tenant_admin.post('/api/users', json={'username': 'api_customer_cashier', 'role_code': 'cashier'})
        self.assertEqual(created.status_code, 200)
        user_id = created.json()['item']['id']

        disabled = platform.post(f'/api/users/{user_id}/active', json={'is_active': False})
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.json()['item']['is_active'], 0)

        repo = create_saas_repository(db_url)
        target = repo.get_user(user_id)
        self.assertEqual(target['is_active'], 0)
        project = next(row for row in repo.list_projects() if row['tenant_id'] == target['tenant_id'])
        logs = repo.list_audit_logs(target['tenant_id'], project['id'])
        disable_log = next(row for row in logs if row['action'] == 'user.disable')
        self.assertEqual(disable_log['detail']['scope'], 'platform')
        self.assertEqual(disable_log['detail']['actor_username'], 'platform_admin')
        repo.close()


if __name__ == '__main__':
    unittest.main()

class TestSaasFastApiPersistentUserManagement(unittest.TestCase):
    def test_admin_user_management_persists_to_repository(self):
        from fastapi.testclient import TestClient
        from server.saas_app import create_app

        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = TestClient(create_app(database_url=db_url))
            login = admin.post('/api/auth/login', json={
                'tenant_name': '持久化物业',
                'project_name': '持久化项目',
                'username': 'admin',
                'role_code': 'system_admin',
            })
            self.assertEqual(login.status_code, 200)
            created = admin.post('/api/users', json={'username': 'cashier_p', 'role_code': 'cashier'})
            self.assertEqual(created.status_code, 200)
            user_id = created.json()['item']['id']
            users_response = admin.get('/api/users')
            self.assertEqual(users_response.status_code, 200)
            self.assertIn('cashier_p', [u['username'] for u in users_response.json()['items']])
            reset = admin.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'tmp-password'})
            self.assertEqual(reset.status_code, 200)
            disabled = admin.post(f'/api/users/{user_id}/active', json={'is_active': False})
            self.assertEqual(disabled.status_code, 200)

            reopened = create_saas_repository(db_url)
            users = reopened.list_users()
            self.assertIn('cashier_p', [u['username'] for u in users])
            stored_hash = reopened.get_user(user_id)['password_hash']
            self.assertNotEqual(stored_hash, 'tmp-password')
            self.assertNotEqual(stored_hash, 'hash:tmp-password')
            self.assertTrue(verify_password('tmp-password', stored_hash))
            self.assertEqual(reopened.get_user(user_id)['is_active'], 0)
            logs = reopened.list_audit_logs(users[0]['tenant_id'], reopened.list_projects()[0]['id'])
            self.assertIn('user.disable', [row['action'] for row in logs])
            reopened.close()
