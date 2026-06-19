import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasPermissionPages(unittest.TestCase):
    def _client(self, role_code='system_admin'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '权限物业',
            'project_name': '权限项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_permission_matrix(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('权限矩阵', page.text)
        self.assertIn('/backoffice/permissions', page.text)

    def test_permission_matrix_documents_roles_and_boundaries(self):
        client = self._client('finance')
        page = client.get('/backoffice/permissions')
        self.assertEqual(page.status_code, 200)
        html = page.text
        for text in [
            '权限矩阵',
            '平台管理员',
            '租户管理员',
            '财务',
            '收费员',
            '客服业务编辑',
            '管理层只读',
            '可做',
            '不可做',
            '租户隔离',
            '平台管理员不能直接创建客户员工',
            '租户管理员只能管理本公司员工',
            '收费员可收款但不能改收费项目',
            '管理层只读不能提交业务写入',
            '密码不展示在页面、日志或审计明细',
        ]:
            self.assertIn(text, html)
        self.assertNotIn('POSTGRES_PASSWORD=', html)
        self.assertNotIn('APP_SECRET_KEY=', html)

    def test_permission_matrix_requires_login(self):
        client = TestClient(create_app())
        page = client.get('/backoffice/permissions')
        self.assertEqual(page.status_code, 401)


if __name__ == '__main__':
    unittest.main()
