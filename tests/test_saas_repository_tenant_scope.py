import tempfile
import unittest
from pathlib import Path

from server.saas_repository import TenantScopeError, create_saas_repository


class TestSaasRepositoryTenantScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = create_saas_repository(f"sqlite:///{Path(self.tmp.name) / 'saas.sqlite3'}")
        self.tenant_a = self.repo.create_tenant('A物业')
        self.project_a = self.repo.create_project(self.tenant_a['id'], 'A项目')
        self.tenant_b = self.repo.create_tenant('B物业')
        self.project_b = self.repo.create_project(self.tenant_b['id'], 'B项目')

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_rejects_charge_target_when_project_does_not_belong_to_tenant(self):
        with self.assertRaises(TenantScopeError):
            self.repo.create_charge_target(self.tenant_a['id'], self.project_b['id'], '1栋', '1单元', '101', '居民', 80)

    def test_rejects_fee_type_when_project_does_not_belong_to_tenant(self):
        with self.assertRaises(TenantScopeError):
            self.repo.create_fee_type(self.tenant_a['id'], self.project_b['id'], '物业费', 2.5)

    def test_rejects_import_file_when_project_does_not_belong_to_tenant(self):
        with self.assertRaises(TenantScopeError):
            self.repo.create_import_file(
                self.tenant_a['id'], self.project_b['id'], 'charge_targets', 'x.xlsx',
                'tenants/1/projects/2/imports/3/original/x.xlsx', 1, 'x'
            )

    def test_allows_business_data_when_project_belongs_to_tenant(self):
        target = self.repo.create_charge_target(self.tenant_a['id'], self.project_a['id'], '1栋', '1单元', '101', '居民', 80)
        fee = self.repo.create_fee_type(self.tenant_a['id'], self.project_a['id'], '物业费', 2.5)
        row = self.repo.create_import_file(
            self.tenant_a['id'], self.project_a['id'], 'charge_targets', 'x.xlsx',
            'tenants/1/projects/1/imports/3/original/x.xlsx', 1, 'x'
        )
        self.assertEqual(target['project_id'], self.project_a['id'])
        self.assertEqual(fee['project_id'], self.project_a['id'])
        self.assertEqual(row['project_id'], self.project_a['id'])


if __name__ == '__main__':
    unittest.main()

class TestSaasSchemaTenantScope(unittest.TestCase):
    def test_schema_has_composite_project_scope_constraints_for_business_tables(self):
        from server.saas_schema import build_saas_postgres_schema

        schema = build_saas_postgres_schema()
        self.assertIn('UNIQUE(id, tenant_id)', schema)
        for table in ['owners', 'charge_targets', 'fee_types', 'bills', 'payments', 'imports', 'audit_logs']:
            section = schema[schema.index(f'CREATE TABLE IF NOT EXISTS {table}') :]
            section = section[:section.index(');')]
            self.assertIn('FOREIGN KEY(project_id, tenant_id) REFERENCES projects(id, tenant_id)', section, table)
