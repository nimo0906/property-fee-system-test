import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasMerchantDirectory(unittest.TestCase):
    def _client(self, database_url, tenant_name='商户档案物业', project_name='商户档案项目', role_code='finance'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _create_target(self, client, **overrides):
        payload = {
            'building': '商场A区', 'unit': '一层', 'room_number': 'A-101', 'category': '商户',
            'area': 88.5, 'floor': 1, 'shop_name': '花店', 'tenant_name': '张商户',
            'tenant_phone': '13800000000', 'unit_price_override': 6.5, 'payment_cycle': 'monthly',
            'notes': '临街铺位',
        }
        payload.update(overrides)
        response = client.post('/api/charge-targets', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['item']

    def test_merchant_directory_api_lists_only_commercial_targets_with_business_fields(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            self._create_target(client)
            self._create_target(client, room_number='A-102', category='商业', shop_name='便利店', tenant_name='李商户')
            self._create_target(client, room_number='R-101', category='居民', shop_name='住宅不应出现')

            response = client.get('/api/merchants')

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['total'], 2)
            self.assertEqual([item['space_no'] for item in data['items']], ['A-101', 'A-102'])
            first = data['items'][0]
            self.assertEqual(first['shop_name'], '花店')
            self.assertEqual(first['merchant_name'], '张商户')
            self.assertEqual(first['phone'], '13800000000')
            self.assertEqual(first['unit_price_override'], 6.5)
            self.assertEqual(first['payment_cycle'], 'monthly')
            for hidden in ['tenant_id', 'project_id']:
                self.assertNotIn(hidden, first)

    def test_merchant_directory_page_is_tenant_scoped_and_links_from_backoffice(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A商户物业', project_name='A商户项目')
            self._create_target(client_a, room_number='A-201', shop_name='A租户店', tenant_name='A商户')

            client_b = self._client(db_url, tenant_name='B商户物业', project_name='B商户项目')
            self._create_target(client_b, room_number='B-301', shop_name='B租户店', tenant_name='B商户')
            home = client_b.get('/backoffice')
            page = client_b.get('/backoffice/merchants')

            self.assertEqual(home.status_code, 200)
            self.assertIn('/backoffice/merchants', home.text)
            self.assertEqual(page.status_code, 200)
            for text in ['商户档案', '铺位号', '店名', '承租人', 'B-301', 'B租户店', 'B商户']:
                self.assertIn(text, page.text)
            self.assertNotIn('A租户店', page.text)
            for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
                self.assertNotIn(hidden, page.text)


if __name__ == '__main__':
    unittest.main()
