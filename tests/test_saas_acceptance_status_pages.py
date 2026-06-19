import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasAcceptanceStatusPages(unittest.TestCase):
    def _client(self, database_url, tenant_name='闭环验收物业', project_name='闭环验收项目', role_code='system_admin'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_full_closure(self, client):
        target = client.post('/api/charge-targets', json={
            'building': '8栋', 'unit': '1单元', 'room_number': '801', 'category': '居民', 'area': 100,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-12',
            'service_start': '2026-12-01', 'service_end': '2026-12-31',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve", json={})
        client.post('/api/payments', json={'bill_id': bill['id'], 'amount': 80, 'method': 'cash', 'idempotency_key': 'ACCEPTANCE-PAY-1'})
        preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': 'building,unit,room_number,category,area\n9栋,1单元,901,居民,90'})
        import_id = preview.text.split('name="import_id" value="')[1].split('"')[0]
        client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})
        client.post('/backoffice/backups/create', follow_redirects=False)
        backups = client.get('/backoffice/backups').text
        backup_id = backups.split('/backoffice/backups/')[1].split('"')[0]
        client.post('/backoffice/backups/restore-drills', data={'backup_id': backup_id, 'scope': 'database'}, follow_redirects=False)

    def test_acceptance_page_shows_current_business_closure_status_and_next_actions(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            self._seed_full_closure(client)

            page = client.get('/backoffice/acceptance?period=2026-12')

            self.assertEqual(page.status_code, 200)
            for text in [
                '闭环状态总览', '当前账期', '收费对象', '收费项目', '账单', '已审核账单', '收款记录',
                '导入批次', '审计日志', '备份记录', '恢复演练', '对账摘要', '下一步建议', '全部核心步骤已有数据',
            ]:
                self.assertIn(text, page.text)
            for number in ['2026-12', '2', '1', '80.0', '120.0']:
                self.assertIn(number, page.text)
            for href in [
                '/backoffice/charge-targets', '/backoffice/fee-types', '/backoffice/bills', '/backoffice/payments',
                '/backoffice/reports?period=2026-12', '/backoffice/imports', '/backoffice/audit-logs', '/backoffice/backups',
            ]:
                self.assertIn(href, page.text)
            for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/var/lib/property-saas']:
                self.assertNotIn(hidden, page.text)

    def test_acceptance_page_is_tenant_scoped_and_shows_missing_first_step(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A闭环物业', project_name='A闭环项目')
            self._seed_full_closure(client_a)

            client_b = self._client(db_url, tenant_name='B闭环物业', project_name='B闭环项目')
            page_b = client_b.get('/backoffice/acceptance?period=2026-12')

            self.assertEqual(page_b.status_code, 200)
            self.assertIn('闭环状态总览', page_b.text)
            self.assertIn('下一步建议：先录入或导入收费对象', page_b.text)
            self.assertNotIn('A闭环物业', page_b.text)
            self.assertNotIn('ACCEPTANCE-PAY-1', page_b.text)


if __name__ == '__main__':
    unittest.main()
