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

    def test_merchant_directory_page_can_create_merchant_charge_target(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")

            response = client.post('/backoffice/merchants/create', data={
                'building': '商场B区',
                'unit': '二层',
                'space_no': 'B-208',
                'floor': '2',
                'shop_name': '咖啡店',
                'merchant_name': '王商户',
                'phone': '13900000000',
                'area': '66.5',
                'unit_price_override': '8.8',
                'payment_cycle': 'quarterly',
                'notes': '新签商户',
            }, follow_redirects=False)

            self.assertEqual(response.status_code, 303)
            self.assertIn('/backoffice/merchants', response.headers.get('location', ''))
            data = client.get('/api/merchants').json()
            self.assertEqual(data['total'], 1)
            merchant = data['items'][0]
            self.assertEqual(merchant['space_no'], 'B-208')
            self.assertEqual(merchant['shop_name'], '咖啡店')
            self.assertEqual(merchant['merchant_name'], '王商户')
            self.assertEqual(merchant['phone'], '13900000000')
            self.assertEqual(merchant['unit_price_override'], 8.8)
            self.assertEqual(merchant['payment_cycle'], 'quarterly')
            page = client.get(response.headers['location'])
            for text in ['商户已新增', 'B-208', '咖啡店', '王商户', '8.8', 'quarterly']:
                self.assertIn(text, page.text)

    def test_merchant_directory_supports_search_and_pagination(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            for index in range(1, 6):
                self._create_target(
                    client,
                    room_number=f'C-{index:03d}',
                    shop_name=f'品牌{index}',
                    tenant_name=f'商户{index}',
                    tenant_phone=f'1390000000{index}',
                )

            api = client.get('/api/merchants?keyword=品牌3&page=1&page_size=2')
            self.assertEqual(api.status_code, 200)
            data = api.json()
            self.assertEqual(data['total'], 1)
            self.assertEqual(data['page'], 1)
            self.assertEqual(data['page_size'], 2)
            self.assertEqual([item['space_no'] for item in data['items']], ['C-003'])

            page = client.get('/backoffice/merchants?keyword=品牌&page=2&page_size=2')
            self.assertEqual(page.status_code, 200)
            self.assertIn('商户检索', page.text)
            self.assertIn('共 5 个商户', page.text)
            self.assertIn('第 2 页', page.text)
            self.assertIn('C-003', page.text)
            self.assertIn('C-004', page.text)
            self.assertNotIn('C-001', page.text)
            self.assertNotIn('C-005', page.text)

    def test_merchant_directory_can_generate_bill_for_selected_merchant(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            target = self._create_target(client, room_number='D-101', shop_name='账单店', tenant_name='账单商户', area=50, unit_price_override=7.0)
            fee = client.post('/api/fee-types', json={'name': '商户物业费', 'unit_price': 3.0}).json()['item']
            page = client.get('/backoffice/merchants')
            self.assertIn('生成商户账单', page.text)
            self.assertIn('商户物业费', page.text)

            response = client.post('/backoffice/merchants/generate-bill', data={
                'target_id': str(target['id']),
                'fee_type_id': str(fee['id']),
                'billing_period': '2027-01',
                'service_start': '2027-01-01',
                'service_end': '2027-01-31',
            }, follow_redirects=False)

            self.assertEqual(response.status_code, 303)
            bills = client.get('/api/bills?period=2027-01').json()['items']
            self.assertEqual(len(bills), 1)
            self.assertEqual(bills[0]['charge_target_id'], target['id'])
            self.assertEqual(bills[0]['fee_type_id'], fee['id'])
            self.assertEqual(bills[0]['amount'], 350.0)
            result_page = client.get(response.headers['location'])
            self.assertIn('商户账单已生成', result_page.text)
            self.assertIn('D-101', result_page.text)


if __name__ == '__main__':
    unittest.main()
