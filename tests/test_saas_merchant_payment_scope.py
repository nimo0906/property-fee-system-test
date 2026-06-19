import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasMerchantPaymentScope(unittest.TestCase):
    def _client(self, database_url):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '商户收款范围物业',
            'project_name': '商户收款范围项目',
            'username': 'finance',
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _create_target(self, client, **overrides):
        payload = {
            'building': '商场收款区', 'unit': '一层', 'room_number': 'P-101',
            'category': '商户', 'area': 88.5, 'floor': 1, 'shop_name': '收款店',
            'tenant_name': '收款商户', 'tenant_phone': '13800000000',
            'unit_price_override': 6.5, 'payment_cycle': 'monthly', 'notes': '收款测试',
        }
        payload.update(overrides)
        response = client.post('/api/charge-targets', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['item']

    def test_payment_target_filter_form_preserves_target_id(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            target = self._create_target(client, room_number='KEEP-101', shop_name='保留范围目标店', tenant_name='保留范围商户')
            page = client.get(f"/backoffice/payments?target_id={target['id']}")
            self.assertEqual(page.status_code, 200)

            hidden = f'name="target_id" value="{target["id"]}"'
            self.assertIn(hidden, page.text)
            for internal in ['tenant_id', 'project_id']:
                self.assertNotIn(internal, page.text)


    def test_payment_target_create_form_returns_to_target_scope_after_payment(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            target = self._create_target(client, room_number='RETURN-101', shop_name='返回范围目标店', tenant_name='返回范围商户', area=80, unit_price_override=4.0)
            other = self._create_target(client, room_number='RETURN-102', shop_name='返回范围其他店', tenant_name='返回范围其他商户', area=30, unit_price_override=2.0)
            fee = client.post('/api/fee-types', json={'name': '返回范围物业费', 'unit_price': 1.0}).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-12',
                'service_start': '2027-12-01', 'service_end': '2027-12-31',
            }).json()['item']
            other_bill = client.post('/api/bills/generate', json={
                'target_id': other['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-12',
                'service_start': '2027-12-01', 'service_end': '2027-12-31',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            client.post(f"/api/bills/{other_bill['id']}/approve", json={})

            page = client.get(f"/backoffice/payments?target_id={target['id']}")
            self.assertEqual(page.status_code, 200)
            self.assertIn(f'name="target_id" value="{target["id"]}"', page.text)

            response = client.post('/backoffice/payments/create', data={
                'bill_id': str(bill['id']),
                'amount': '120',
                'method': 'cash',
                'idempotency_key': 'MERCHANT-RETURN-TARGET',
                'target_id': str(target['id']),
            }, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertIn(f'target_id={target["id"]}', response.headers['location'])

            result_page = client.get(response.headers['location'])
            self.assertIn(bill['bill_number'], result_page.text)
            self.assertNotIn(other_bill['bill_number'], result_page.text)


    def test_payment_receipt_return_link_preserves_target_scope(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            target = self._create_target(client, room_number='RECEIPT-101', shop_name='收据目标店', tenant_name='收据目标商户', area=60, unit_price_override=5.0)
            other = self._create_target(client, room_number='RECEIPT-102', shop_name='收据其他店', tenant_name='收据其他商户', area=30, unit_price_override=2.0)
            fee = client.post('/api/fee-types', json={'name': '收据范围物业费', 'unit_price': 1.0}).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-01',
                'service_start': '2028-01-01', 'service_end': '2028-01-31',
            }).json()['item']
            other_bill = client.post('/api/bills/generate', json={
                'target_id': other['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-01',
                'service_start': '2028-01-01', 'service_end': '2028-01-31',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            client.post(f"/api/bills/{other_bill['id']}/approve", json={})
            payment = client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 100, 'method': 'cash',
                'idempotency_key': 'MERCHANT-RECEIPT-RETURN-TARGET',
            }).json()['item']

            list_page = client.get(f"/backoffice/payments?target_id={target['id']}")
            self.assertEqual(list_page.status_code, 200)
            receipt_href = f"/backoffice/payments/{payment['id']}/receipt?target_id={target['id']}"
            self.assertIn(receipt_href, list_page.text)

            receipt_page = client.get(receipt_href)
            self.assertEqual(receipt_page.status_code, 200)
            return_href = f"/backoffice/payments?target_id={target['id']}"
            self.assertIn(return_href, receipt_page.text)
            result_page = client.get(return_href)
            self.assertIn(bill['bill_number'], result_page.text)
            self.assertNotIn(other_bill['bill_number'], result_page.text)


if __name__ == '__main__':
    unittest.main()
