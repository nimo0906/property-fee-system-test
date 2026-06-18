import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasFastApiPersistentMode(unittest.TestCase):
    def test_fastapi_uses_configured_repository_for_tenant_project_user_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            health = client.get('/health')
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()['storage'], 'persistent')
            login = client.post('/api/auth/login', json={
                'tenant_name': '持久化物业',
                'project_name': '持久化项目',
                'username': 'admin',
                'role_code': 'system_admin',
            })
            self.assertEqual(login.status_code, 200)
            me = client.get('/api/auth/me')
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()['tenant_name'], '持久化物业')

            second = TestClient(create_app(database_url=db_url))
            lookup = second.get('/api/admin/bootstrap-state')
            self.assertEqual(lookup.status_code, 200)
            self.assertEqual(lookup.json()['tenants'][0]['name'], '持久化物业')
            self.assertEqual(lookup.json()['projects'][0]['name'], '持久化项目')
            self.assertEqual(lookup.json()['users'][0]['username'], 'admin')

    def test_fastapi_default_mode_remains_in_memory(self):
        client = TestClient(create_app())
        health = client.get('/health')
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()['storage'], 'memory')


if __name__ == '__main__':
    unittest.main()
