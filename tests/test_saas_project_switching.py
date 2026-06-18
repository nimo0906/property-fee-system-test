import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasProjectSwitching(unittest.TestCase):
    def _client(self, db_url, tenant='切换物业', project='一期', username='admin', role_code='system_admin'):
        client = TestClient(create_app(database_url=db_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant,
            'project_name': project,
            'username': username,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_switch_project_updates_session_and_business_scope(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url)
            created = client.post('/backoffice/tenant-projects/create', data={'name': '二期', 'code': 'P2'}, follow_redirects=False)
            self.assertEqual(created.status_code, 303)
            repo = create_saas_repository(db_url)
            projects = {row['name']: row for row in repo.list_projects()}
            repo.close()

            first = client.post('/api/charge-targets', json={
                'building': '一期楼栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80,
            })
            self.assertEqual(first.status_code, 200)
            switched = client.post('/api/auth/switch-project', json={'project_id': projects['二期']['id']})
            self.assertEqual(switched.status_code, 200)
            self.assertEqual(switched.json()['project_name'], '二期')
            me = client.get('/api/auth/me')
            self.assertEqual(me.json()['project_name'], '二期')
            self.assertEqual(me.json()['project_id'], projects['二期']['id'])
            second = client.post('/api/charge-targets', json={
                'building': '二期楼栋', 'unit': '2单元', 'room_number': '201', 'category': '居民', 'area': 90,
            })
            self.assertEqual(second.status_code, 200)
            list_second = client.get('/api/charge-targets')
            self.assertIn('二期楼栋', str(list_second.json()))
            self.assertNotIn('一期楼栋', str(list_second.json()))

            back = client.post('/api/auth/switch-project', json={'project_id': projects['一期']['id']})
            self.assertEqual(back.status_code, 200)
            list_first = client.get('/api/charge-targets')
            self.assertIn('一期楼栋', str(list_first.json()))
            self.assertNotIn('二期楼栋', str(list_first.json()))

    def test_cannot_switch_to_other_tenant_project(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant='A物业', project='A项目', username='admin_a')
            self._client(db_url, tenant='B物业', project='B项目', username='admin_b')
            repo = create_saas_repository(db_url)
            b_project = next(row for row in repo.list_projects() if row['name'] == 'B项目')
            repo.close()
            blocked = client_a.post('/api/auth/switch-project', json={'project_id': b_project['id']})
            self.assertEqual(blocked.status_code, 403)
            me = client_a.get('/api/auth/me')
            self.assertEqual(me.json()['project_name'], 'A项目')

    def test_tenant_project_page_exposes_switch_action_for_own_projects(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url)
            client.post('/backoffice/tenant-projects/create', data={'name': '二期', 'code': 'P2'}, follow_redirects=False)
            page = client.get('/backoffice/tenant-projects')
            self.assertEqual(page.status_code, 200)
            self.assertIn('切换项目', page.text)
            self.assertIn('/backoffice/tenant-projects/switch', page.text)
            repo = create_saas_repository(db_url)
            p2 = next(row for row in repo.list_projects() if row['name'] == '二期')
            repo.close()
            switched = client.post('/backoffice/tenant-projects/switch', data={'project_id': str(p2['id'])}, follow_redirects=False)
            self.assertEqual(switched.status_code, 303)
            self.assertEqual(client.get('/api/auth/me').json()['project_name'], '二期')


if __name__ == '__main__':
    unittest.main()
