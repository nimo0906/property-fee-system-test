import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasReportPageEnhancements(unittest.TestCase):
    def _client(self, database_url, tenant_name='增强报表物业', project_name='增强报表项目', role_code='finance'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_bill_with_payment(self, client, period, room, due_amount, payment_amount):
        target = client.post('/api/charge-targets', json={
            'building': '5栋', 'unit': '5单元', 'room_number': room, 'category': '居民', 'area': due_amount,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': f'物业费{room}', 'unit_price': 1}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': period,
            'service_start': f'{period}-01', 'service_end': f'{period}-28',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve", json={})
        if payment_amount:
            payment = client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': payment_amount, 'method': 'cash',
                'idempotency_key': f'REPORT-ENH-{period}-{room}',
            })
            self.assertEqual(payment.status_code, 200)
        return bill

    def test_report_page_has_commercial_summary_rates_and_period_exports(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            self._seed_bill_with_payment(client, '2026-10', '501', 100, 100)
            self._seed_bill_with_payment(client, '2026-10', '502', 300, 50)
            self._seed_bill_with_payment(client, '2026-11', '503', 900, 900)

            page = client.get('/backoffice/reports?period=2026-10')

            self.assertEqual(page.status_code, 200)
            for text in ['对账报表', '高级筛选', '经营摘要', '收缴率', '欠费率', '导出账单', '导出收款流水', '欠费提醒']:
                self.assertIn(text, page.text)
            self.assertIn('37.50%', page.text)
            self.assertIn('62.50%', page.text)
            self.assertIn('/api/exports/bills?period=2026-10', page.text)
            self.assertIn('/api/exports/payments?period=2026-10', page.text)
            self.assertIn('400.0', page.text)
            self.assertIn('150.0', page.text)
            self.assertIn('250.0', page.text)
            self.assertNotIn('900.0</div>', page.text)

    def test_empty_report_page_shows_zero_rates_without_cross_tenant_data_or_internal_fields(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A增强报表物业', project_name='A增强报表项目')
            self._seed_bill_with_payment(client_a, '2026-10', '601', 500, 500)

            client_b = self._client(db_url, tenant_name='B增强报表物业', project_name='B增强报表项目')
            page = client_b.get('/backoffice/reports?period=2026-10')

            self.assertEqual(page.status_code, 200)
            self.assertIn('0.00%', page.text)
            self.assertIn('暂无欠费', page.text)
            self.assertNotIn('500.0</div>', page.text)
            for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'password']:
                self.assertNotIn(hidden, page.text)


if __name__ == '__main__':
    unittest.main()
