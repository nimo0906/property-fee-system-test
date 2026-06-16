#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 37: tenant transfer and bill snapshots."""

from tests.integration_base import *


class TestIntegration37(IntegrationTestBase):
    def test_room_tenant_transfer_keeps_old_bill_customer_snapshot(self):
        import server.db as db_module
        from server.bill_snapshots import apply_snapshot, room_snapshot
        db = db_module.get_db()
        owner_id = create_owner(db, '转租业主A', '13800137001')
        room_id = db.execute(
            """INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,tenant_phone,contract_start,contract_end)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            ('B座', 'B座', '3701', 37, '商户', 88, owner_id, '旧租户A', '13800137002', '2026-01-01', '2026-06-30'),
        ).lastrowid
        fee_id = db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", ('转租测试物业费A', 'fixed', 120)).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_id, '2026-06', 120, 'unpaid', 'TRANSFER-ROOM-OLD'),
        ).lastrowid
        apply_snapshot(db, bill_id, room_snapshot(db, room_id, owner_id))
        db.commit(); db.close()

        status, body = http_get(f'/rooms/{room_id}/tenant_transfer', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('转租登记', body)
        self.assertIn('旧租户A', body)

        status, _, loc = http_post(f'/rooms/{room_id}/tenant_transfer', {
            'new_tenant_name': '新租户A',
            'new_tenant_phone': '13800137003',
            'effective_date': '2026-07-01',
            'contract_start': '2026-07-01',
            'contract_end': '2026-12-31',
            'notes': '测试转租',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/rooms', loc)

        status, body = http_get(f'/bills/{bill_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('客户快照', body)
        self.assertIn('旧租户A', body)
        self.assertNotIn('新租户A</td>', body)
        db = db_module.get_db()
        room = db.execute('SELECT tenant_name,tenant_phone,contract_start,contract_end FROM rooms WHERE id=?', (room_id,)).fetchone()
        audits = db.execute("SELECT COUNT(*) FROM audit_logs WHERE action='tenant_transfer' AND entity_type='room' AND entity_id=?", (room_id,)).fetchone()[0]
        db.close()
        self.assertEqual(room['tenant_name'], '新租户A')
        self.assertEqual(room['contract_start'], '2026-07-01')
        self.assertGreaterEqual(audits, 1)

    def test_merchant_contract_transfer_keeps_old_contract_bill_snapshot(self):
        import server.db as db_module
        from server.contract_billing import confirm_contract_billing, build_contract_billing_preview
        db = db_module.get_db()
        space_id = db.execute(
            "INSERT INTO commercial_spaces(space_no,floor,area,shop_name,merchant_name,status) VALUES(?,?,?,?,?,?)",
            ('TR-SP-3702', 1, 60, '旧店铺B', '旧商户B', 'active'),
        ).lastrowid
        contract_id = db.execute(
            """INSERT INTO merchant_contracts(commercial_space_id,contract_no,merchant_name,shop_name,rent_amount,rent_cycle,
               property_rate,property_cycle,deposit_amount,contract_area,building_area,start_date,end_date,status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (space_id, 'TR-OLD-3702', '旧商户B', '旧店铺B', 6000, 'monthly', 6, 'monthly', 3000, 60, 62, '2026-01-01', '2026-12-31', 'active'),
        ).lastrowid
        db.commit(); db.close()
        preview = build_contract_billing_preview(contract_id, '2026-06-01')
        result = confirm_contract_billing(contract_id, preview['items'], 'tester')
        bill_id = result['bill_ids'][0]

        status, body = http_get(f'/merchant_contracts/{contract_id}/transfer', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('合同转租登记', body)
        self.assertIn('旧商户B', body)

        status, _, loc = http_post(f'/merchant_contracts/{contract_id}/transfer', {
            'new_contract_no': 'TR-NEW-3702',
            'new_merchant_name': '新商户B',
            'new_shop_name': '新店铺B',
            'effective_date': '2026-07-01',
            'end_date': '2026-12-31',
            'notes': '测试商业转租',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/merchant_contracts/', loc)

        status, body = http_get(f'/bills/{bill_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('客户快照', body)
        self.assertIn('旧商户B', body)
        self.assertNotIn('新商户B</td>', body)
        db = db_module.get_db()
        old = db.execute('SELECT status,end_date FROM merchant_contracts WHERE id=?', (contract_id,)).fetchone()
        new = db.execute("SELECT id,merchant_name,start_date FROM merchant_contracts WHERE contract_no='TR-NEW-3702'").fetchone()
        space = db.execute('SELECT merchant_name,shop_name FROM commercial_spaces WHERE id=?', (space_id,)).fetchone()
        db.close()
        self.assertEqual(old['status'], 'inactive')
        self.assertEqual(old['end_date'], '2026-06-30')
        self.assertEqual(new['merchant_name'], '新商户B')
        self.assertEqual(new['start_date'], '2026-07-01')
        self.assertEqual(space['merchant_name'], '新商户B')

    def test_readonly_cannot_post_room_tenant_transfer(self):
        import server.db as db_module
        db = db_module.get_db()
        room_id = create_room(db, building='B座', unit='B座', room_number='3703')
        db.execute("UPDATE rooms SET tenant_name='只读旧租户' WHERE id=?", (room_id,))
        db.commit(); db.close()
        cookie = self._create_user_and_login('readonly_transfer_37', 'pw123456', 'readonly', '只读用户')
        status, _, loc = http_post(f'/rooms/{room_id}/tenant_transfer', {
            'new_tenant_name': '只读新租户',
            'effective_date': '2026-07-01',
        }, cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限执行写操作', urllib.parse.unquote(loc))
        db = db_module.get_db()
        name = db.execute('SELECT tenant_name FROM rooms WHERE id=?', (room_id,)).fetchone()[0]
        db.close()
        self.assertEqual(name, '只读旧租户')
