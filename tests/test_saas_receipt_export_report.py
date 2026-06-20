import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository
from server.saas_service import SaasBackofficeService


class TestSaasReceiptExportReport(unittest.TestCase):
    def setUp(self):
        self.service = SaasBackofficeService.in_memory()
        self.tenant = self.service.create_tenant('收据物业')
        self.project = self.service.create_project(self.tenant, '收据项目')
        self.finance = self.service.create_user(self.tenant, 'finance', 'finance')
        self.target = self.service.create_charge_target(self.finance, self.project, '1栋', '1单元', '101', '居民', 80)
        self.fee = self.service.create_fee_type(self.finance, self.project, '物业费', 2.5)
        self.bill = self.service.generate_bill(self.finance, self.project, self.target, self.fee, '2026-06', '2026-06-01', '2026-06-30')
        self.service.approve_bill(self.finance, self.project, self.bill['id'])

    def test_payment_gets_receipt_number_and_report_balances(self):
        payment = self.service.record_payment(self.finance, self.bill['id'], 50, 'cash', 'R-1')
        self.assertTrue(payment['receipt_number'].startswith('RCPT-'))
        report = self.service.report(self.finance, self.project, '2026-06')
        self.assertEqual(report['bill_count'], 1)
        self.assertEqual(report['bill_amount_total'], 200.0)
        self.assertEqual(report['payment_amount_total'], 50.0)
        self.assertEqual(report['unpaid_amount_total'], 150.0)

    def test_export_bills_and_payments_are_tenant_scoped(self):
        payment = self.service.record_payment(self.finance, self.bill['id'], 50, 'cash', 'R-2')
        bills = self.service.export_bills(self.finance, self.project, period='2026-06')
        payments = self.service.export_payments(self.finance, self.project, period='2026-06')
        self.assertEqual(bills['filename'], 'bills-2026-06.csv')
        self.assertIn('bill_number,billing_period,building,unit,room_number,shop_name,tenant_name,owner_name,fee_name,amount,paid_amount,unpaid_amount,status', bills['content'])
        self.assertIn(self.bill['bill_number'], bills['content'])
        self.assertEqual(payments['filename'], 'payments-2026-06.csv')
        self.assertIn('receipt_number,bill_number,billing_period,building,unit,room_number,shop_name,tenant_name,owner_name,amount_paid,method,paid_amount,unpaid_amount', payments['content'])
        self.assertIn(payment['receipt_number'], payments['content'])
        self.assertIn('50.0,cash,50.0,150.0', payments['content'])


class TestSaasFastApiReceiptExportReport(unittest.TestCase):
    def test_api_export_bills_payments_and_report(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': 'API导出物业', 'project_name': 'API导出项目', 'username': 'finance', 'role_code': 'finance'
        })
        target = client.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-06',
            'service_start': '2026-06-01', 'service_end': '2026-06-30'
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve", json={})
        payment = client.post('/api/payments', json={'bill_id': bill['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'API-R-1'})
        self.assertEqual(payment.status_code, 200)
        self.assertTrue(payment.json()['item']['receipt_number'].startswith('RCPT-'))
        bills = client.get('/api/exports/bills?period=2026-06')
        payments = client.get('/api/exports/payments?period=2026-06')
        report = client.get('/api/reports/summary?period=2026-06')
        self.assertEqual(bills.status_code, 200)
        self.assertEqual(payments.status_code, 200)
        self.assertIn('bills-2026-06.csv', bills.json()['filename'])
        self.assertIn(payment.json()['item']['receipt_number'], payments.json()['content'])
        self.assertEqual(report.json()['unpaid_amount_total'], 150.0)
        self.assertEqual(report.json()['collection_rate'], '25.00%')
        self.assertEqual(report.json()['arrears_rate'], '75.00%')


class TestSaasRepositoryReceiptExportReport(unittest.TestCase):
    def test_repository_persists_receipt_number(self):
        with tempfile.TemporaryDirectory() as td:
            repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            tenant = repo.create_tenant('持久收据物业')
            project = repo.create_project(tenant['id'], '持久收据项目')
            target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 80)
            fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2.5)
            bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2026-06', '2026-06-01', '2026-06-30', 200)
            repo.approve_bill(tenant['id'], project['id'], bill['id'])
            payment = repo.create_payment(tenant['id'], project['id'], bill['id'], 50, 'cash', 'RP-1')
            self.assertTrue(payment['receipt_number'].startswith('RCPT-'))
            self.assertEqual(repo.report_summary(tenant['id'], project['id'], '2026-06')['unpaid_amount_total'], 150.0)
            repo.close()


if __name__ == '__main__':
    unittest.main()
