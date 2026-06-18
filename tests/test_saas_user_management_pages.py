import unittest

from fastapi.testclient import TestClient

from server.passwords import verify_password
from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasUserManagementPages(unittest.TestCase):
    def _admin_client(self, database_url=None, role_code='system_admin'):
        client = TestClient(create_app(database_url=database_url))
        login = client.post('/api/auth/login', json={
            'tenant_name': '页面物业',
            'project_name': '页面项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(login.status_code, 200)
        return client

    def test_user_management_page_lists_accounts_and_forms(self):
        client = self._admin_client()
        created = client.post('/api/users', json={'username': 'cashier_page', 'role_code': 'cashier'})
        self.assertEqual(created.status_code, 200)
        page = client.get('/backoffice/users')
        self.assertEqual(page.status_code, 200)
        html = page.text
        self.assertIn('账号管理', html)
        self.assertIn('cashier_page', html)
        self.assertIn('停用账号', html)
        self.assertIn('重置密码', html)
        self.assertIn('tenant-scope', html)

    def test_non_admin_cannot_open_user_management_page(self):
        client = self._admin_client(role_code='finance')
        page = client.get('/backoffice/users')
        self.assertEqual(page.status_code, 403)

    def test_user_management_page_filters_and_paginates_accounts(self):
        client = self._admin_client()
        for username, role_code in [
            ('cashier_alpha', 'cashier'),
            ('cashier_beta', 'cashier'),
            ('finance_alpha', 'finance'),
        ]:
            created = client.post('/api/users', json={'username': username, 'role_code': role_code})
            self.assertEqual(created.status_code, 200)
        beta_id = next(item['id'] for item in client.get('/api/users').json()['items'] if item['username'] == 'cashier_beta')
        client.post(f'/api/users/{beta_id}/active', json={'is_active': False})

        keyword = client.get('/backoffice/users?q=finance')
        self.assertEqual(keyword.status_code, 200)
        self.assertIn('finance_alpha', keyword.text)
        self.assertNotIn('cashier_alpha', keyword.text)

        role_filtered = client.get('/backoffice/users?role_code=cashier')
        self.assertIn('cashier_alpha', role_filtered.text)
        self.assertIn('cashier_beta', role_filtered.text)
        self.assertNotIn('finance_alpha', role_filtered.text)

        inactive = client.get('/backoffice/users?is_active=0')
        self.assertIn('cashier_beta', inactive.text)
        self.assertNotIn('cashier_alpha', inactive.text)

        page_one = client.get('/backoffice/users?page_size=1&page=1')
        page_two = client.get('/backoffice/users?page_size=1&page=2')
        self.assertIn('下一页', page_one.text)
        self.assertIn('上一页', page_two.text)
        self.assertNotEqual(page_one.text, page_two.text)

    def test_user_page_can_disable_enable_and_reset_password_without_plaintext_audit(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._admin_client(database_url=db_url)
            created = client.post('/api/users', json={'username': 'cashier_page', 'role_code': 'cashier'})
            user_id = created.json()['item']['id']

            disabled = client.post(f'/backoffice/users/{user_id}/active', data={'is_active': '0'}, follow_redirects=False)
            self.assertEqual(disabled.status_code, 303)
            enabled = client.post(f'/backoffice/users/{user_id}/active', data={'is_active': '1'}, follow_redirects=False)
            self.assertEqual(enabled.status_code, 303)
            reset = client.post(f'/backoffice/users/{user_id}/reset-password', data={'new_password': 'page-temp-password'}, follow_redirects=False)
            self.assertEqual(reset.status_code, 303)

            repo = create_saas_repository(db_url)
            user = repo.get_user(user_id)
            self.assertEqual(user['is_active'], 1)
            self.assertTrue(verify_password('page-temp-password', user['password_hash']))
            project_id = repo.list_projects()[0]['id']
            logs = repo.list_audit_logs(user['tenant_id'], project_id)
            actions = [row['action'] for row in logs]
            self.assertIn('user.disable', actions)
            self.assertIn('user.enable', actions)
            self.assertIn('user.password_reset', actions)
            self.assertNotIn('page-temp-password', str(logs))
            repo.close()


if __name__ == '__main__':
    unittest.main()
