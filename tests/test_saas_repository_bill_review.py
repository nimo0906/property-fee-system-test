import tempfile
import unittest
from pathlib import Path

from server.saas_repository import TenantScopeError, create_saas_repository


class TestSaasRepositoryBillReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = create_saas_repository(f"sqlite:///{Path(self.tmp.name) / 'saas.sqlite3'}")
        self.tenant = self.repo.create_tenant('账单持久物业')
        self.project = self.repo.create_project(self.tenant['id'], '账单持久项目')
        self.target = self.repo.create_charge_target(self.tenant['id'], self.project['id'], '1栋', '1单元', '101', '居民', 80)
        self.fee = self.repo.create_fee_type(self.tenant['id'], self.project['id'], '物业费', 2.5)

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_bill_starts_pending_review_and_can_be_approved_and_listed(self):
        bill = self.repo.create_bill(self.tenant['id'], self.project['id'], self.target['id'], self.fee['id'], '2026-06', '2026-06-01', '2026-06-30', 200)
        self.assertEqual(bill['status'], 'pending_review')
        pending = self.repo.list_bills(self.tenant['id'], self.project['id'], period='2026-06', status='pending_review')
        self.assertEqual([b['id'] for b in pending], [bill['id']])
        approved = self.repo.approve_bill(self.tenant['id'], self.project['id'], bill['id'])
        self.assertEqual(approved['status'], 'unpaid')
        self.assertEqual(self.repo.list_bills(self.tenant['id'], self.project['id'], status='pending_review'), [])

    def test_cannot_approve_other_tenant_bill(self):
        bill = self.repo.create_bill(self.tenant['id'], self.project['id'], self.target['id'], self.fee['id'], '2026-06', '2026-06-01', '2026-06-30', 200)
        other = self.repo.create_tenant('其他物业')
        other_project = self.repo.create_project(other['id'], '其他项目')
        with self.assertRaises(TenantScopeError):
            self.repo.approve_bill(other['id'], other_project['id'], bill['id'])


class TestSaasBillReviewSchema(unittest.TestCase):
    def test_schema_sets_bills_pending_review_by_default(self):
        from server.saas_schema import build_saas_postgres_schema

        schema = build_saas_postgres_schema()
        block = schema.split('CREATE TABLE IF NOT EXISTS bills', 1)[1].split(');', 1)[0]
        self.assertIn("status TEXT NOT NULL DEFAULT 'pending_review'", block)
