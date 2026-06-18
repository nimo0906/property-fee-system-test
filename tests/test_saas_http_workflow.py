import unittest

from server.saas_http import create_saas_http_app


class TestSaasHttpWorkflow(unittest.TestCase):
    def test_empty_tenant_can_import_bill_pay_and_report(self):
        client = create_saas_http_app()
        login = client.post('/auth/login', json={
            'tenant_name': '流程物业', 'project_name': '流程项目', 'username': 'finance', 'role_code': 'finance'
        })
        self.assertEqual(login.status_code, 200)
        fee = client.post('/fee-types', json={'name': '物业费', 'unit_price': 2.5})
        self.assertEqual(fee.status_code, 200)
        preview = client.post('/imports/charge-targets/preview', json={
            'rows': [
                {'building': '住宅楼', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
                {'building': '住宅楼', 'unit': '1单元', 'room_number': '102', 'category': '居民', 'area': 'bad'},
            ]
        })
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['valid_count'], 1)
        self.assertEqual(len(client.get('/charge-targets').json()['items']), 0)
        confirmed = client.post('/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()['created_count'], 1)
        target_id = client.get('/charge-targets').json()['items'][0]['id']
        bill = client.post('/bills/generate', json={
            'target_id': target_id,
            'fee_type_id': fee.json()['item']['id'],
            'billing_period': '2026-06',
            'service_start': '2026-06-01',
            'service_end': '2026-06-30',
        })
        self.assertEqual(bill.status_code, 200)
        self.assertEqual(bill.json()['item']['amount'], 200.0)
        paid = client.post('/payments', json={
            'bill_id': bill.json()['item']['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'P-001'
        })
        self.assertEqual(paid.status_code, 200)
        paid_again = client.post('/payments', json={
            'bill_id': bill.json()['item']['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'P-001'
        })
        self.assertEqual(paid.json()['item']['id'], paid_again.json()['item']['id'])
        report = client.get('/reports/summary?period=2026-06')
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()['bill_amount_total'], 200.0)
        self.assertEqual(report.json()['payment_amount_total'], 50.0)
        self.assertEqual(report.json()['unpaid_amount_total'], 150.0)

    def test_cashier_can_pay_but_cannot_generate_bill(self):
        client = create_saas_http_app()
        client.post('/auth/login', json={
            'tenant_name': '收费物业', 'project_name': '收费项目', 'username': 'cashier', 'role_code': 'cashier'
        })
        response = client.post('/bills/generate', json={
            'target_id': 1, 'fee_type_id': 1, 'billing_period': '2026-06',
            'service_start': '2026-06-01', 'service_end': '2026-06-30'
        })
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
