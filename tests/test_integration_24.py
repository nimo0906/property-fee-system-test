#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 24."""

from tests.integration_base import *


class TestIntegration24(IntegrationTestBase):
    def test_bill_generate_undo_skips_paid_bills(self):
        http_post('/rooms/create', {
            'building': 'UNDOPAID', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-04',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'UNDOPAID',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bill = db.execute("SELECT id, amount FROM bills WHERE billing_period='2027-04' LIMIT 1").fetchone()
        db.close()
        self.assertIsNotNone(bill)

        http_post(f'/bills/{bill["id"]}/pay', {
            'amount_paid': str(bill['amount']),
            'payment_method': 'cash',
            'operator': '测试',
        }, self.cookie, TEST_PORT)

        status, result_html, loc = http_post('/bills/undo_generated', {
            'period': '2027-04',
            'bill_ids': str(bill['id']),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('撤销生成结果', result_html)
        self.assertIn('跳过账单', result_html)
        self.assertIn('已有缴费记录', result_html)

        db = db_module.get_db()
        count = db.execute("SELECT COUNT(*) FROM bills WHERE id=?", (bill['id'],)).fetchone()[0]
        db.close()
        self.assertEqual(count, 1)


    def test_bill_generate_result_can_export_created_bills_csv(self):
        http_post('/rooms/create', {
            'building': 'EXPORTGEN', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-02',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'EXPORTGEN',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('/bills/export_generated?', html)

        import re
        path = re.search(r'href="(/bills/export_generated\?ids=[^"]+)"', html).group(1).replace('&amp;', '&')
        status, csv_body = http_get(path, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('票据编号,楼栋,房号', csv_body)
        self.assertIn('EXPORTGEN', csv_body)
        self.assertIn('物业费(居民)', csv_body)

    def test_bill_generate_page_confirm_button_goes_to_precheck_before_writing(self):
        status, page = http_get('/bills/generate', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="mode" value="preview"', page)
        self.assertIn('name="mode" value="confirm_review"', page)
        self.assertIn('生成前核对', page)

    def test_bill_generate_confirm_review_shows_summary_warnings_and_does_not_write(self):
        http_post('/rooms/create', {
            'building': 'PRECHECK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '0',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        before = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2032-01'").fetchone()[0]
        db.close()

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm_review',
            'period': '2032-01',
            'fee_type_ids': '7',
            'due_day': '28',
            'building': 'PRECHECK',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('出账前核对', html)
        self.assertIn('涉及房间', html)
        self.assertIn('收费项目', html)
        self.assertIn('金额合计', html)
        self.assertIn('异常核对清单', html)
        self.assertIn('面积为0', html)
        self.assertIn('PRECHECK-801', html)
        self.assertIn('name="reviewed" value="1"', html)
        self.assertIn('确认生成账单', html)

        db = db_module.get_db()
        after = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2032-01'").fetchone()[0]
        db.close()
        self.assertEqual(after, before)


    def test_bill_generate_result_shows_review_warnings(self):
        http_post('/rooms/create', {
            'building': 'WARN', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '0',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-01',
            'fee_type_ids': '7',
            'due_day': '28',
            'building': 'WARN',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('异常核对清单', html)
        self.assertIn('无业主', html)
        self.assertIn('面积为0', html)
        self.assertIn('WARN-801', html)


    def test_bill_generate_confirm_creates_auto_backup_restore_link(self):
        http_post('/rooms/create', {
            'building': 'GENBACKUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-10', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'GENBACKUP',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动备份', html)
        self.assertRegex(html, r'action="/backups/auto_before_bill_generation_[^"]+\.db/restore"')


    def test_bill_generate_confirm_shows_result_details(self):
        http_post('/rooms/create', {
            'building': 'RESULT', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2026-12',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'RESULT',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', html)
        self.assertIn('本次生成账单', html)
        self.assertIn('金额合计', html)
        self.assertIn('RESULT-801', html)
        self.assertIn('物业费(居民)', html)
        self.assertIn('查看账单列表', html)


    def test_bill_generate(self):
        self._ensure_room_for_billing()
        status, body, loc = http_post('/bills/generate', {
            'period': '2026-06',
            'fee_type_ids': '1,3,4,7,8',
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)
        self.assertIn('本次生成账单', body)


    def test_bills_list_shows_generated(self):
        self._ensure_room_for_billing()
        http_post('/bills/generate', {
            'period': '2026-06', 'fee_type_ids': '1,3', 'due_day': '28',
        }, self.cookie, TEST_PORT)
        _, body = http_get('/bills?period=2026-06', self.cookie, TEST_PORT)
        self.assertIn('2026-06', body)


    def test_bills_summary_counts_all_filtered_rows_not_current_page(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '账单统计业主', '13900007777')
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()[0]
        for i in range(60):
            room_id = create_room(
                db, building='SUMMARYALL', unit='A座', room_number=f'{1000+i}',
                category='居民', area=10, owner_id=owner_id,
            )
            create_bill(
                db, room_id=room_id, owner_id=owner_id, fee_type_id=fee_id,
                period='2036-06', amount=10, status='unpaid',
            )
        db.close()

        status, body = http_get('/bills?period=2036-06&building=SUMMARYALL', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('60户 / 60笔', body)
        self.assertIn('共 60 条，第 1 / 2 页', body)


    def test_bills_default_page_shows_all_periods_until_user_filters_period(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '默认全部账单业主', '13900008888')
        room_id = create_room(db, building='BILLALL', unit='A座', room_number='8801', category='居民', area=10, owner_id=owner_id)
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()[0]
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=fee_id, period='2037-06', amount=10, status='unpaid')
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=fee_id, period='2037-07', amount=20, status='unpaid')
        db.close()

        status, body = http_get('/bills?building=BILLALL', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('共 2 条', body)
        self.assertIn('2037-06', body)
        self.assertIn('2037-07', body)

        status, filtered = http_get('/bills?period=2037-06&building=BILLALL', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('共 1 条', filtered)
        self.assertIn('2037-06', filtered)
        self.assertNotIn('2037-07', filtered)


    def test_bills_default_list_shows_paid_bills_after_returning_from_print(self):
        http_post('/rooms/create', {
            'building': 'BILLDEFAULT', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2026-05', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BILLDEFAULT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bill = db.execute(
            "SELECT id,bill_number FROM bills WHERE billing_period='2026-05' AND room_id=(SELECT id FROM rooms WHERE building='BILLDEFAULT' LIMIT 1)"
        ).fetchone()
        bid = str(bill['id'])
        bill_number = bill['bill_number']
        db.close()

        http_post(f'/bills/{bid}/pay', {
            'amount_paid': '19',
            'payment_method': 'cash',
            'operator': '默认列表测试员',
        }, self.cookie, TEST_PORT)

        status, body = http_get('/bills?period=2026-05', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(bill_number, body)
        self.assertIn('已缴', body)


    def test_bill_detail_return_preserves_list_filters(self):
        http_post('/rooms/create', {
            'building': 'BACKFILTER', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-09', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BACKFILTER',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2029-09' LIMIT 1").fetchone()['id'])
        db.close()

        status, html = http_get('/bills?period=2029-09&building=BACKFILTER&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'/bills/{bid}?back=', html)
        self.assertIn('period%3D2029-09', html)
        self.assertIn('building%3DBACKFILTER', html)

        status, detail = http_get(f'/bills/{bid}?back=/bills%3Fperiod%3D2029-09%26building%3DBACKFILTER%26status%3Dunpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('data-back-url="/bills?period=2029-09&amp;building=BACKFILTER&amp;status=unpaid"', detail)
        self.assertNotIn('history.back()', detail)
        self.assertIn('返回账单管理', detail)
        self.assertIn('class="btn btn-outline-secondary mt-3 bill-detail-back"', detail)
