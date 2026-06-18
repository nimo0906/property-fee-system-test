import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasFastApiUploadIsolation(unittest.TestCase):
    def test_register_import_file_generates_tenant_scoped_key(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': 'A物业', 'project_name': 'A项目', 'username': 'finance', 'role_code': 'finance'
        })
        response = client.post('/api/imports/files/register', json={
            'import_type': 'charge_targets',
            'original_name': '../房间表.xlsx',
            'file_size': 2048,
            'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        self.assertEqual(response.status_code, 200)
        item = response.json()['item']
        self.assertEqual(item['tenant_id'], 1)
        self.assertEqual(item['project_id'], 2)
        self.assertTrue(item['storage_key'].startswith('tenants/1/projects/2/imports/'))
        self.assertNotIn('..', item['storage_key'])
        self.assertFalse(item['storage_key'].startswith('system/'))

    def test_register_import_file_requires_login(self):
        client = TestClient(create_app())
        response = client.post('/api/imports/files/register', json={
            'import_type': 'charge_targets', 'original_name': 'x.xlsx', 'file_size': 1, 'content_type': 'x'
        })
        self.assertEqual(response.status_code, 401)

    def test_register_import_file_rejects_invalid_category_attempt(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': 'B物业', 'project_name': 'B项目', 'username': 'finance', 'role_code': 'finance'
        })
        response = client.post('/api/imports/files/register', json={
            'import_type': 'system/templates',
            'original_name': 'roles.json',
            'file_size': 1,
            'content_type': 'application/json',
        })
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
