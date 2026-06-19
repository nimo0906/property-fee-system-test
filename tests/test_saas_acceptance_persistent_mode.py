import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasAcceptancePersistentMode(unittest.TestCase):
    def test_acceptance_script_reports_persistent_mode(self):
        result = subprocess.run(
            [sys.executable, 'scripts/saas_acceptance_check.py'],
            cwd=Path.cwd(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('PASS saas acceptance workflow memory', result.stdout)
        self.assertIn('PASS saas acceptance workflow persistent', result.stdout)
        self.assertIn('PASS saas acceptance isolation persistent', result.stdout)
        self.assertIn('PASS saas acceptance account boundary persistent', result.stdout)
        self.assertIn('PASS saas acceptance import upload persistent', result.stdout)

    def test_persistent_billing_payment_report_records_survive_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            client.post('/api/auth/login', json={
                'tenant_name': '持久验收物业', 'project_name': '持久验收项目', 'username': 'admin', 'role_code': 'system_admin'
            })
            target = client.post('/api/charge-targets', json={
                'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
            })
            self.assertEqual(target.status_code, 200)
            fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5})
            self.assertEqual(fee.status_code, 200)
            bill = client.post('/api/bills/generate', json={
                'target_id': target.json()['item']['id'], 'fee_type_id': fee.json()['item']['id'],
                'billing_period': '2026-06', 'service_start': '2026-06-01', 'service_end': '2026-06-30'
            })
            self.assertEqual(bill.status_code, 200)
            self.assertEqual(bill.json()['item']['status'], 'pending_review')
            self.assertEqual(client.post(f"/api/bills/{bill.json()['item']['id']}/approve", json={}).status_code, 200)
            payment = client.post('/api/payments', json={
                'bill_id': bill.json()['item']['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'PERSIST-PAY-1'
            })
            self.assertEqual(payment.status_code, 200)
            repo = create_saas_repository(db_url)
            tenants = repo.list_tenants()
            projects = repo.list_projects()
            bills = repo.search_bills(tenants[0]['id'], projects[0]['id'], keyword='101')
            payments = repo.search_payments(tenants[0]['id'], projects[0]['id'], keyword=payment.json()['item']['receipt_number'])
            self.assertEqual(bills['total'], 1)
            self.assertEqual(payments['total'], 1)
            repo.close()


if __name__ == '__main__':
    unittest.main()
