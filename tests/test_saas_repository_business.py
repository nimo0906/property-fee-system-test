import tempfile
import unittest
from pathlib import Path

from server.saas_repository import create_saas_repository


class TestSaasRepositoryBusiness(unittest.TestCase):
    def _repo(self):
        self.tmp = tempfile.TemporaryDirectory()
        return create_saas_repository(f"sqlite:///{Path(self.tmp.name) / 'saas.sqlite3'}")

    def tearDown(self):
        if hasattr(self, 'tmp'):
            self.tmp.cleanup()

    def test_repository_persists_billing_payment_report_and_audit(self):
        repo = self._repo()
        tenant = repo.create_tenant('业务物业')
        project = repo.create_project(tenant['id'], '业务项目')
        user = repo.create_user(tenant['id'], 'finance', 'finance')
        target = repo.create_charge_target(tenant['id'], project['id'], '住宅楼', '1单元', '101', '居民', 80)
        fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2.5)
        bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2026-06', '2026-06-01', '2026-06-30', 200)
        repo.approve_bill(tenant['id'], project['id'], bill['id'])
        payment = repo.create_payment(tenant['id'], project['id'], bill['id'], 50, 'cash', 'PAY-001')
        duplicate = repo.create_payment(tenant['id'], project['id'], bill['id'], 50, 'cash', 'PAY-001')
        self.assertEqual(payment['id'], duplicate['id'])
        repo.create_audit_log(tenant['id'], project['id'], user['id'], 'payment.record', 'payment', payment['id'], {'amount_paid': 50})
        report = repo.report_summary(tenant['id'], project['id'], '2026-06')
        self.assertEqual(report['bill_count'], 1)
        self.assertEqual(report['bill_amount_total'], 200.0)
        self.assertEqual(report['payment_amount_total'], 50.0)
        self.assertEqual(report['unpaid_amount_total'], 150.0)
        logs = repo.list_audit_logs(tenant['id'], project['id'])
        self.assertEqual(logs[0]['action'], 'payment.record')
        self.assertEqual(logs[0]['detail']['amount_paid'], 50)
        repo.close()

        reopened = create_saas_repository(f"sqlite:///{Path(self.tmp.name) / 'saas.sqlite3'}")
        self.assertEqual(reopened.report_summary(tenant['id'], project['id'], '2026-06')['unpaid_amount_total'], 150.0)
        self.assertEqual(len(reopened.list_audit_logs(tenant['id'], project['id'])), 1)
        reopened.close()

    def test_repository_isolates_tenant_business_rows(self):
        repo = self._repo()
        tenant_a = repo.create_tenant('A物业')
        tenant_b = repo.create_tenant('B物业')
        project_a = repo.create_project(tenant_a['id'], 'A项目')
        project_b = repo.create_project(tenant_b['id'], 'B项目')
        a_target = repo.create_charge_target(tenant_a['id'], project_a['id'], '住宅楼', '1单元', '101', '居民', 80)
        b_target = repo.create_charge_target(tenant_b['id'], project_b['id'], '住宅楼', '1单元', '201', '居民', 90)
        self.assertEqual([x['id'] for x in repo.list_charge_targets(tenant_a['id'], project_a['id'])], [a_target['id']])
        self.assertEqual([x['id'] for x in repo.list_charge_targets(tenant_b['id'], project_b['id'])], [b_target['id']])
        self.assertEqual(repo.list_charge_targets(tenant_a['id'], project_b['id']), [])
        repo.close()


if __name__ == '__main__':
    unittest.main()
