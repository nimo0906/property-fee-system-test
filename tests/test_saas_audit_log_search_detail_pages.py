import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasAuditLogSearchDetailPages(unittest.TestCase):
    def _client(self, database_url, tenant_name='审计增强物业', project_name='审计增强项目', role_code='system_admin'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_logs(self, db_url, client):
        created = client.post('/api/users', json={'username': 'audit_cashier', 'role_code': 'cashier'}).json()['item']
        client.post(f"/api/users/{created['id']}/reset-password", json={'new_password': 'SensitivePass-2026'})
        target = client.post('/api/charge-targets', json={
            'building': '7栋', 'unit': '1单元', 'room_number': '701', 'category': '居民', 'area': 100,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-12',
            'service_start': '2026-12-01', 'service_end': '2026-12-31',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve", json={})
        client.post('/api/payments', json={'bill_id': bill['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'AUDIT-DETAIL-PAY'})
        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        logs = repo.list_audit_logs(tenant['id'], project['id'])
        repo.close()
        return logs

    def test_audit_page_filters_high_risk_action_entity_keyword_and_paginates(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url)
            self._seed_logs(db_url, client)

            page = client.get('/backoffice/audit-logs?action=payment.record&entity_type=payment&keyword=AUDIT-DETAIL-PAY&risk=high&page=1&page_size=1')

            self.assertEqual(page.status_code, 200)
            for text in ['高级筛选', '高风险', '上一页', '下一页', '查看详情']:
                self.assertIn(text, page.text)
            for field in ['action', 'entity_type', 'keyword', 'risk', 'page_size']:
                self.assertIn(f'name="{field}"', page.text)
            self.assertIn('payment.record', page.text)
            self.assertIn('AUDIT-DETAIL-PAY', page.text)
            self.assertNotIn('bill.generate</td>', page.text)
            self.assertNotIn('SensitivePass-2026', page.text)

    def test_audit_detail_page_is_tenant_scoped_and_masks_internal_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A审计增强物业', project_name='A审计增强项目')
            logs = self._seed_logs(db_url, client_a)
            payment_log = next(row for row in logs if row['action'] == 'payment.record')

            detail = client_a.get(f"/backoffice/audit-logs/{payment_log['id']}")
            self.assertEqual(detail.status_code, 200)
            for text in ['审计详情', 'payment.record', 'payment', 'AUDIT-DETAIL-PAY', 'A审计增强物业', 'A审计增强项目']:
                self.assertIn(text, detail.text)
            for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'SensitivePass-2026', 'password_hash']:
                self.assertNotIn(hidden, detail.text)

            client_b = self._client(db_url, tenant_name='B审计增强物业', project_name='B审计增强项目')
            blocked = client_b.get(f"/backoffice/audit-logs/{payment_log['id']}")
            self.assertEqual(blocked.status_code, 404)


if __name__ == '__main__':
    unittest.main()
