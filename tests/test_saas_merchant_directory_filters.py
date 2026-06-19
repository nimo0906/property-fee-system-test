import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasMerchantDirectoryFilters(unittest.TestCase):
    def _client(self, database_url):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '商户筛选物业',
            'project_name': '商户筛选项目',
            'username': 'finance',
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _create_target(self, client, **overrides):
        payload = {
            'building': '商场筛选区', 'unit': '一层', 'room_number': 'F-101',
            'category': '商户', 'area': 88.5, 'floor': 1, 'shop_name': '筛选店',
            'tenant_name': '筛选商户', 'tenant_phone': '13800000000',
            'unit_price_override': 6.5, 'payment_cycle': 'monthly', 'notes': '筛选测试',
        }
        payload.update(overrides)
        response = client.post('/api/charge-targets', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['item']

    def test_merchant_directory_can_filter_arrears_in_api_page_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            arrears_target = self._create_target(client, room_number='AR-FILTER', shop_name='欠费筛选店', tenant_name='欠费筛选商户', area=80, unit_price_override=4.0)
            paid_target = self._create_target(client, room_number='PAID-FILTER', shop_name='已清筛选店', tenant_name='已清筛选商户', area=30, unit_price_override=2.0)
            self._create_target(client, room_number='NO-BILL', shop_name='未出账店', tenant_name='未出账商户', area=20, unit_price_override=3.0)
            fee = client.post('/api/fee-types', json={'name': '筛选物业费', 'unit_price': 1.0}).json()['item']
            arrears_bill = client.post('/api/bills/generate', json={
                'target_id': arrears_target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-06',
                'service_start': '2027-06-01', 'service_end': '2027-06-30',
            }).json()['item']
            paid_bill = client.post('/api/bills/generate', json={
                'target_id': paid_target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-06',
                'service_start': '2027-06-01', 'service_end': '2027-06-30',
            }).json()['item']
            client.post(f"/api/bills/{arrears_bill['id']}/approve", json={})
            client.post(f"/api/bills/{paid_bill['id']}/approve", json={})
            client.post('/api/payments', json={
                'bill_id': paid_bill['id'], 'amount': 60, 'method': 'cash',
                'idempotency_key': 'MERCHANT-ARREARS-FILTER-PAID',
            })

            api = client.get('/api/merchants?arrears=1')
            self.assertEqual(api.status_code, 200)
            self.assertEqual(api.json()['total'], 1)
            self.assertEqual(api.json()['items'][0]['space_no'], 'AR-FILTER')

            page = client.get('/backoffice/merchants?arrears=1')
            self.assertEqual(page.status_code, 200)
            for expected in ['仅看欠费商户', 'AR-FILTER', '欠费筛选店', '320.0']:
                self.assertIn(expected, page.text)
            for hidden in ['PAID-FILTER', 'NO-BILL', 'tenant_id', 'project_id']:
                self.assertNotIn(hidden, page.text)

            csv_response = client.get('/api/merchants/export.csv?arrears=1')
            self.assertEqual(csv_response.status_code, 200)
            csv_text = csv_response.content.decode('utf-8-sig')
            self.assertIn('AR-FILTER', csv_text)
            self.assertIn('320.0', csv_text)
            self.assertNotIn('PAID-FILTER', csv_text)
            self.assertNotIn('NO-BILL', csv_text)

    def test_merchant_directory_can_filter_by_building_and_unit_in_api_page_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            self._create_target(client, room_number='A-201', building='商场A区', unit='二层', shop_name='A区二层店')
            self._create_target(client, room_number='A-101', building='商场A区', unit='一层', shop_name='A区一层店')
            self._create_target(client, room_number='B-201', building='商场B区', unit='二层', shop_name='B区二层店')

            api = client.get('/api/merchants?building=商场A区&unit=二层')
            self.assertEqual(api.status_code, 200)
            self.assertEqual(api.json()['total'], 1)
            self.assertEqual(api.json()['items'][0]['space_no'], 'A-201')

            page = client.get('/backoffice/merchants?building=商场A区&unit=二层')
            self.assertEqual(page.status_code, 200)
            for expected in ['楼栋 / 区域', '分区', '商场A区', '二层', 'A-201', 'A区二层店']:
                self.assertIn(expected, page.text)
            for hidden in ['A-101', 'B-201', 'tenant_id', 'project_id']:
                self.assertNotIn(hidden, page.text)

            csv_response = client.get('/api/merchants/export.csv?building=商场A区&unit=二层')
            self.assertEqual(csv_response.status_code, 200)
            csv_text = csv_response.content.decode('utf-8-sig')
            self.assertIn('A-201', csv_text)
            self.assertIn('A区二层店', csv_text)
            self.assertNotIn('A-101', csv_text)
            self.assertNotIn('B-201', csv_text)

    def test_merchant_directory_links_arrears_merchant_to_target_payment_page(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            arrears_target = self._create_target(client, room_number='PAY-101', shop_name='快捷收款店', tenant_name='快捷商户', area=80, unit_price_override=4.0)
            other_target = self._create_target(client, room_number='PAY-102', shop_name='其他收款店', tenant_name='其他商户', area=30, unit_price_override=2.0)
            fee = client.post('/api/fee-types', json={'name': '快捷收款物业费', 'unit_price': 1.0}).json()['item']
            arrears_bill = client.post('/api/bills/generate', json={
                'target_id': arrears_target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-07',
                'service_start': '2027-07-01', 'service_end': '2027-07-31',
            }).json()['item']
            other_bill = client.post('/api/bills/generate', json={
                'target_id': other_target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-07',
                'service_start': '2027-07-01', 'service_end': '2027-07-31',
            }).json()['item']
            client.post(f"/api/bills/{arrears_bill['id']}/approve", json={})
            client.post(f"/api/bills/{other_bill['id']}/approve", json={})

            merchant_page = client.get('/backoffice/merchants?arrears=1')
            self.assertEqual(merchant_page.status_code, 200)
            payment_href = f"/backoffice/payments?target_id={arrears_target['id']}"
            self.assertIn('登记收款', merchant_page.text)
            self.assertIn(payment_href, merchant_page.text)

            payment_page = client.get(payment_href)
            self.assertEqual(payment_page.status_code, 200)
            self.assertIn('快捷收款店', payment_page.text)
            self.assertIn(arrears_bill['bill_number'], payment_page.text)
            self.assertNotIn(other_bill['bill_number'], payment_page.text)
            for hidden in ['tenant_id', 'project_id']:
                self.assertNotIn(hidden, payment_page.text)


if __name__ == '__main__':
    unittest.main()
