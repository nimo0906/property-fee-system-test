import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasMerchantWorkbenchPages(unittest.TestCase):
    def _client(self, database_url):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '商户工作台物业',
            'project_name': '商户工作台项目',
            'username': 'finance',
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_merchant_page_looks_like_commercial_charge_workbench(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            target = client.post('/api/charge-targets', json={
                'building': '商场', 'unit': '一层', 'room_number': 'M-101', 'category': '商户',
                'area': 50, 'shop_name': '奶茶店', 'tenant_name': '王商户', 'tenant_phone': '13800000000',
                'unit_price_override': 5.0, 'payment_cycle': 'monthly',
            }).json()['item']
            fee = client.post('/api/fee-types', json={'name': '商户物业费', 'unit_price': 3.0}).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-07',
                'service_start': '2027-07-01', 'service_end': '2027-07-31',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 100, 'method': 'cash', 'idempotency_key': 'MERCHANT-WORKBENCH-PAY-1',
            })

            page = client.get('/backoffice/merchants')

            self.assertEqual(page.status_code, 200)
            for text in [
                '商户收费工作台', '商户总数', '欠费商户', '商户应收', '商户实收', '商户欠费',
                '商户收费流程', '维护商户档案', '生成商户账单', '登记商户收款', '查看欠费商户', '导出商户清单',
                '/backoffice/merchants?arrears=1', '/backoffice/payments?target_id=', '/api/merchants/export.csv',
                'M-101', '奶茶店', '王商户', '250.0', '100.0', '150.0',
            ]:
                self.assertIn(text, page.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
                self.assertNotIn(hidden, page.text)


if __name__ == '__main__':
    unittest.main()
