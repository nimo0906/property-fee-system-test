#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 22."""

from tests.integration_base import *


class TestIntegration22(IntegrationTestBase):
    def test_bill_generate_preview_does_not_write_until_confirmed(self):
        http_post('/rooms/create', {
            'building': 'PREVIEW', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period': '2026-10',
            'fee_type_ids': '1',
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('生成账单预览', html)
        self.assertIn('将生成账单', html)
        self.assertIn('跳过重复', html)
        self.assertIn('PREVIEW', html)
        self.assertIn('确认生成账单', html)

        import server.db as db_module
        db = db_module.get_db()
        before = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2026-10'").fetchone()[0]
        db.close()
        self.assertEqual(before, 0)

        status, body, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2026-10',
            'fee_type_ids': '1',
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)
        db = db_module.get_db()
        after = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2026-10'").fetchone()[0]
        db.close()
        self.assertGreater(after, 0)


    def test_bill_generate_filters_by_building_before_confirm(self):
        http_post('/rooms/create', {
            'building': 'FILTER-A', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/rooms/create', {
            'building': 'FILTER-B', 'unit': 'A座', 'room_number': '802',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period': '2026-11',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'FILTER-A',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('FILTER-A', html)
        self.assertNotIn('FILTER-B', html)

        status, body, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2026-11',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'FILTER-A',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)

        import server.db as db_module
        db = db_module.get_db()
        counts = dict(db.execute(
            "SELECT r.building, COUNT(*) FROM bills b JOIN rooms r ON b.room_id=r.id WHERE b.billing_period='2026-11' GROUP BY r.building"
        ).fetchall())
        db.close()
        self.assertEqual(counts.get('FILTER-A'), 1)
        self.assertIsNone(counts.get('FILTER-B'))


    def test_bills_review_workbench_lists_adjusted_bills_with_edit_links(self):
        http_post('/rooms/create', {
            'building': 'REVIEW', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-11',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'REVIEW',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2027-11' LIMIT 1").fetchone()['id'])
        db.close()

        http_post('/bills/batch_edit/apply', {
            'bill_ids': bid,
            'due_date': '2027-11-30',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '核对工作台测试',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills/review?period=2027-11&scope=adjusted', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单核对工作台', html)
        self.assertIn('人工修正', html)
        self.assertIn('REVIEW-A座-801', html)
        self.assertIn('19.00', html)
        self.assertIn('20.90', html)
        self.assertIn('2027-11-30', html)
        self.assertIn(f'href="/bills/{bid}/edit"', html)


    def test_bill_generation_result_links_to_review_workbench(self):
        http_post('/rooms/create', {
            'building': 'REVIEWLINK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-12',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'REVIEWLINK',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('去核对工作台', html)
        self.assertIn('/bills/review?period=2027-12', html)


    def test_bill_batch_edit_preview_shows_changes_without_updating(self):
        http_post('/rooms/create', {
            'building': 'BATCHPREVIEW', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-10',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHPREVIEW',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2027-10' LIMIT 1").fetchone()['id'])
        db.close()

        status, preview_html, loc = http_post('/bills/batch_edit/preview', {
            'bill_ids': bid,
            'due_date': '2027-10-31',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '预览确认测试',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正预览', preview_html)
        self.assertIn('原金额', preview_html)
        self.assertIn('新金额', preview_html)
        self.assertIn('19.00', preview_html)
        self.assertIn('20.90', preview_html)
        self.assertIn('2027-10-28', preview_html)
        self.assertIn('2027-10-31', preview_html)
        self.assertIn('action="/bills/batch_edit/apply"', preview_html)
        self.assertIn('确认执行批量修正', preview_html)

        db = db_module.get_db()
        bill = db.execute("SELECT amount,due_date,notes FROM bills WHERE id=?", (bid,)).fetchone()
        db.close()
        self.assertEqual(bill['amount'], 19)
        self.assertEqual(bill['due_date'], '2027-10-28')
        self.assertTrue(not bill['notes'])


    def test_bill_edit_creates_auto_backup_before_adjustment(self):
        http_post('/rooms/create', {
            'building': 'EDITBACKUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-08', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'EDITBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = db.execute("SELECT id FROM bills WHERE billing_period='2028-08' LIMIT 1").fetchone()['id']
        db.close()
        before = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_bill_adjustment_')] if os.path.exists(db_module.BACKUP_DIR) else []

        status, body, loc = http_post(f'/bills/{bid}/edit', {
            'new_amount': '18.00',
            'due_date': '2028-08-31',
            'notes': '单笔修正自动备份测试',
            'approved_by': '备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        after = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_bill_adjustment_')]
        self.assertGreater(len(after), len(before))


    def test_bill_batch_edit_result_shows_auto_backup_restore_link(self):
        http_post('/rooms/create', {
            'building': 'BATCHBACKUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-09', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BATCHBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-09' LIMIT 1").fetchone()['id'])
        db.close()

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': bid,
            'due_date': '2028-09-30',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '批量修正自动备份测试',
            'approved_by': '备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动备份', result_html)
        self.assertRegex(result_html, r'action="/backups/auto_before_batch_adjustment_[^"]+\.db/restore"')


