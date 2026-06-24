#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 23."""

from tests.integration_base import *


class TestIntegration23(IntegrationTestBase):
    def test_bill_batch_edit_result_shows_before_after_details(self):
        http_post('/rooms/create', {
            'building': 'BATCHDETAIL', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-09',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHDETAIL',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2027-09' LIMIT 1").fetchone()['id'])
        db.close()

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': bid,
            'due_date': '2027-09-30',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '结果详情测试',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正明细', result_html)
        self.assertIn('原金额', result_html)
        self.assertIn('新金额', result_html)
        self.assertIn('19.0', result_html)
        self.assertIn('20.9', result_html)
        self.assertIn('2027-09-28', result_html)
        self.assertIn('2027-09-30', result_html)
        self.assertIn('/bills/review?scope=adjusted', result_html)


    def test_bill_batch_edit_adjusts_amount_by_percent_and_records_adjustments(self):
        for room_no in ('803', '804'):
            http_post('/rooms/create', {
                'building': 'BATCHAMT', 'unit': 'A座', 'room_number': room_no,
                'floor': '8', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-08',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHAMT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2027-08' ORDER BY id").fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': ','.join(ids),
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '统一上调10%',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正结果', result_html)

        db = db_module.get_db()
        amounts = [r['amount'] for r in db.execute("SELECT amount FROM bills WHERE id IN (?, ?) ORDER BY id", ids).fetchall()]
        adj_count = db.execute("SELECT COUNT(*) FROM bill_adjustments WHERE bill_id IN (?, ?)", ids).fetchone()[0]
        db.close()
        self.assertEqual(amounts, [20.9, 20.9])
        self.assertEqual(adj_count, 2)


    def test_bill_batch_edit_updates_due_date_and_notes_for_selected_bills(self):
        for room_no in ('801', '802'):
            http_post('/rooms/create', {
                'building': 'BATCHEDIT', 'unit': 'A座', 'room_number': room_no,
                'floor': '8', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-07',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHEDIT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2027-07' ORDER BY id").fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        back_url = '/bills?period=2027-07&building=BATCHEDIT'
        status, form_html, loc = http_post('/bills/batch_edit', {
            'bill_ids': ','.join(ids),
            'back': back_url,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正账单', form_html)
        self.assertIn('name="due_date"', form_html)
        self.assertIn('name="notes"', form_html)
        self.assertIn(f'name="back" value="{back_url.replace("&", "&amp;")}"', form_html)
        self.assertIn(f'href="{back_url.replace("&", "&amp;")}"', form_html)

        status, preview_html, loc = http_post('/bills/batch_edit/preview', {
            'bill_ids': ','.join(ids),
            'due_date': '2027-07-31',
            'notes': '统一调整截止日',
            'back': back_url,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'name="back" value="{back_url.replace("&", "&amp;")}"', preview_html)
        self.assertIn(f'href="{back_url.replace("&", "&amp;")}"', preview_html)

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': ','.join(ids),
            'due_date': '2027-07-31',
            'notes': '统一调整截止日',
            'back': back_url,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正结果', result_html)
        self.assertIn('更新账单', result_html)
        self.assertIn(f'href="{back_url.replace("&", "&amp;")}"', result_html)

        db = db_module.get_db()
        rows = db.execute("SELECT due_date, notes FROM bills WHERE id IN (?, ?) ORDER BY id", ids).fetchall()
        db.close()
        self.assertEqual([r['due_date'] for r in rows], ['2027-07-31', '2027-07-31'])
        self.assertEqual([r['notes'] for r in rows], ['统一调整截止日', '统一调整截止日'])


    def test_bill_edit_updates_amount_due_date_and_notes(self):
        http_post('/rooms/create', {
            'building': 'EDITBILL', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-06',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'EDITBILL',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = db.execute("SELECT id FROM bills WHERE billing_period='2027-06' ORDER BY id DESC LIMIT 1").fetchone()['id']
        db.close()

        status, form = http_get(f'/bills/{bid}/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="due_date"', form)
        self.assertIn('name="notes"', form)
        self.assertIn('href="/bills"', form)
        self.assertIn('返回账单管理', form)
        self.assertNotIn(f'href="/bills/{bid}" class="btn btn-outline-secondary">取消</a>', form)

        status, body, loc = http_post(f'/bills/{bid}/edit', {
            'new_amount': '88.9',
            'due_date': '2027-06-30',
            'notes': '人工核对修正',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = db_module.get_db()
        bill = db.execute("SELECT amount,due_date,notes FROM bills WHERE id=?", (bid,)).fetchone()
        db.close()
        self.assertEqual(bill['amount'], 88.9)
        self.assertEqual(bill['due_date'], '2027-06-30')
        self.assertEqual(bill['notes'], '人工核对修正')


    def test_bill_generate_result_has_direct_edit_links(self):
        http_post('/rooms/create', {
            'building': 'EDITLINK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-05',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'EDITLINK',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('直接修正', html)
        self.assertRegex(html, r'href="/bills/\d+/edit"')


    def test_bill_generate_result_can_undo_created_unpaid_bills(self):
        http_post('/rooms/create', {
            'building': 'UNDO', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-03',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'UNDO',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('撤销本次生成', html)

        import re
        action = re.search(r'action="(/bills/undo_generated)"', html).group(1)
        ids = re.search(r'name="bill_ids" value="([^"]+)"', html).group(1)
        status, result_html, loc = http_post(action, {
            'period': '2027-03',
            'bill_ids': ids,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('撤销生成结果', result_html)
        self.assertIn('删除账单', result_html)
        self.assertIn('跳过账单', result_html)

        import server.db as db_module
        db = db_module.get_db()
        count = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2027-03'").fetchone()[0]
        db.close()
        self.assertEqual(count, 0)

