import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasPaymentSearchReceiptPages(unittest.TestCase):
    def _client(self, database_url, tenant_name='收款筛选物业', project_name='收款筛选项目', role_code='finance'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _create_paid_bill(self, client, room, period, amount, method, key):
        target = client.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': room, 'category': '居民', 'area': amount,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': f'物业费{room}', 'unit_price': 1}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': period,
            'service_start': f'{period}-01', 'service_end': f'{period}-28',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve", json={})
        payment = client.post('/backoffice/payments/create', data={
            'bill_id': str(bill['id']), 'amount': str(amount), 'method': method, 'idempotency_key': key,
        }, follow_redirects=False)
        self.assertEqual(payment.status_code, 303)
        return bill

    def test_payment_page_has_advanced_filters_pagination_and_export_link(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            self._create_paid_bill(client, '101', '2026-08', 100, 'cash', 'PAY-FILTER-1')

            page = client.get('/backoffice/payments?period=2026-08&method=cash&amount_min=90&amount_max=120&page_size=1')

            self.assertEqual(page.status_code, 200)
            for text in ['高级筛选', '导出收款流水', '上一页', '下一页']:
                self.assertIn(text, page.text)
            for field in ['keyword', 'period', 'method', 'amount_min', 'amount_max', 'page_size']:
                self.assertIn(f'name="{field}"', page.text)
            self.assertIn('/api/exports/payments?period=2026-08', page.text)

    def test_payment_page_filters_by_period_method_amount_keyword_and_paginates(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            bill_101 = self._create_paid_bill(client, '101', '2026-08', 100, 'cash', 'PAY-SEARCH-1')
            self._create_paid_bill(client, '102', '2026-08', 200, 'transfer', 'PAY-SEARCH-2')
            self._create_paid_bill(client, '103', '2026-09', 300, 'cash', 'PAY-SEARCH-3')

            filtered = client.get(
                f"/backoffice/payments?keyword={quote(bill_101['bill_number'])}&period=2026-08&method=cash&amount_min=90&amount_max=120&page=1&page_size=1"
            )

            self.assertEqual(filtered.status_code, 200)
            self.assertIn(bill_101['bill_number'], filtered.text)
            self.assertIn('cash', filtered.text)
            self.assertNotIn('transfer', filtered.text)
            self.assertNotIn('2026-09', filtered.text)

    def test_receipt_detail_is_tenant_scoped_and_hides_internal_ids_and_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A收据物业', project_name='A收据项目')
            bill = self._create_paid_bill(client_a, '201', '2026-08', 88, 'wechat-offline', 'RECEIPT-A-1')
            page = client_a.get('/backoffice/payments')
            self.assertEqual(page.status_code, 200)
            self.assertIn('/backoffice/payments/1/receipt', page.text)

            receipt = client_a.get('/backoffice/payments/1/receipt')
            self.assertEqual(receipt.status_code, 200)
            for text in ['收据详情', 'RCPT-', bill['bill_number'], '2026-08', '88.0', 'wechat-offline', 'A收据物业', 'A收据项目']:
                self.assertIn(text, receipt.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', 'password']:
                self.assertNotIn(hidden, receipt.text)

            client_b = self._client(db_url, tenant_name='B收据物业', project_name='B收据项目')
            blocked = client_b.get('/backoffice/payments/1/receipt')
            self.assertEqual(blocked.status_code, 404)


if __name__ == '__main__':
    unittest.main()
