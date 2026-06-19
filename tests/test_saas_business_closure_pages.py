import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasBusinessClosurePages(unittest.TestCase):
    def _client(self):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '闭环物业',
            'project_name': '闭环项目',
            'username': 'finance',
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_core_business_pages_show_closure_steps_and_next_links(self):
        client = self._client()
        expectations = {
            '/backoffice/charge-targets': ['业务闭环', '第 1 步', '下一步：配置收费项目', '/backoffice/fee-types'],
            '/backoffice/fee-types': ['业务闭环', '第 2 步', '下一步：生成账单', '/backoffice/bills'],
            '/backoffice/bills': ['业务闭环', '第 3 步', '第 4 步', '下一步：登记收款', '/backoffice/payments'],
            '/backoffice/payments': ['业务闭环', '第 5 步', '下一步：查看对账报表', '/backoffice/reports'],
            '/backoffice/reports': ['业务闭环', '第 6 步', '可导出账单或收款记录', '/api/exports/bills', '/api/exports/payments'],
        }
        for path, texts in expectations.items():
            page = client.get(path)
            self.assertEqual(page.status_code, 200, path)
            for text in texts:
                self.assertIn(text, page.text, f'{text} missing from {path}')
            self.assertIn('当前租户和项目隔离', page.text, path)


if __name__ == '__main__':
    unittest.main()
