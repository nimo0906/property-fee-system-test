import html
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


    def test_payment_export_preserves_and_applies_current_filters(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            bill_101 = self._create_paid_bill(client, '101', '2026-08', 100, 'cash', 'PAY-EXPORT-FILTER-1')
            bill_102 = self._create_paid_bill(client, '102', '2026-08', 200, 'transfer', 'PAY-EXPORT-FILTER-2')
            bill_103 = self._create_paid_bill(client, '103', '2026-09', 100, 'cash', 'PAY-EXPORT-FILTER-3')

            page = client.get(
                f"/backoffice/payments?keyword={quote(bill_101['bill_number'])}&period=2026-08&method=cash&amount_min=90&amount_max=120"
            )
            self.assertEqual(page.status_code, 200)
            expected_href = (
                f"/api/exports/payments?keyword={quote(bill_101['bill_number'])}"
                "&period=2026-08&method=cash&amount_min=90&amount_max=120"
            )
            self.assertIn(html.escape(expected_href, quote=True), page.text)

            exported = client.get(expected_href)
            self.assertEqual(exported.status_code, 200)
            content = exported.json()['content']
            self.assertIn(bill_101['bill_number'], content)
            self.assertNotIn(bill_102['bill_number'], content)
            self.assertNotIn(bill_103['bill_number'], content)

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

    def test_receipt_detail_can_export_current_receipt_csv_with_tenant_scope(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A收据导出物业', project_name='A收据导出项目')
            bill = self._create_paid_bill(client_a, '401', '2026-11', 77, 'cash', 'RECEIPT-EXPORT-A')
            receipt = client_a.get('/backoffice/payments/1/receipt')
            self.assertEqual(receipt.status_code, 200)
            self.assertIn('/api/exports/receipts/1.csv', receipt.text)

            exported = client_a.get('/api/exports/receipts/1.csv')
            self.assertEqual(exported.status_code, 200)
            data = exported.json()
            self.assertEqual(data['filename'], 'receipt-1.csv')
            content = data['content']
            self.assertIn('receipt_number,bill_number,billing_period,building,unit,room_number,shop_name,tenant_name,owner_name,amount_paid,method,paid_amount,unpaid_amount', content)
            self.assertIn('RCPT-', content)
            self.assertIn(bill['bill_number'], content)
            self.assertIn('77.0', content)
            for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
                self.assertNotIn(hidden, content)

            client_b = self._client(db_url, tenant_name='B收据导出物业', project_name='B收据导出项目')
            blocked = client_b.get('/api/exports/receipts/1.csv')
            self.assertEqual(blocked.status_code, 404)

    def test_receipt_detail_has_browser_print_controls_without_internal_fields(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, tenant_name='打印收据物业', project_name='打印收据项目')
            bill = self._create_paid_bill(client, '301', '2026-10', 66, 'cash', 'RECEIPT-PRINT-1')

            receipt = client.get('/backoffice/payments/1/receipt')

            self.assertEqual(receipt.status_code, 200)
            for text in ['打印收据', 'window.print()', '@media print', 'receipt-print-area', '打印收据物业', '打印收据项目', bill['bill_number']]:
                self.assertIn(text, receipt.text)
            for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
                self.assertNotIn(hidden, receipt.text)


    def test_backoffice_payment_create_message_shows_receipt_number(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, tenant_name='收款回执物业', project_name='收款回执项目')
            bill = self._create_paid_bill(client, '601', '2027-03', 100, 'cash', 'PAYMENT-CREATE-RECEIPT-SETUP')

            target = client.post('/api/charge-targets', json={
                'building': '6栋', 'unit': '1单元', 'room_number': '602', 'category': '居民', 'area': 80,
            }).json()['item']
            fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 1}).json()['item']
            new_bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-03',
                'service_start': '2027-03-01', 'service_end': '2027-03-31',
            }).json()['item']
            client.post(f"/api/bills/{new_bill['id']}/approve", json={})

            response = client.post('/backoffice/payments/create', data={
                'bill_id': str(new_bill['id']), 'amount': '80', 'method': 'transfer', 'idempotency_key': 'PAYMENT-CREATE-RECEIPT-1',
            }, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            page = client.get(response.headers['location'])

            self.assertEqual(page.status_code, 200)
            self.assertIn('收款已登记', page.text)
            self.assertIn('收据号 RCPT-', page.text)

    def test_payment_list_shows_balance_after_each_partial_payment(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, tenant_name='列表分次收款物业', project_name='列表分次收款项目')
            target = client.post('/api/charge-targets', json={
                'building': '5栋', 'unit': '2单元', 'room_number': '502', 'category': '居民', 'area': 100,
            }).json()['item']
            fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-02',
                'service_start': '2027-02-01', 'service_end': '2027-02-28',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 60, 'method': 'cash', 'idempotency_key': 'PAYMENT-LIST-PARTIAL-1',
            })
            client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 140, 'method': 'cash', 'idempotency_key': 'PAYMENT-LIST-PARTIAL-2',
            })

            page = client.get('/backoffice/payments?period=2027-02')

            self.assertEqual(page.status_code, 200)
            for text in ['本次收款', '收后累计已收', '收后欠费余额']:
                self.assertIn(text, page.text)
            self.assertIn('<td>60.0</td><td>60.0</td><td>140.0</td><td>cash</td>', page.text)
            self.assertIn('<td>140.0</td><td>200.0</td><td>0.0</td><td>cash</td>', page.text)


    def test_receipt_detail_shows_balance_after_each_partial_payment(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, tenant_name='分次收款物业', project_name='分次收款项目')
            target = client.post('/api/charge-targets', json={
                'building': '2栋', 'unit': '1单元', 'room_number': '201', 'category': '居民', 'area': 100,
            }).json()['item']
            fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-01',
                'service_start': '2027-01-01', 'service_end': '2027-01-31',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            first = client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 80, 'method': 'cash', 'idempotency_key': 'RECEIPT-PARTIAL-1',
            }).json()['item']
            second = client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 120, 'method': 'cash', 'idempotency_key': 'RECEIPT-PARTIAL-2',
            }).json()['item']

            first_receipt = client.get(f"/backoffice/payments/{first['id']}/receipt")
            self.assertEqual(first_receipt.status_code, 200)
            self.assertIn('<th>本次收款</th><td>80.0</td>', first_receipt.text)
            self.assertIn('<th>收后累计已收</th><td>80.0</td>', first_receipt.text)
            self.assertIn('<th>收后欠费余额</th><td>120.0</td>', first_receipt.text)

            second_receipt = client.get(f"/backoffice/payments/{second['id']}/receipt")
            self.assertEqual(second_receipt.status_code, 200)
            self.assertIn('<th>本次收款</th><td>120.0</td>', second_receipt.text)
            self.assertIn('<th>收后累计已收</th><td>200.0</td>', second_receipt.text)
            self.assertIn('<th>收后欠费余额</th><td>0.0</td>', second_receipt.text)

            exported = client.get(f"/api/exports/receipts/{first['id']}.csv")
            self.assertEqual(exported.status_code, 200)
            content = exported.json()['content']
            self.assertIn('amount_paid,method,paid_amount,unpaid_amount', content)
            self.assertIn('80.0,cash,80.0,120.0', content)


if __name__ == '__main__':
    unittest.main()
