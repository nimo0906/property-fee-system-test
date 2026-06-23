#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 40: prorated billing and commercial contract selection."""

from tests.integration_base import *


class TestIntegration40(IntegrationTestBase):
    def test_billing_prorates_partial_month_but_keeps_full_natural_month(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '按天折算业主', '13900004001')
        room_id = create_room(db, building='PRORATE', unit='B座', room_number='1401', floor=14, category='居民', area=30, owner_id=owner_id)
        fee_id = db.execute("""
            INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes)
            VALUES('按天物业费测试','area',3,'元/m²·月','monthly',26,1,'周期性按服务天数折算')
        """).lastrowid
        db.commit(); db.close()

        status, _, loc = http_post('/billing/calc', {
            'room_id': str(room_id), 'fee_types': str(fee_id),
            'period_start': '2026-06-14', 'period_end': '2026-06-30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        half = db.execute('SELECT amount,service_start,service_end FROM bills WHERE room_id=? AND fee_type_id=? ORDER BY id DESC LIMIT 1', (room_id, fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(half)
        self.assertEqual(half['service_start'], '2026-06-14')
        self.assertEqual(half['service_end'], '2026-06-30')
        self.assertEqual(half['amount'], 51.0)  # 30㎡ * 3元 * 17/30天

        status, _, loc = http_post('/billing/calc', {
            'room_id': str(room_id), 'fee_types': str(fee_id),
            'period_start': '2026-02-01', 'period_end': '2026-02-28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        full = db.execute('SELECT amount FROM bills WHERE room_id=? AND fee_type_id=? AND service_start=?', (room_id, fee_id, '2026-02-01')).fetchone()
        db.close()
        self.assertIsNotNone(full)
        self.assertEqual(full['amount'], 90.0)  # 完整自然月仍按一个月，不按28/30折扣

    def test_quarter_date_range_includes_start_day_and_receipt_shows_full_dates(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '季度日期收据业主', '13900004011')
        room_id = create_room(db, building='RECEIPTDATE', unit='B座', room_number='1001', floor=10, category='商户', area=100, owner_id=owner_id)
        fee_id = db.execute("""
            INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes)
            VALUES('季度完整日期物业费','area',1,'元/m²·月','monthly',46,1,'完整日期收据测试')
        """).lastrowid
        db.commit(); db.close()

        status, _, _ = http_post('/billing/calc', {
            'room_id': str(room_id), 'fee_types': str(fee_id),
            'period_start': '2026-07-01', 'period_end': '2026-09-30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = db_module.get_db()
        bill = db.execute("""SELECT id,amount,billing_period,service_start,service_end FROM bills
            WHERE room_id=? AND fee_type_id=? ORDER BY id DESC LIMIT 1""", (room_id, fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(float(bill['amount']), 300.0)
        self.assertEqual(bill['billing_period'], '2026-07~2026-09')
        self.assertEqual(bill['service_start'], '2026-07-01')
        self.assertEqual(bill['service_end'], '2026-09-30')

        status, receipt_html, _ = http_post('/bills/receipt_by_ids', {
            'bill_ids': str(bill['id']),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-07-01 至 2026-09-30', receipt_html)
        self.assertNotIn('2026-07~2026-09</td>', receipt_html)

    def test_receipt_shows_exact_date_when_end_is_first_day_of_next_month(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '一号截止收据业主', '13900004012')
        room_id = create_room(db, building='RECEIPTDATE', unit='B座', room_number='1002', floor=10, category='商户', area=100, owner_id=owner_id)
        fee_id = db.execute("""
            INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes)
            VALUES('一号截止完整日期物业费','area',1,'元/m²·月','monthly',47,1,'完整日期收据测试')
        """).lastrowid
        db.commit(); db.close()

        status, _, _ = http_post('/billing/calc', {
            'room_id': str(room_id), 'fee_types': str(fee_id),
            'period_start': '2026-07-01', 'period_end': '2026-10-01',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = db_module.get_db()
        bill = db.execute("SELECT id FROM bills WHERE room_id=? AND fee_type_id=? ORDER BY id DESC LIMIT 1", (room_id, fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)

        status, receipt_html, _ = http_post('/bills/receipt_by_ids', {
            'bill_ids': str(bill['id']),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-07-01 至 2026-10-01', receipt_html)
        self.assertNotIn('2026-07~2026-10</td>', receipt_html)

    def test_one_time_fee_does_not_prorate_by_selected_dates(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '固定收费业主', '13900004002')
        room_id = create_room(db, building='ONETIME', unit='商场', room_number='S-01', floor=1, category='商户', area=50, owner_id=owner_id)
        fee_id = db.execute("""
            INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes)
            VALUES('一次性泄水费测试','area',2,'元/m²','once',36,1,'一次性固定收费')
        """).lastrowid
        db.commit(); db.close()

        status, _, loc = http_post('/billing/calc', {
            'room_id': str(room_id), 'fee_types': str(fee_id),
            'period_start': '2026-06-14', 'period_end': '2026-06-30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        bill = db.execute('SELECT amount FROM bills WHERE room_id=? AND fee_type_id=? ORDER BY id DESC LIMIT 1', (room_id, fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['amount'], 100.0)  # 50㎡ * 2元，固定收一次

    def test_commercial_billing_lists_active_contracts_before_compatible_rooms(self):
        from server.contract_billing import create_merchant_contract
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '商业合同收费商户', '13900004003')
        space_id = db.execute("""
            INSERT INTO commercial_spaces(project_id,space_no,floor,area,shop_name,merchant_name,business_type,status)
            VALUES(1,'C-401',4,80,'合同优先店','商业合同收费商户','零售','active')
        """).lastrowid
        room_id = create_room(db, building='商场', unit='商场', room_number='R-401', floor=4, category='商户', area=80, owner_id=owner_id)
        db.execute("UPDATE rooms SET shop_name='兼容房间店' WHERE id=?", (room_id,))
        db.commit(); db.close()
        create_merchant_contract({
            'commercial_space_id': space_id, 'owner_id': owner_id, 'contract_no': 'HT-BILL-SELECT-001',
            'merchant_name': '商业合同收费商户', 'shop_name': '合同优先店', 'rent_amount': 10000,
            'property_rate': 5, 'deposit_amount': 0, 'start_date': '2026-01-01', 'end_date': '2026-12-31',
        })

        status, html = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商业合同', html)
        self.assertIn('兼容房间', html)
        self.assertIn('id="roomSearch"', html)
        self.assertIn('class="form-select searchable-select"', html)
        self.assertIn('searchable_select.js', html)
        select_html = html.split('id="billingRoom"', 1)[1].split('</select>', 1)[0]
        self.assertLess(select_html.index('商业合同'), select_html.index('兼容房间'))
        self.assertIn('HT-BILL-SELECT-001', html)
        self.assertIn('合同优先店', html)


    def test_commercial_contract_water_billing_uses_space_water_standard_and_meter_reading(self):
        from server.contract_billing import create_merchant_contract
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '蓝按SPA商户', '13900004005')
        space_id = db.execute("""
            INSERT INTO commercial_spaces(project_id,space_no,floor,area,shop_name,merchant_name,business_type,water_rate_type,status)
            VALUES(1,'7F-SPA',7,120,'蓝按SPA','蓝按SPA商户','特行服务','特行','active')
        """).lastrowid
        special_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(特行)'").fetchone()['id']
        normal_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()['id']
        db.execute("""INSERT INTO meter_readings(commercial_space_id,fee_type_id,period,previous_reading,current_reading,consumption,status)
                    VALUES(?,?,?,?,?,?,?)""", (space_id, special_fee, '202606', 0, 5, 5, 'confirmed'))
        db.commit(); db.close()
        contract_id = create_merchant_contract({
            'commercial_space_id': space_id, 'owner_id': owner_id, 'contract_no': 'HT-SPA-WATER-001',
            'merchant_name': '蓝按SPA商户', 'shop_name': '蓝按SPA', 'rent_amount': 10000,
            'property_rate': 5, 'deposit_amount': 0, 'start_date': '2026-01-01', 'end_date': '2026-12-31',
        })

        status, html = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        option = html.split(f'value="contract:{contract_id}"', 1)[1].split('</option>', 1)[0]
        self.assertIn('data-water="特行"', option)
        self.assertIn(f'data-meter-target="space:{space_id}"', option)
        self.assertIn(f'"space:{space_id}:{special_fee}:202606": 5.0', html)

        status, _, loc = http_post('/billing/calc', {
            'room_id': f'contract:{contract_id}', 'fee_types': str(special_fee),
            'period_start': '2026-06-01', 'period_end': '2026-06-30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills', loc)
        db = db_module.get_db()
        bill = db.execute("""
            SELECT amount,commercial_space_id,room_id FROM bills
            WHERE source='merchant_contract' AND source_ref=? AND fee_type_id=?
        """, (str(contract_id), special_fee)).fetchone()
        wrong_bill = db.execute("""
            SELECT id FROM bills WHERE source='merchant_contract' AND source_ref=? AND fee_type_id=?
        """, (str(contract_id), normal_fee)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['commercial_space_id'], space_id)
        self.assertIsNone(bill['room_id'])
        self.assertAlmostEqual(float(bill['amount']), 100.55)
        self.assertIsNone(wrong_bill)

    def test_commercial_billing_can_generate_bill_from_contract_selection(self):
        from server.contract_billing import create_merchant_contract, get_contract_fee_type_id
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '合同出账商户', '13900004004')
        space_id = db.execute("""
            INSERT INTO commercial_spaces(project_id,space_no,floor,area,shop_name,merchant_name,business_type,status)
            VALUES(1,'C-402',4,80,'合同出账店','合同出账商户','餐饮','active')
        """).lastrowid
        db.commit(); db.close()
        contract_id = create_merchant_contract({
            'commercial_space_id': space_id, 'owner_id': owner_id, 'contract_no': 'HT-BILL-CALC-001',
            'merchant_name': '合同出账商户', 'shop_name': '合同出账店', 'rent_amount': 10000,
            'property_rate': 5, 'deposit_amount': 0, 'start_date': '2026-01-01', 'end_date': '2026-12-31',
        })
        db = db_module.get_db()
        fee_id = get_contract_fee_type_id(db, '合同物业费')
        db.close()

        status, _, loc = http_post('/billing/calc', {
            'room_id': f'contract:{contract_id}', 'fee_types': str(fee_id),
            'period_start': '2026-06-14', 'period_end': '2026-06-30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        bill = db.execute("""
            SELECT source,source_ref,commercial_space_id,room_id,owner_id,amount,service_start,service_end
            FROM bills WHERE source='merchant_contract' AND source_ref=? AND fee_type_id=?
        """, (str(contract_id), fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['commercial_space_id'], space_id)
        self.assertIsNone(bill['room_id'])
        self.assertEqual(bill['owner_id'], owner_id)
        self.assertEqual(bill['service_start'], '2026-06-14')
        self.assertEqual(bill['service_end'], '2026-06-30')
        self.assertEqual(bill['amount'], 226.67)  # 80㎡ * 5元 * 17/30天
