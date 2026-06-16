#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 29."""

from tests.integration_base import *


class TestIntegration29(IntegrationTestBase):
    def test_fee_type_delete_hides_referenced_item_and_returns_group(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '删除收费项业主', '13900009991')
        room_id = create_room(db, building='FEEDEL', unit='A座', room_number='101', owner_id=owner_id)
        fee_id = db.execute("""
            INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active)
            VALUES('删除引用测试费','fixed',88,'元','monthly',29,1)
        """).lastrowid
        bill_id = create_bill(db, room_id=room_id, fee_type_id=fee_id, period='2036-06', amount=88, status='unpaid', owner_id=owner_id)
        db.commit(); db.close()

        status, page = http_get('/fee_types?group=property', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('删除引用测试费', page)
        self.assertIn(f'name="return_group" value="property"', page)

        status, body, loc = http_post(f'/fee_types/{fee_id}/delete', {'return_group': 'property'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/fee_types?group=property', loc)

        status, page = http_get('/fee_types?group=property', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('删除引用测试费', page)
        db = db_module.get_db()
        fee = db.execute('SELECT is_active FROM fee_types WHERE id=?', (fee_id,)).fetchone()
        bill = db.execute('SELECT fee_type_id FROM bills WHERE id=?', (bill_id,)).fetchone()
        db.close()
        self.assertEqual(fee['is_active'], 0)
        self.assertEqual(bill['fee_type_id'], fee_id)


    def test_fee_type_edit_allows_blank_optional_numbers(self):
        status, _, loc = http_post('/fee_types/13/edit', {
            'name': '泄水费',
            'calc_method': 'area',
            'unit_price': '1.5',
            'unit': '元/m²·月',
            'billing_cycle': 'monthly',
            'sort_order': '',
            'is_active': 'on',
            'notes': '排水设施维护费',
            'reminder_advance_days': '',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/fee_types/13/edit?flash=', loc)


    def test_fee_type_edit_stays_on_edit_page_after_save(self):
        status, _, loc = http_post('/fee_types/10/edit', {
            'name': '垃圾清运费',
            'calc_method': 'household',
            'unit_price': '30',
            'unit': '元/户',
            'billing_cycle': 'monthly',
            'sort_order': '32',
            'is_active': 'on',
            'notes': '商业垃圾清运服务费',
            'reminder_advance_days': '30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/fee_types/10/edit?flash=', loc)


    def test_fee_type_create_saves_new_tiers_and_generates_with_tier_rate(self):
        status, body, loc = http_post('/fee_types/create', {
            'name': '自定义分档面积费',
            'calc_method': 'area',
            'unit_price': '9',
            'unit': '元/m²·月',
            'billing_cycle': 'monthly',
            'sort_order': '96',
            'is_active': 'on',
            'notes': '测试分档',
            'reminder_advance_days': '30',
            'new_tier_cat': '商户',
            'new_tier_rate': '7',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        import server.db as db_module
        db = db_module.get_db()
        ft = db.execute("SELECT id FROM fee_types WHERE name='自定义分档面积费'").fetchone()
        self.assertIsNotNone(ft)
        tier = db.execute("SELECT rate FROM fee_type_tiers WHERE fee_type_id=? AND category='商户'", (ft['id'],)).fetchone()
        db.close()
        self.assertIsNotNone(tier)
        self.assertEqual(tier['rate'], 7)

        http_post('/rooms/create', {
            'building': 'TIER', 'unit': 'A座', 'room_number': '701',
            'floor': '7', 'category': '商户', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, body, loc = http_post('/bills/generate', {
            'period': '2026-09',
            'fee_type_ids': str(ft['id']),
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)

        db = db_module.get_db()
        bill = db.execute("""
            SELECT b.amount FROM bills b
            JOIN rooms r ON b.room_id=r.id
            WHERE b.billing_period='2026-09' AND b.fee_type_id=?
              AND r.building='TIER' AND r.room_number='701'
        """, (ft['id'],)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['amount'], 70)



    def test_finance_user_can_create_fee_type_without_dashboard_redirect(self):
        finance_cookie = self._create_user_and_login(
            'finance_fee_create', 'finance123', 'finance', '收费项目财务'
        )

        status, form = http_get('/fee_types/create?group=property', finance_cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('添加物业公司收费项目', form)

        status, body, loc = http_post('/fee_types/create', {
            'name': '财务新增收费项',
            'calc_method': 'fixed',
            'unit_price': '66',
            'unit': '元',
            'billing_cycle': 'monthly',
            'sort_order': '28',
            'is_active': 'on',
            'notes': '财务可维护收费项目',
            'reminder_advance_days': '30',
            'return_group': 'property',
        }, finance_cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('/fee_types?group=property', loc)
        self.assertNotIn('/?flash=', loc)
        import server.db as db_module
        db = db_module.get_db()
        fee = db.execute("SELECT id FROM fee_types WHERE name='财务新增收费项'").fetchone()
        db.close()
        self.assertIsNotNone(fee)


    def test_business_text_inputs_disable_browser_autocomplete(self):
        pages = [
            ('/owners', 'name="keyword"'),
            ('/rooms', 'name="keyword"'),
            ('/fee_types/create?group=property', 'name="name"'),
        ]
        for path, marker in pages:
            status, body = http_get(path, self.cookie, TEST_PORT)
            self.assertEqual(status, 200, path)
            self.assertIn(marker, body, path)
            self.assertIn('/static/form_hygiene.js', body, path)
            if 'keyword' in marker:
                self.assertIn('autocomplete="off"', body, path)
            else:
                self.assertIn('autocomplete="new-password"', body, path)

    def test_backup_page_labels_and_filters_auto_backup_types(self):
        http_post('/rooms/create', {
            'building': 'BACKUPFILTER', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-11', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BACKUPFILTER',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-11' LIMIT 1").fetchone()['id'])
        db.close()
        http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': bid,
            'payment_method': 'wechat',
            'operator': '备份分类测试员',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/backups', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成前', html)
        self.assertIn('批量收费前', html)
        self.assertIn('name="type"', html)

        status, filtered = http_get('/backups?type=bill_generation', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成前', filtered)
        self.assertNotIn('auto_before_batch_payment_', filtered)


    def test_closing_close_shows_precheck_before_writing_record(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('结账检查业主', '13400000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSECHECK', 'A座', '1301', 13, '居民', 90, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-03', 100, '2030-03-28', 'paid', 'CC-PAID')
        """, (room_id, owner_id))
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-03', 80, '2030-03-28', 'partial', 'CC-PARTIAL')
        """, (room_id, owner_id))
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-03', 60, '2030-03-28', 'unpaid', 'CC-UNPAID')
        """, (room_id, owner_id))
        db.commit()
        db.close()

        status, html, loc = http_post('/closing/close', {'period': '2030-03', 'notes': '月末结账'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('结账前检查', html)
        self.assertIn('2030-03', html)
        self.assertIn('未缴账单', html)
        self.assertIn('部分缴费', html)
        self.assertIn('异常提醒', html)
        self.assertIn('应收合计', html)
        self.assertIn('本次将结账的账单明细', html)
        self.assertIn('CC-PAID', html)
        self.assertIn('CC-PARTIAL', html)
        self.assertIn('CC-UNPAID', html)
        self.assertIn('240.00', html)
        self.assertIn('确认结账', html)
        db = db_module.get_db()
        closed = db.execute("SELECT COUNT(*) FROM closing_records WHERE period='2030-03' AND status='closed'").fetchone()[0]
        db.close()
        self.assertEqual(closed, 0)


    def test_reopen_closing_requires_confirm_page_before_writing(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("""
            INSERT INTO closing_records(period, close_date, status, operator, notes, paid_count, total_amount)
            VALUES('2030-05', datetime('now','localtime'), 'closed', '管理员', '测试反结账', 3, 300)
        """)
        db.commit()
        db.close()

        status, html = http_get('/closing/reopen?period=2030-05', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('反结账确认', html)
        self.assertIn('2030-05', html)
        self.assertIn('风险提示', html)
        self.assertIn('结账金额', html)
        self.assertIn('300.00', html)
        self.assertIn('当前账单摘要', html)
        self.assertIn('确认反结账', html)
        db = db_module.get_db()
        status_value = db.execute("SELECT status FROM closing_records WHERE period='2030-05'").fetchone()['status']
        db.close()
        self.assertEqual(status_value, 'closed')


    def test_reopen_closing_post_requires_confirm_flag_and_then_reopens(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("""
            INSERT INTO closing_records(period, close_date, status, operator, notes, paid_count, total_amount)
            VALUES('2030-06', datetime('now','localtime'), 'closed', '管理员', '测试确认反结账', 2, 200)
        """)
        db.commit()
        db.close()

        status, html, loc = http_post('/closing/reopen', {'period': '2030-06'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('反结账确认', html)
        db = db_module.get_db()
        status_value = db.execute("SELECT status FROM closing_records WHERE period='2030-06'").fetchone()['status']
        db.close()
        self.assertEqual(status_value, 'closed')

        status, body, loc = http_post('/closing/reopen', {'period': '2030-06', 'confirm': '1'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-06', loc)
        db = db_module.get_db()
        status_value = db.execute("SELECT status FROM closing_records WHERE period='2030-06'").fetchone()['status']
        db.close()
        self.assertEqual(status_value, 'reopened')


