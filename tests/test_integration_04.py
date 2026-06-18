#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 04."""

from tests.integration_base import *


class TestIntegration04(IntegrationTestBase):
    def test_meter_create_allows_commercial_space_readings_when_space_water_standard_matches(self):
        from server.commercial_spaces import create_commercial_space
        from server.db import get_db

        space_id = create_commercial_space({
            'space_no': 'METER-SP-001',
            'shop_name': '抄表商铺',
            'merchant_name': '抄表商户',
            'business_type': '零售',
            'floor': '1',
            'area': '66',
            'water_rate_type': '特行',
            'status': 'active',
        })
        db = get_db()
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='水费(特行)'").fetchone()[0]
        db.close()

        status, _, loc = http_post('/meter_readings/create', {
            'target_type': 'commercial_space',
            'commercial_space_id': str(space_id),
            'fee_type_id': str(fee_id),
            'period': '2026-06-01',
            'current_reading': '88',
            'reading_date': '2026-06-14',
            'status': 'draft',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('/meter_readings?flash=抄表录入成功', urllib.parse.unquote(loc))
        db = get_db()
        row = db.execute("SELECT room_id,commercial_space_id,fee_type_id,current_reading,status FROM meter_readings WHERE commercial_space_id=?", (space_id,)).fetchone()
        db.close()
        self.assertIsNone(row['room_id'])
        self.assertEqual(row['commercial_space_id'], space_id)
        self.assertEqual(row['status'], 'draft')
        self.assertAlmostEqual(float(row['current_reading']), 88.0)


    def test_meter_list_defaults_to_all_periods_and_supports_keyword_unit_filters(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '抄表筛选业主', '13900000014')
        room_june = create_room(db, building='METERALL', unit='A座', room_number='601', category='商户', owner_id=owner_id)
        room_nov = create_room(db, building='METERALL', unit='商场', room_number='1101', category='商户', owner_id=owner_id)
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()[0]
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status,reading_date) VALUES(?,?,?,?,?,?,?,?)", (room_june, fee_id, '203606', 66, 0, 66, 'confirmed', '2036-06-03'))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status,reading_date) VALUES(?,?,?,?,?,?,?,?)", (room_nov, fee_id, '203611', 111, 0, 111, 'draft', '2036-11-03'))
        db.commit(); db.close()

        status, body = http_get('/meter_readings', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="" onchange="this.form.submit()"', body)
        self.assertIn('METERALL-A座-601', body)
        self.assertIn('METERALL-商场-1101', body)

        status, november = http_get('/meter_readings?period=2036-11-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="2036-11-01" onchange="this.form.submit()"', november)
        self.assertIn('METERALL-商场-1101', november)
        self.assertNotIn('METERALL-A座-601', november)

        status, filtered = http_get('/meter_readings?keyword=1101&unit=%E5%95%86%E5%9C%BA&status=draft', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="1101"', filtered)
        self.assertIn('METERALL-商场-1101', filtered)
        self.assertNotIn('METERALL-A座-601', filtered)


    def test_meter_create_page_uses_unit_first_room_selection(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '抄表二级业主', '13900000015')
        room_a = create_room(db, building='METERUNIT', unit='A座', room_number='701', category='商户', owner_id=owner_id)
        room_mall = create_room(db, building='METERUNIT', unit='商场', room_number='M101', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='A座租户', water_rate_type='非居民' WHERE id=?", (room_a,))
        db.execute("UPDATE rooms SET shop_name='商场店铺', water_rate_type='特行' WHERE id=?", (room_mall,))
        db.commit(); db.close()

        status, body = http_get('/meter_readings/create', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('单元/分区 *', body)
        self.assertIn('id="mUnit"', body)
        self.assertIn('data-unit="商场"', body)
        self.assertIn('data-label="METERUNIT-商场-M101', body)
        self.assertIn('选择单元/分区后再选择收费对象', body)


    def test_meter_create_rejects_water_fee_standard_mismatch(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '抄表错档业主', '13900000011')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM104', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (room_id,))
        special_fee_id = db.execute("SELECT id FROM fee_types WHERE name='水费(特行)'").fetchone()[0]
        db.commit(); db.close()

        status, body, loc = http_post('/meter_readings/create', {
            'room_id': str(room_id),
            'fee_type_id': str(special_fee_id),
            'period': '2026-06-01',
            'current_reading': '100',
            'reading_date': '2026-06-03',
            'status': 'confirmed',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        decoded = urllib.parse.unquote(loc)
        self.assertIn('水费标准', decoded)
        self.assertIn('非居民', decoded)
        self.assertIn('水费(特行)', decoded)
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM meter_readings WHERE room_id=?", (room_id,)).fetchone()[0]
        db.close()
        self.assertEqual(count, 0)


    def test_meter_confirm_rejects_water_fee_standard_mismatch(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '确认错档业主', '13900000012')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM105', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (room_id,))
        special_fee_id = db.execute("SELECT id FROM fee_types WHERE name='水费(特行)'").fetchone()[0]
        mid = db.execute(
            "INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)",
            (room_id, special_fee_id, '202606', 100, 0, 100, 'draft'),
        ).lastrowid
        db.commit(); db.close()

        status, body, loc = http_post(f'/meter_readings/{mid}/confirm', {}, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('水费标准', urllib.parse.unquote(loc))
        db = get_db()
        status_after = db.execute("SELECT status FROM meter_readings WHERE id=?", (mid,)).fetchone()[0]
        db.close()
        self.assertEqual(status_after, 'draft')



    def test_meter_ledger_saves_water_and_electric_together_and_syncs_unpaid_bills(self):
        from server.commercial_spaces import create_commercial_space
        from server.db import get_db

        space_id = create_commercial_space({
            'space_no': 'LEDGER-SP-001',
            'shop_name': '统一抄表商铺',
            'merchant_name': '统一抄表商户',
            'business_type': '餐饮',
            'floor': '1',
            'area': '88',
            'water_rate_type': '特行',
            'status': 'active',
        })
        db = get_db()
        water_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(特行)'").fetchone()['id']
        electric_fee = db.execute("SELECT id FROM fee_types WHERE name='电费(商业)'").fetchone()['id']
        db.execute("""INSERT INTO bills(room_id,commercial_space_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,source_ref)
                      VALUES(NULL,?,?,?,999,'2044-06-30','unpaid','LEDGER-WATER-001','normal',NULL)""", (space_id, water_fee, '2044-06'))
        db.execute("""INSERT INTO bills(room_id,commercial_space_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,source_ref)
                      VALUES(NULL,?,?,?,999,'2044-06-30','paid','LEDGER-ELEC-PAID-001','normal',NULL)""", (space_id, electric_fee, '2044-06'))
        db.commit(); db.close()

        status, page = http_get('/meter_readings/ledger', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('统一抄表台账', page)
        self.assertIn('统一抄表商铺', page)
        self.assertIn('房间管理和合同档案都可在同一商户下一次录入水、电', page)
        self.assertIn('id="ledgerTargetSearch"', page)
        self.assertIn('id="ledgerTarget"', page)
        self.assertIn('searchable_select.js', page)

        status, _, loc = http_post('/meter_readings/ledger/save', {
            'target_type': 'commercial_space',
            'commercial_space_id': str(space_id),
            'period': '2044-06-01',
            'reading_date': '2044-06-15',
            'status': 'draft',
            f'enabled_{water_fee}': 'on',
            f'current_reading_{water_fee}': '100',
            f'enabled_{electric_fee}': 'on',
            f'current_reading_{electric_fee}': '200',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/meter_readings/ledger', loc)

        status, _, loc = http_post('/meter_readings/ledger/save', {
            'target_type': 'commercial_space',
            'commercial_space_id': str(space_id),
            'period': '2044-06-01',
            'reading_date': '2044-06-16',
            'status': 'confirmed',
            f'enabled_{water_fee}': 'on',
            f'current_reading_{water_fee}': '120',
            f'enabled_{electric_fee}': 'on',
            f'current_reading_{electric_fee}': '260',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('已保存2项抄表', urllib.parse.unquote(loc))

        db = get_db()
        rows = db.execute("""SELECT fee_type_id,previous_reading,current_reading,consumption,status,reading_date
                             FROM meter_readings WHERE commercial_space_id=? AND period='204406'
                             ORDER BY fee_type_id""", (space_id,)).fetchall()
        water_bill = db.execute("SELECT amount,status FROM bills WHERE bill_number='LEDGER-WATER-001'").fetchone()
        paid_bill = db.execute("SELECT amount,status FROM bills WHERE bill_number='LEDGER-ELEC-PAID-001'").fetchone()
        db.close()

        self.assertEqual(len(rows), 2)
        by_fee = {r['fee_type_id']: r for r in rows}
        self.assertAlmostEqual(float(by_fee[water_fee]['current_reading']), 120.0)
        self.assertAlmostEqual(float(by_fee[water_fee]['consumption']), 120.0)
        self.assertEqual(by_fee[water_fee]['status'], 'confirmed')
        self.assertEqual(by_fee[water_fee]['reading_date'], '2044-06-16')
        self.assertAlmostEqual(float(by_fee[electric_fee]['current_reading']), 260.0)
        self.assertEqual(water_bill['status'], 'unpaid')
        self.assertAlmostEqual(float(water_bill['amount']), 2413.2)
        self.assertEqual(paid_bill['status'], 'paid')
        self.assertAlmostEqual(float(paid_bill['amount']), 999.0)


    def test_meter_ledger_supports_room_management_target_and_syncs_unpaid_bills(self):
        from server.db import get_db

        db = get_db()
        owner_id = create_owner(db, '房间管理抄表商户', '13900000404')
        room_id = create_room(db, building='金莎国际', unit='商场', room_number='ROOM-LEDGER-001',
                              floor=1, category='商户', area=66, owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='房间管理抄表商户', water_rate_type='非居民' WHERE id=?", (room_id,))
        water_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()['id']
        db.execute("""INSERT INTO bills(room_id,commercial_space_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,source_ref)
                      VALUES(?,NULL,?,?,999,'2044-07-31','unpaid','LEDGER-ROOM-WATER-001','normal',NULL)""", (room_id, water_fee, '2044-07'))
        db.commit(); db.close()

        status, page = http_get(f'/meter_readings/ledger?target=room:{room_id}&period=2044-07-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('房间管理和合同档案都可', page)
        self.assertIn('placeholder="搜索铺位号/房号/店名/商户..."', page)
        self.assertIn('ROOM-LEDGER-001', page)

        status, _, loc = http_post('/meter_readings/ledger/save', {
            'target_type': 'room',
            'room_id': str(room_id),
            'period': '2044-07-01',
            'reading_date': '2044-07-15',
            'status': 'confirmed',
            f'enabled_{water_fee}': 'on',
            f'current_reading_{water_fee}': '30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('已保存1项抄表', urllib.parse.unquote(loc))

        db = get_db()
        reading = db.execute("""SELECT room_id,commercial_space_id,consumption,status
                                FROM meter_readings WHERE room_id=? AND fee_type_id=? AND period='204407'""",
                             (room_id, water_fee)).fetchone()
        bill = db.execute("SELECT amount,status FROM bills WHERE bill_number='LEDGER-ROOM-WATER-001'").fetchone()
        db.close()
        self.assertIsNotNone(reading)
        self.assertEqual(reading['room_id'], room_id)
        self.assertIsNone(reading['commercial_space_id'])
        self.assertAlmostEqual(float(reading['consumption']), 30.0)
        self.assertEqual(reading['status'], 'confirmed')
        self.assertEqual(bill['status'], 'unpaid')
        self.assertAlmostEqual(float(bill['amount']), 174.0)


    def test_shared_expense_unit_label_matches_room_management_wording(self):
        status, body = http_get('/shared_expenses', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('单元/分区', body)
        self.assertIn('全部单元/分区', body)
        self.assertNotIn('单元/座', body)


    def test_shared_expense_page_uses_natural_date_range(self):
        status, body = http_get('/shared_expenses', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="period_start"', body)
        self.assertIn('name="period_end"', body)
        self.assertIn('按财务自然日期范围生成公摊账单', body)
        self.assertNotIn('账期 *', body)


    def test_shared_expense_confirm_sets_service_dates(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('公摊区间业主')").lastrowid
        db.execute("""INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id)
            VALUES('SHARERANGE','A座','801',8,'居民',50,?)""", (owner_id,))
        fid = db.execute("SELECT id FROM fee_types WHERE name='公摊能耗费' LIMIT 1").fetchone()['id']
        db.commit(); db.close()

        status, body, loc = http_post('/shared_expenses/allocate', {
            'mode': 'confirm',
            'period_start': '2033-02-01',
            'period_end': '2033-02-28',
            'fee_type_id': str(fid),
            'total_amount': '100',
            'allocation_method': 'area',
            'building': 'SHARERANGE',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('公摊账单生成完成', body)
        self.assertIn('/bills?period_start=2033-02-01&amp;period_end=2033-02-28', body)

        db = db_module.get_db()
        bill = db.execute("""SELECT b.billing_period,b.service_start,b.service_end,b.due_date,b.source
            FROM bills b JOIN rooms r ON b.room_id=r.id
            WHERE r.building='SHARERANGE' AND b.fee_type_id=?""", (fid,)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2033-02')
        self.assertEqual(bill['service_start'], '2033-02-01')
        self.assertEqual(bill['service_end'], '2033-02-28')
        self.assertEqual(bill['due_date'], '2033-02-28')
        self.assertEqual(bill['source'], 'shared_expense')


    def test_merchant_contract_form_and_billing_preview_flow(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '合同闭环商户', '13900008888')
        room_id = create_room(db, building='商场', unit='商场', room_number='MC-101', category='商户', area=100, owner_id=owner_id)
        db.execute("UPDATE rooms SET shop_name=?, custom_rate=? WHERE id=?", ('合同闭环商户', 9.5, room_id))
        db.commit(); db.close()

        status, form = http_get('/merchant_contracts/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="rent_cycle"', form)
        self.assertIn('name="property_cycle"', form)

        status, body, loc = http_post('/merchant_contracts/create', {
            'room_id': str(room_id),
            'owner_id': str(owner_id),
            'contract_no': 'HT-FLOW-001',
            'merchant_name': '合同闭环商户',
            'rent_amount': '10000',
            'rent_cycle': 'quarterly',
            'property_rate': '9.5',
            'property_cycle': 'monthly',
            'deposit_amount': '20000',
            'start_date': '2036-01-01',
            'end_date': '2036-12-31',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = get_db()
        contract_id = db.execute("SELECT id FROM merchant_contracts WHERE contract_no='HT-FLOW-001'").fetchone()['id']
        db.close()

        status, contracts = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('预览出账', contracts)
        self.assertIn('出账状态', contracts)
        self.assertIn('行政档案/合同备查', contracts)
        self.assertIn('contract-group', contracts)
        self.assertIn('B座合同', contracts)
        self.assertIn('商业合同', contracts)
        self.assertNotIn('导入合同档案', contracts)
        self.assertIn('新增合同档案', contracts)
        self.assertNotIn('去商业收费', contracts)
        self.assertIn('最近服务期', contracts)
        self.assertIn('到期提醒', contracts)
        self.assertIn('未出账', contracts)
        self.assertNotIn('生成本期账单', contracts)

        status, preview = http_get(f'/merchant_contracts/{contract_id}/billing?service_start=2036-01-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('合同出账预览', preview)
        self.assertIn('2036-01-01 至 2036-03-31', preview)
        self.assertIn('合同押金', preview)

        db = get_db()
        before = db.execute(
            "SELECT COUNT(*) FROM bills WHERE source='merchant_contract' AND source_ref=?",
            (str(contract_id),),
        ).fetchone()[0]
        db.close()
        self.assertEqual(before, 0)

        status, result, loc = http_post(f'/merchant_contracts/{contract_id}/billing/confirm', {
            'service_start': '2036-01-01',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/merchant_contracts', loc)

        db = get_db()
        bills = db.execute("""SELECT f.name,b.service_start,b.service_end,b.amount
            FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.source='merchant_contract' AND b.source_ref=? ORDER BY f.name""", (str(contract_id),)).fetchall()
        db.close()
        self.assertEqual(len(bills), 3)
        self.assertIn(('合同租金', '2036-01-01', '2036-03-31', 30000.0), [(b['name'], b['service_start'], b['service_end'], float(b['amount'])) for b in bills])

        status, contracts = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('已出账 3 笔', contracts)
        self.assertIn('欠费 3 笔', contracts)
        self.assertIn('2036-01-01 至 2036-12-31', contracts)
