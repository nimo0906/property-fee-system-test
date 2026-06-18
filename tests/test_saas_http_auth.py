import unittest

from server.saas_http import create_saas_http_app


class TestSaasHttpAuth(unittest.TestCase):
    def test_login_sets_session_and_returns_tenant_scoped_me(self):
        app = create_saas_http_app()
        client = app
        response = client.post('/auth/login', json={
            'tenant_name': '云端物业',
            'project_name': '云端项目',
            'username': 'admin',
            'role_code': 'system_admin',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('session_id', response.cookies)
        me = client.get('/auth/me')
        self.assertEqual(me.status_code, 200)
        data = me.json()
        self.assertEqual(data['tenant_name'], '云端物业')
        self.assertEqual(data['project_name'], '云端项目')
        self.assertEqual(data['role_code'], 'system_admin')

    def test_unauthenticated_request_is_rejected(self):
        client = create_saas_http_app()
        response = client.get('/auth/me')
        self.assertEqual(response.status_code, 401)

    def test_tenant_context_limits_charge_targets_api(self):
        client_a = create_saas_http_app()
        login_a = client_a.post('/auth/login', json={
            'tenant_name': 'A物业', 'project_name': 'A项目', 'username': 'finance_a', 'role_code': 'finance'
        })
        self.assertEqual(login_a.status_code, 200)
        created = client_a.post('/charge-targets', json={
            'building': '住宅楼', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        })
        self.assertEqual(created.status_code, 200)
        self.assertEqual(len(client_a.get('/charge-targets').json()['items']), 1)

        client_b = create_saas_http_app()
        client_b.post('/auth/login', json={
            'tenant_name': 'B物业', 'project_name': 'B项目', 'username': 'finance_b', 'role_code': 'finance'
        })
        self.assertEqual(len(client_b.get('/charge-targets').json()['items']), 0)

    def test_readonly_user_cannot_post_charge_target(self):
        client = create_saas_http_app()
        client.post('/auth/login', json={
            'tenant_name': '只读物业', 'project_name': '只读项目', 'username': 'reader', 'role_code': 'executive'
        })
        response = client.post('/charge-targets', json={
            'building': '住宅楼', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        })
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
