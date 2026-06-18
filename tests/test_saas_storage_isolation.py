import unittest

from server.saas_storage import SaasStorage


class TestSaasStorageIsolation(unittest.TestCase):
    def setUp(self):
        self.storage = SaasStorage(root_dir='/tmp/saas-storage-test')

    def test_system_asset_path_is_under_system_prefix(self):
        path = self.storage.system_asset_path('templates', 'bill.xlsx')
        self.assertTrue(path.startswith('system/templates/'))
        self.assertIn('bill.xlsx', path)

    def test_tenant_upload_path_includes_tenant_and_project(self):
        path = self.storage.upload_path(
            tenant_id=12,
            project_id=34,
            upload_id=56,
            category='imports',
            filename='owners.xlsx',
        )
        self.assertEqual(path, 'tenants/12/projects/34/imports/56/original/owners.xlsx')

    def test_tenant_upload_path_sanitizes_traversal(self):
        path = self.storage.upload_path(
            tenant_id=1,
            project_id=2,
            upload_id=3,
            category='imports',
            filename='../../secret.xlsx',
        )
        self.assertTrue(path.startswith('tenants/1/projects/2/imports/3/original/'))
        self.assertNotIn('..', path)
        self.assertNotIn('/secret.xlsx', path)

    def test_system_and_tenant_prefixes_are_never_the_same(self):
        system_path = self.storage.system_asset_path('defaults', 'roles.json')
        tenant_path = self.storage.upload_path(1, 2, 3, 'imports', 'roles.json')
        self.assertNotEqual(system_path.split('/')[0], tenant_path.split('/')[0])
        self.assertTrue(system_path.startswith('system/'))
        self.assertTrue(tenant_path.startswith('tenants/'))

    def test_same_filename_different_tenants_get_different_paths(self):
        a = self.storage.upload_path(1, 2, 3, 'attachments', 'contract.pdf')
        b = self.storage.upload_path(9, 8, 7, 'attachments', 'contract.pdf')
        self.assertNotEqual(a, b)

    def test_upload_path_requires_tenant_and_project(self):
        with self.assertRaises(ValueError):
            self.storage.upload_path(None, 2, 3, 'imports', 'x.xlsx')
        with self.assertRaises(ValueError):
            self.storage.upload_path(1, None, 3, 'imports', 'x.xlsx')


if __name__ == '__main__':
    unittest.main()

class TestSaasImportStorageMetadata(unittest.TestCase):
    def test_schema_imports_store_customer_upload_metadata_under_tenant_scope(self):
        from server.saas_schema import build_saas_postgres_schema

        schema = build_saas_postgres_schema()
        self.assertIn('tenant_id BIGINT NOT NULL REFERENCES tenants(id)', schema)
        self.assertIn('project_id BIGINT NOT NULL REFERENCES projects(id)', schema)
        self.assertIn('original_name TEXT', schema)
        self.assertIn('storage_key TEXT', schema)
        self.assertIn('file_size BIGINT', schema)
        self.assertIn('content_type TEXT', schema)

    def test_repository_records_import_file_metadata_with_tenant_project_scope(self):
        import tempfile
        from pathlib import Path

        from server.saas_repository import create_saas_repository

        with tempfile.TemporaryDirectory() as td:
            repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            tenant = repo.create_tenant('A物业')
            project = repo.create_project(tenant['id'], 'A项目')
            row = repo.create_import_file(
                tenant_id=tenant['id'],
                project_id=project['id'],
                import_type='charge_targets',
                original_name='房间.xlsx',
                storage_key='tenants/1/projects/2/imports/3/original/房间.xlsx',
                file_size=1024,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            self.assertEqual(row['tenant_id'], tenant['id'])
            self.assertEqual(row['project_id'], project['id'])
            self.assertEqual(row['storage_key'], 'tenants/1/projects/2/imports/3/original/房间.xlsx')
            self.assertEqual(row['original_name'], '房间.xlsx')
            imports = repo.list_import_files(tenant['id'], project['id'])
            self.assertEqual([item['id'] for item in imports], [row['id']])
            self.assertEqual(repo.list_import_files(999, project['id']), [])
            repo.close()
