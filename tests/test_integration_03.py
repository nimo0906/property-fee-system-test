#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 03."""

from tests.integration_base import *


class TestIntegration03(IntegrationTestBase):
    def test_payments_page_groups_by_room_and_exports_csv(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '缴费业主', '13900000000')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='1801', owner_id=owner_id)
        fee_id = db.execute("INSERT INTO fee_types(name, calc_method, unit_price, sort_order, is_active) VALUES(?,?,?,?,1)",
                            ('物业服务费', 'area', 2.5, 10)).lastrowid
        db.commit()
        bill_id = create_bill(db, room_id=room_id, fee_type_id=fee_id, period='2026-05', amount=250, owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=250, method='transfer', operator='测试经手人')
        db.close()

        status, body = http_get('/payments?period=2026-05-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('导出CSV', body)
        self.assertIn('payment-group', body)
        self.assertIn('金莎国际-B座-1801', body)
        self.assertIn('缴费业主', body)

        status, csv_body = http_get('/payments/export.csv?period=2026-05-01&method=transfer&operator=%E6%B5%8B%E8%AF%95%E7%BB%8F%E6%89%8B%E4%BA%BA', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('payment_date,receipt_number,bill_number', csv_body)
        self.assertIn('金莎国际', csv_body)
        self.assertIn('测试经手人', csv_body)


    def test_payments_keyword_filters_by_room_owner_tenant_and_exports_csv(self):
        from server.db import get_db
        db = get_db()
        owner_a = create_owner(db, '缴费搜索业主A', '13900001001')
        owner_b = create_owner(db, '缴费搜索业主B', '13900001002')
        room_a = create_room(db, building='金莎国际', unit='B座', room_number='PAY-1423', category='商户', owner_id=owner_a)
        room_b = create_room(db, building='金莎国际', unit='B座', room_number='PAY-9999', category='商户', owner_id=owner_b)
        db.execute("UPDATE rooms SET tenant_name=? WHERE id=?", ('搜索租户甲', room_a))
        db.execute("UPDATE rooms SET tenant_name=? WHERE id=?", ('搜索租户乙', room_b))
        bill_a = create_bill(db, room_id=room_a, owner_id=owner_a, fee_type_id=1, period='2038-08', amount=1423, status='paid')
        bill_b = create_bill(db, room_id=room_b, owner_id=owner_b, fee_type_id=1, period='2038-08', amount=9999, status='paid')
        create_payment(db, bill_id=bill_a, amount=1423, method='transfer', operator='搜索经手人')
        create_payment(db, bill_id=bill_b, amount=9999, method='transfer', operator='搜索经手人')
        db.commit(); db.close()

        status, body = http_get('/payments?period=2038-08-01&operator=%E6%90%9C%E7%B4%A2%E7%BB%8F%E6%89%8B%E4%BA%BA&keyword=PAY-1423', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="keyword"', body)
        self.assertIn('value="PAY-1423"', body)
        self.assertIn('PAY-1423', body)
        self.assertNotIn('PAY-9999', body)
        self.assertIn('¥1423.00', body)
        self.assertNotIn('¥9999.00', body)

        status, tenant_body = http_get('/payments?period=2038-08-01&operator=%E6%90%9C%E7%B4%A2%E7%BB%8F%E6%89%8B%E4%BA%BA&keyword=%E6%90%9C%E7%B4%A2%E7%A7%9F%E6%88%B7%E4%B9%99', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('PAY-9999', tenant_body)
        self.assertNotIn('PAY-1423', tenant_body)

        status, csv_body = http_get('/payments/export.csv?period=2038-08-01&operator=%E6%90%9C%E7%B4%A2%E7%BB%8F%E6%89%8B%E4%BA%BA&keyword=PAY-1423', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('PAY-1423', csv_body)
        self.assertNotIn('PAY-9999', csv_body)


    def test_payments_default_page_shows_all_periods_until_user_filters_period(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '缴费默认全部业主', '13900009999')
        room_id = create_room(db, building='PAYALL', unit='A座', room_number='9901', category='居民', owner_id=owner_id)
        paid_june = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2038-06', amount=10, status='paid')
        paid_july = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2038-07', amount=20, status='paid')
        create_payment(db, bill_id=paid_june, amount=10, method='cash', operator='默认全部')
        create_payment(db, bill_id=paid_july, amount=20, method='cash', operator='默认全部')
        db.close()

        status, body = http_get('/payments?operator=%E9%BB%98%E8%AE%A4%E5%85%A8%E9%83%A8', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('2038-06', body)
        self.assertIn('2038-07', body)
        self.assertIn('¥30.00', body)

        status, filtered = http_get('/payments?period=2038-06-01&operator=%E9%BB%98%E8%AE%A4%E5%85%A8%E9%83%A8', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2038-06', filtered)
        self.assertNotIn('2038-07', filtered)
        self.assertIn('¥10.00', filtered)


    def test_property_billing_excludes_commercial_only_fee_names_even_if_sort_order_is_low(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '物业B座商户业主', '13900000008')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='B-M01', category='商户', owner_id=owner_id)
        db.execute("UPDATE fee_types SET sort_order=17, is_active=1 WHERE name='泄水费'")
        db.commit(); db.close()

        status, body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('金莎国际-B座-B-M01', body)
        self.assertNotIn('泄水费', body)
        self.assertNotIn('装修押金', body)
        self.assertNotIn('空调能源费', body)


    def test_commercial_billing_shows_water_fees_for_every_merchant_and_uses_water_standard(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商业水费业主', '13900000004')
        normal_id = create_room(db, building='金莎国际', unit='商场', room_number='CW101', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (normal_id,))
        normal_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()[0]
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (normal_id, normal_fee, '202605', 10, 0, 10, 'confirmed'))
        db.commit(); db.close()

        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('金莎国际-商场-CW101', body)
        self.assertIn('data-water="非居民"', body)
        self.assertIn('水费(非居民)', body)
        self.assertNotIn('商场商业收费已迁移', body)

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(normal_id),
            'fee_types': str(normal_fee),
            'period_start': '2026-05-01',
            'period_end': '2026-05-28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills', loc)
        db = get_db()
        bill = db.execute("SELECT amount,billing_period FROM bills WHERE room_id=? AND fee_type_id=?", (normal_id, normal_fee)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2026-05')
        self.assertAlmostEqual(float(bill['amount']), 58.0)


    def test_room_water_rate_type_controls_water_fee_standard(self):
        from server.db import get_db
        from server.billing_engine import calculate_bill_amount, fee_applies_to_room
        db = get_db()
        owner_id = create_owner(db, '水费档位业主', '13900000003')
        normal_id = create_room(db, building='金莎国际', unit='商场', room_number='W101', category='商户', owner_id=owner_id)
        special_id = create_room(db, building='金莎国际', unit='商场', room_number='W102', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (normal_id,))
        db.execute("UPDATE rooms SET water_rate_type='特行' WHERE id=?", (special_id,))
        normal_room = db.execute("SELECT * FROM rooms WHERE id=?", (normal_id,)).fetchone()
        special_room = db.execute("SELECT * FROM rooms WHERE id=?", (special_id,)).fetchone()
        normal_fee = db.execute("SELECT * FROM fee_types WHERE name='水费(非居民)'").fetchone()
        special_fee = db.execute("SELECT * FROM fee_types WHERE name='水费(特行)'").fetchone()
        self.assertTrue(fee_applies_to_room(normal_fee['name'], normal_room))
        self.assertFalse(fee_applies_to_room(special_fee['name'], normal_room))
        self.assertTrue(fee_applies_to_room(special_fee['name'], special_room))
        self.assertFalse(fee_applies_to_room(normal_fee['name'], special_room))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (normal_id, normal_fee['id'], '202605', 10, 0, 10, 'confirmed'))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (special_id, special_fee['id'], '202605', 10, 0, 10, 'confirmed'))
        db.commit()
        self.assertEqual(calculate_bill_amount(db, normal_room, normal_fee, '2026-05')['amount'], 58.0)
        self.assertEqual(calculate_bill_amount(db, special_room, special_fee, '2026-05')['amount'], 201.1)
        db.close()


    def test_meter_billing_sums_confirmed_readings_across_selected_range(self):
        from server.db import get_db
        from server.billing_engine import calculate_bill_amount
        db = get_db()
        owner_id = create_owner(db, '跨月水费业主', '13900000005')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM101', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (room_id,))
        room = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
        fee = db.execute("SELECT * FROM fee_types WHERE name='水费(非居民)'").fetchone()
        for period, consumption, status in [('202606', 10, 'confirmed'), ('202607', 8, 'confirmed'), ('202608', 4, 'draft')]:
            db.execute(
                "INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)",
                (room_id, fee['id'], period, consumption, 0, consumption, status),
            )
        db.commit()

        calc = calculate_bill_amount(db, room, fee, '2026-06~2026-08', 3)

        self.assertEqual(calc['amount'], 104.4)
        self.assertIn('用量合计18', calc['formula'])
        self.assertNotIn('×3个月', calc['formula'])
        db.close()


    def test_billing_page_embeds_confirmed_meter_readings_for_frontend_calculation(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '收费页抄表业主', '13900000006')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM102', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (room_id,))
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()[0]
        db.execute(
            "INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)",
            (room_id, fee_id, '202606', 16, 0, 16, 'confirmed'),
        )
        db.commit(); db.close()

        status, body = http_get('/billing', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('window.METER_READINGS=', body)
        self.assertIn(f'"{room_id}:{fee_id}:202606": 16.0', body)


    def test_room_water_rate_type_controls_water_fee_display_even_for_residential_category(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '水费显示业主', '13900000014')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM107', category='居民', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (room_id,))
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()[0]
        db.execute(
            "INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)",
            (room_id, fee_id, '202606', 12, 0, 12, 'confirmed'),
        )
        db.commit(); db.close()

        status, body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('水费(非居民)', body)
        self.assertIn(f'"{room_id}:{fee_id}:202606": 12.0', body)
        self.assertIn('window.METER_READINGS=', body)


    def test_meter_create_page_hints_room_water_rate_type_for_fee_selection(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '抄表提示业主', '13900000013')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM106', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='特行' WHERE id=?", (room_id,))
        db.commit(); db.close()

        status, body = http_get('/meter_readings/create', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('房间管理水费类型提示', body)
        self.assertIn('data-water="特行"', body)
        self.assertIn('WM106', body)
        self.assertIn('建议选择：水费(特行)', body)
        self.assertIn('id="waterFeeHint"', body)


