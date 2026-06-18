#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 07."""

from tests.integration_base import *


class TestIntegration07(IntegrationTestBase):
    def test_auto_billing_page_is_independent_and_confirms_contract_based_bills(self):
        from server.db import get_db
        from server.contract_billing import ensure_contract_fee_types
        db = get_db()
        ensure_contract_fee_types(db)
        owner_id = create_owner(db, '自动出账页面业主', '13900007777')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOHTTP', 'B座', '2701', 27, '居民', 100, owner_id, '页面租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        status, body = http_get('/auto_billing?advance_days=30', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('本次服务期', body)
        self.assertIn('出账服务期', body)
        self.assertNotIn('本次出账账期', body)
        self.assertIn('自动出账预览', body)
        self.assertIn('收费项目选择', body)
        self.assertIn('name="period_cycle"', body)
        self.assertIn('name="target_scope"', body)
        self.assertIn('A座', body)
        self.assertIn('B座', body)
        self.assertIn('商业对象', body)
        self.assertIn('物业收费项目', body)
        self.assertIn('商业收费项目', body)
        self.assertIn('其他收费项目', body)
        self.assertNotIn('合同档案项目', body)
        for contract_fee in ['合同租金', '合同物业费', '合同押金']:
            self.assertNotIn(contract_fee, body)
        self.assertIn('按租户资料周期', body)
        self.assertIn('季度', body)
        self.assertIn('按租户合同开始日、结束日、缴费周期计算下一期出账服务期', body)
        self.assertIn('提前 30 天只是筛选即将到期的下一期', body)
        self.assertIn('生成后按缴费截止日进入催缴管理', body)
        self.assertIn('预览汇总', body)
        self.assertRegex(body, r'可生成 \d+ 笔')
        self.assertRegex(body, r'已存在 \d+ 笔')
        self.assertRegex(body, r'涉及租户 \d+ 户')
        self.assertRegex(body, r'涉及房间 \d+ 间')
        self.assertRegex(body, r'应收合计 ¥\d+\.\d{2}')
        self.assertIn('进入生成确认', body)
        self.assertNotIn('确认生成选中账单', body)
        self.assertIn('页面租户', body)
        self.assertIn('2026-06-27 至 2026-09-26', body)
        self.assertIn('2026-06-26', body)
        self.assertIn('href="/auto_billing"', body)

        status, body = http_get('/auto_billing?advance_days=30&target_scope=b&fee_ids=1&fee_ids=3', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('电梯费', body)
        self.assertIn('value="b" selected', body)

        status, quarter_body = http_get(f'/auto_billing?advance_days=30&period_cycle=quarterly&fee_ids={fee_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-06-27 至 2026-09-26', quarter_body)
        self.assertIn('value="quarterly" selected', quarter_body)

        db = get_db()
        existing_owner = create_owner(db, '已存在筛选业主', '13900008888')
        existing_room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOEXIST', 'B座', '2703', 27, '居民', 100, existing_owner, '已存在租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        db.execute("""
            INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (existing_room_id, existing_owner, fee_id, '2026-06~2026-09', 570, '2026-06-26', 'unpaid', 'AUTOEXIST-001', 'auto_contract', '2026-06-27', '2026-09-26'))
        db.commit(); db.close()

        status, only_can = http_get('/auto_billing?advance_days=30&preview_status=can_generate', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('只看可生成', only_can)
        self.assertIn('页面租户', only_can)
        self.assertNotIn('已存在租户', only_can)

        status, only_existing = http_get('/auto_billing?advance_days=30&preview_status=existing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('只看已存在', only_existing)
        self.assertIn('已存在租户', only_existing)
        self.assertNotIn('页面租户', only_existing)
        self.assertIn('同房间、同收费项目、同服务期已存在账单', only_existing)
        self.assertIn('当前筛选条件下没有可生成账单', only_existing)
        self.assertIn('可切换到“全部”或“只看已存在”查看原因', only_existing)
        self.assertIn('检查租户合同开始/结束日期、缴费周期、收费项目是否适用', only_existing)
        self.assertIn('disabled', only_existing)
        self.assertIn('暂无可生成账单', only_existing)
        self.assertNotIn('进入生成确认</button>', only_existing)

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing/runs/', loc)
        self.assertNotIn('keyword=', urllib.parse.unquote(loc))

        db = get_db()
        bill = db.execute(
            "SELECT service_start,service_end,due_date,billing_period,source,auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?",
            (room_id, fee_id)
        ).fetchone()
        db.close()
        self.assertIn(bill['auto_batch_no'], loc)
        status, detail = http_get(loc, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动出账批次详情', detail)
        self.assertIn('查看本批次账单', detail)
        self.assertIn('查看相关催缴', detail)
        status, reminders = http_get('/reminders?period=2026-06-01&status=approaching', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('页面租户', reminders)
        self.assertIn('自动出账', reminders)
        self.assertIn('服务期 2026-06-27 至 2026-09-26', reminders)
        self.assertEqual(bill['service_start'], '2026-06-27')
        self.assertEqual(bill['service_end'], '2026-09-26')
        self.assertEqual(bill['due_date'], '2026-06-26')
        self.assertEqual(bill['billing_period'], '2026-06~2026-09')
        self.assertEqual(bill['source'], 'auto_contract')


    def test_auto_billing_confirm_page_allows_editing_before_final_write(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动确认编辑业主', '13900009991')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOEDITHTTP', 'B座', '2502', 25, '居民', 100, owner_id, '自动确认编辑租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()
        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'

        status, html, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('确认后才会写入账单', html)
        self.assertIn(f'name="amount__{item_key}"', html)
        self.assertIn(f'name="due_date__{item_key}"', html)
        self.assertIn('value="570.00"', html)

        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'confirm': '1',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            f'amount__{item_key}': '618.88',
            f'due_date__{item_key}': '2026-07-05',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing/runs/', loc)

        db = get_db()
        bill = db.execute("SELECT amount,due_date,auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        self.assertEqual(bill['amount'], 618.88)
        self.assertEqual(bill['due_date'], '2026-07-05')
        db.execute("DELETE FROM bills WHERE room_id=?", (room_id,))
        db.execute("DELETE FROM auto_billing_runs WHERE batch_no=?", (bill['auto_batch_no'],))
        db.execute("DELETE FROM rooms WHERE id=?", (room_id,))
        db.execute("DELETE FROM owners WHERE id=?", (owner_id,))
        db.commit(); db.close()


    def test_auto_billing_confirm_page_previews_before_writing_bills(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动确认业主', '13922221111')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOCONFIRM', 'B座', '2702', 27, '居民', 100, owner_id, '确认页租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, html, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('自动出账确认', html)
        self.assertIn('将生成 1 笔账单', html)
        self.assertIn('确认页租户', html)
        self.assertIn('AUTOCONFIRM-B座-2702', html)
        self.assertIn('2026-06-27 至 2026-09-26', html)
        self.assertIn('2026-06-26', html)
        self.assertIn('应收合计', html)
        self.assertIn('¥570.00', html)
        self.assertIn('confirm', html)
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()[0]
        db.close()
        self.assertEqual(count, 0)


    def test_auto_billing_page_lists_and_rolls_back_recent_batch(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动撤回业主', '13933334444')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOROLL', 'B座', '2602', 26, '居民', 100, owner_id, '自动撤回租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        status, page = http_get('/auto_billing?advance_days=30', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('最近自动出账记录', page)
        self.assertIn('撤回未缴账单', page)

        db = get_db()
        batch_no = db.execute("SELECT auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()['auto_batch_no']
        db.close()
        status, body, loc = http_post(f'/auto_billing/runs/{batch_no}/rollback', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing', loc)
        db = get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()[0], 0)
        run = db.execute("SELECT status,rollback_count FROM auto_billing_runs WHERE batch_no=?", (batch_no,)).fetchone()
        db.close()
        self.assertEqual(run['status'], 'rolled_back')
        self.assertEqual(run['rollback_count'], 1)


