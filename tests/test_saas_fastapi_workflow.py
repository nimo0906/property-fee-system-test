import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasFastApiWorkflow(unittest.TestCase):
    def test_fastapi_can_run_staff_backoffice_billing_payment_report_audit_flow(self):
        client = TestClient(create_app())
        login = client.post('/api/auth/login', json={
            'tenant_name': '流程物业', 'project_name': '流程项目', 'username': 'finance', 'role_code': 'finance'
        })
        self.assertEqual(login.status_code, 200)
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5})
        self.assertEqual(fee.status_code, 200)
        preview = client.post('/api/imports/charge-targets/preview', json={
            'rows': [
                {'building': '住宅楼', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
                {'building': '住宅楼', 'unit': '1单元', 'room_number': '102', 'category': '居民', 'area': 'bad'},
            ]
        })
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['valid_count'], 1)
        self.assertEqual(client.get('/api/charge-targets').json()['items'], [])
        confirmed = client.post('/api/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()['created_count'], 1)
        target_id = client.get('/api/charge-targets').json()['items'][0]['id']
        bill = client.post('/api/bills/generate', json={
            'target_id': target_id,
            'fee_type_id': fee.json()['item']['id'],
            'billing_period': '2026-06',
            'service_start': '2026-06-01',
            'service_end': '2026-06-30',
        })
        self.assertEqual(bill.status_code, 200)
        self.assertEqual(bill.json()['item']['amount'], 200.0)
        approved = client.post(f"/api/bills/{bill.json()['item']['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200)
        payment = client.post('/api/payments', json={
            'bill_id': bill.json()['item']['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'FAST-PAY-1'
        })
        self.assertEqual(payment.status_code, 200)
        payment_again = client.post('/api/payments', json={
            'bill_id': bill.json()['item']['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'FAST-PAY-1'
        })
        self.assertEqual(payment.json()['item']['id'], payment_again.json()['item']['id'])
        report = client.get('/api/reports/summary?period=2026-06')
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()['bill_amount_total'], 200.0)
        self.assertEqual(report.json()['payment_amount_total'], 50.0)
        self.assertEqual(report.json()['unpaid_amount_total'], 150.0)
        audit = client.get('/api/audit-logs')
        self.assertEqual(audit.status_code, 200)
        actions = [row['action'] for row in audit.json()['items']]
        self.assertIn('bill.generate', actions)
        self.assertIn('payment.record', actions)

    def test_fastapi_admin_backup_allowed_and_finance_backup_forbidden(self):
        finance = TestClient(create_app())
        finance.post('/api/auth/login', json={
            'tenant_name': '财务物业', 'project_name': '财务项目', 'username': 'finance', 'role_code': 'finance'
        })
        self.assertEqual(finance.post('/api/backups/create', json={}).status_code, 403)

        admin = TestClient(create_app())
        admin.post('/api/auth/login', json={
            'tenant_name': '管理物业', 'project_name': '管理项目', 'username': 'admin', 'role_code': 'system_admin'
        })
        backup = admin.post('/api/backups/create', json={})
        self.assertEqual(backup.status_code, 200)
        self.assertTrue(backup.json()['item']['backup_id'].startswith('backup-'))


if __name__ == '__main__':
    unittest.main()
