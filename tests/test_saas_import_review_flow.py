import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_service import PermissionDenied, SaasBackofficeService


class TestSaasImportReviewFlow(unittest.TestCase):
    def setUp(self):
        self.service = SaasBackofficeService.in_memory()
        self.tenant_a = self.service.create_tenant('A物业')
        self.project_a = self.service.create_project(self.tenant_a, 'A项目')
        self.user_a = self.service.create_user(self.tenant_a, 'finance_a', 'finance')
        self.tenant_b = self.service.create_tenant('B物业')
        self.project_b = self.service.create_project(self.tenant_b, 'B项目')
        self.user_b = self.service.create_user(self.tenant_b, 'finance_b', 'finance')

    def test_preview_keeps_review_rows_without_writing_charge_targets(self):
        preview = self.service.preview_charge_target_import(self.user_a, self.project_a, [
            {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
            {'building': '1栋', 'unit': '1单元', 'room_number': '', 'category': '居民', 'area': '60'},
            {'building': '1栋', 'unit': '1单元', 'room_number': '103', 'category': '居民', 'area': 'bad'},
        ])
        self.assertEqual(preview['valid_count'], 1)
        self.assertEqual(preview['error_count'], 2)
        self.assertEqual(self.service.list_charge_targets(self.user_a, self.project_a), [])
        review = self.service.get_import_review(self.user_a, self.project_a, preview['import_id'])
        self.assertEqual(len(review['valid_rows']), 1)
        self.assertEqual(len(review['errors']), 2)
        self.assertEqual(review['errors'][0]['row'], 2)
        self.assertIn('房号', review['errors'][0]['error'])

    def test_confirm_writes_only_valid_rows_and_is_idempotent(self):
        preview = self.service.preview_charge_target_import(self.user_a, self.project_a, [
            {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
            {'building': '1栋', 'unit': '1单元', 'room_number': 'bad', 'category': '居民', 'area': '-1'},
        ])
        first = self.service.confirm_charge_target_import(self.user_a, self.project_a, preview['import_id'])
        second = self.service.confirm_charge_target_import(self.user_a, self.project_a, preview['import_id'])
        targets = self.service.list_charge_targets(self.user_a, self.project_a)
        self.assertEqual(first, {'created_count': 1, 'skipped_count': 1})
        self.assertEqual(second, {'created_count': 0, 'skipped_count': 1})
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['room_number'], '101')

    def test_other_tenant_cannot_read_or_confirm_import_review(self):
        preview = self.service.preview_charge_target_import(self.user_a, self.project_a, [
            {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
        ])
        with self.assertRaises(PermissionDenied):
            self.service.get_import_review(self.user_b, self.project_b, preview['import_id'])
        with self.assertRaises(PermissionDenied):
            self.service.confirm_charge_target_import(self.user_b, self.project_b, preview['import_id'])
        self.assertEqual(self.service.list_charge_targets(self.user_a, self.project_a), [])


class TestSaasFastApiImportReviewFlow(unittest.TestCase):
    def test_api_preview_review_confirm_flow(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': '导入物业', 'project_name': '导入项目', 'username': 'finance', 'role_code': 'finance'
        })
        preview = client.post('/api/imports/charge-targets/preview', json={'rows': [
            {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
            {'building': '1栋', 'unit': '1单元', 'room_number': '', 'category': '居民', 'area': '60'},
        ]})
        self.assertEqual(preview.status_code, 200)
        import_id = preview.json()['import_id']
        self.assertEqual(client.get('/api/charge-targets').json()['items'], [])
        review = client.get(f'/api/imports/{import_id}/review')
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.json()['valid_count'], 1)
        self.assertEqual(review.json()['error_count'], 1)
        confirmed = client.post('/api/imports/charge-targets/confirm', json={'import_id': import_id})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()['created_count'], 1)
        self.assertEqual(len(client.get('/api/charge-targets').json()['items']), 1)

    def test_api_other_tenant_cannot_confirm_import_id(self):
        app = create_app()
        client_a = TestClient(app)
        client_b = TestClient(app)
        client_a.post('/api/auth/login', json={
            'tenant_name': 'A物业', 'project_name': 'A项目', 'username': 'finance_a', 'role_code': 'finance'
        })
        preview = client_a.post('/api/imports/charge-targets/preview', json={'rows': [
            {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
        ]})
        client_b.post('/api/auth/login', json={
            'tenant_name': 'B物业', 'project_name': 'B项目', 'username': 'finance_b', 'role_code': 'finance'
        })
        self.assertEqual(client_b.get(f"/api/imports/{preview.json()['import_id']}/review").status_code, 403)
        self.assertEqual(client_b.post('/api/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']}).status_code, 403)
