#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split tests from tests/test_db_logic.py chunk 01."""

from tests.test_db_logic_split_base import *
import sqlite3


class TestDBLogic01(DBLogicTestBase):
    def test_calc_elevator_fee_ground_floor_default_rate(self):
        """Below range 7 → falls through to default rate 1.0"""
        fee = calc_elevator_fee(1, 100)
        self.assertAlmostEqual(fee, 100.0)


    def test_calc_elevator_fee_tier_7_11(self):
        """7-11层 单价1.0"""
        fee = calc_elevator_fee(7, 100)
        self.assertAlmostEqual(fee, 100.0)


    def test_calc_elevator_fee_tier_12_16(self):
        """12-16层 单价1.05"""
        fee = calc_elevator_fee(12, 100)
        self.assertAlmostEqual(fee, 105.0)


    def test_calc_elevator_fee_tier_17_21(self):
        """17-21层 单价1.1"""
        fee = calc_elevator_fee(17, 100)
        self.assertAlmostEqual(fee, 110.0)


    def test_calc_elevator_fee_tier_22_26(self):
        """22-26层 单价1.15"""
        fee = calc_elevator_fee(22, 100)
        self.assertAlmostEqual(fee, 115.0)


    def test_calc_elevator_fee_zero_area(self):
        self.assertAlmostEqual(calc_elevator_fee(10, 0), 0.0)


    def test_calc_elevator_fee_rounded(self):
        self.assertAlmostEqual(calc_elevator_fee(15, 87.5), 91.88)


    def test_late_fee_no_bill(self):
        """Non-existent bill id → 0"""
        self.assertEqual(calc_bill_late_fee(99999), 0)


    def test_late_fee_paid_bill(self):
        """已缴账单 → 0"""
        rid = self.db.execute("INSERT INTO rooms (building, room_number, area) VALUES ('X','1',10)").lastrowid
        bid = self.db.execute(
            "INSERT INTO bills (room_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?,1,'2026-05',100,'2026-05-01','paid','LF-TEST-1')",
            (rid,)
        ).lastrowid
        self.db.commit()
        self.assertEqual(calc_bill_late_fee(bid), 0)


    def test_late_fee_unpaid_not_due(self):
        """未过期（截止日在未来）→ 0"""
        rid = self.db.execute("INSERT INTO rooms (building, room_number, area) VALUES ('X','2',10)").lastrowid
        bid = self.db.execute(
            "INSERT INTO bills (room_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?,1,'2099-01',100,'2099-12-31','unpaid','LF-TEST-2')",
            (rid,)
        ).lastrowid
        self.db.commit()
        self.assertEqual(calc_bill_late_fee(bid), 0)


    def test_period_not_closed_initially(self):
        self.assertFalse(is_period_closed('2026-05'))


    def test_period_closed_after_close(self):
        self.db.execute(
            "INSERT INTO closing_records (period, close_date, status) "
            "VALUES ('2026-04', datetime('now','localtime'), 'closed')"
        )
        self.db.commit()
        self.assertTrue(is_period_closed('2026-04'))
        self.assertFalse(is_period_closed('2026-05'))


    def test_period_reopened_not_closed(self):
        self.db.execute(
            "INSERT INTO closing_records (period, close_date, status) "
            "VALUES ('2026-03', datetime('now','localtime'), 'reopened')"
        )
        self.db.commit()
        self.assertFalse(is_period_closed('2026-03'))


    def test_get_fee_type_rate_default(self):
        """Fee type 1 (物业费(居民)) default rate = 1.9"""
        rate = get_fee_type_rate(1, '居民')
        self.assertAlmostEqual(rate, 1.9)


    def test_get_fee_type_rate_with_tier(self):
        """If a tier exists, it overrides the default rate."""
        ft_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES ('test-rate','area',5.0)"
        ).lastrowid
        self.db.execute(
            "INSERT INTO fee_type_tiers (fee_type_id, category, rate) VALUES (?, '商户', 8.0)",
            (ft_id,)
        )
        self.db.commit()
        rate = get_fee_type_rate(ft_id, '商户')
        self.assertAlmostEqual(rate, 8.0)


    def test_login_rate_limit_is_disabled_for_localhost(self):
        from server.db import check_login_rate

        self.db.execute("DELETE FROM login_attempts")
        self.db.commit()
        for _ in range(10):
            self.db.execute("INSERT INTO login_attempts(ip, success) VALUES('127.0.0.1', 0)")
        self.db.commit()

        self.assertEqual(check_login_rate('127.0.0.1'), 0)


    def test_password_hash_uses_pbkdf2_and_verifies_legacy_sha256(self):
        import hashlib
        from server.passwords import hash_password, is_legacy_sha256_hash, verify_password
        encoded = hash_password('secure123')
        legacy = hashlib.sha256('secure123'.encode()).hexdigest()

        self.assertTrue(encoded.startswith('pbkdf2_sha256$'))
        self.assertTrue(verify_password('secure123', encoded))
        self.assertFalse(verify_password('wrong', encoded))
        self.assertTrue(is_legacy_sha256_hash(legacy))
        self.assertTrue(verify_password('secure123', legacy))


    def test_db_init_seeds_admin_even_when_tiers_exist(self):
        """Old databases may have tiers but no admin user."""
        self.db.execute("DELETE FROM sessions")
        self.db.execute("DELETE FROM users")
        self.db.execute("DELETE FROM elevator_fee_tiers")
        self.db.execute(
            "INSERT INTO elevator_fee_tiers(floor_from,floor_to,rate,label) "
            "VALUES(1,6,0,'existing')"
        )
        self.db.commit()

        db_init()

        admin = self.db.execute("SELECT username, role FROM users WHERE username='admin'").fetchone()
        self.assertIsNotNone(admin)
        self.assertEqual(admin['role'], 'admin')


    def test_db_init_deduplicates_renamed_air_conditioning_fee(self):
        self.db.execute(
            "INSERT INTO fee_types(name, calc_method, unit_price, unit, billing_cycle, sort_order, is_active, notes) "
            "VALUES('空调费(商业)', 'area', 2.5, '元/m²·月', 'monthly', 36, 1, '旧名称')"
        )
        self.db.commit()

        db_init()

        active = self.db.execute(
            "SELECT COUNT(*) FROM fee_types WHERE name='空调能源费' AND is_active=1"
        ).fetchone()[0]
        legacy = self.db.execute(
            "SELECT COUNT(*) FROM fee_types WHERE name='空调费(商业)' AND is_active=1"
        ).fetchone()[0]
        self.assertEqual(active, 1)
        self.assertEqual(legacy, 0)


    def test_db_init_migrates_merchant_contract_room_id_to_nullable(self):
        """Old contract archive DBs had room_id NOT NULL, but space contracts may not link rooms."""
        self.db.execute("DROP TABLE IF EXISTS merchant_contracts")
        self.db.execute(
            """CREATE TABLE merchant_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL DEFAULT 1,
                room_id INTEGER NOT NULL REFERENCES rooms(id),
                owner_id INTEGER REFERENCES owners(id),
                contract_no TEXT NOT NULL UNIQUE,
                merchant_name TEXT NOT NULL,
                shop_name TEXT,
                rent_amount REAL NOT NULL DEFAULT 0,
                rent_cycle TEXT NOT NULL DEFAULT 'monthly',
                property_rate REAL NOT NULL DEFAULT 0,
                property_cycle TEXT NOT NULL DEFAULT 'monthly',
                deposit_amount REAL NOT NULL DEFAULT 0,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                commercial_space_id INTEGER REFERENCES commercial_spaces(id),
                contract_area REAL NOT NULL DEFAULT 0,
                building_area REAL NOT NULL DEFAULT 0
            )"""
        )
        self.db.commit()

        db_init()

        room_id_col = self.db.execute("PRAGMA table_info(merchant_contracts)").fetchall()[2]
        self.assertEqual(room_id_col['name'], 'room_id')
        self.assertEqual(room_id_col['notnull'], 0)
        self.db.execute(
            """INSERT INTO merchant_contracts(
                project_id, room_id, commercial_space_id, contract_no, merchant_name, shop_name,
                rent_amount, rent_cycle, property_rate, property_cycle, deposit_amount,
                start_date, end_date, status, notes, contract_area, building_area
            ) VALUES(1,NULL,NULL,'NULL-ROOM-CONTRACT','无房间空间合同','测试',0,'monthly',0,'monthly',0,'2026-01-01','2026-12-31','active','',0,0)"""
        )


    def test_db_init_creates_scale_indexes_for_large_bill_volume(self):
        db_init()

        index_rows = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        indexes = {r['name'] for r in index_rows}

        expected = {
            'idx_bills_period_status',
            'idx_bills_period_room',
            'idx_bills_period_fee',
            'idx_bills_due_status',
            'idx_rooms_building_room',
            'idx_payments_bill_date',
            'idx_payments_date',
            'idx_adjustments_bill_created',
        }
        self.assertTrue(expected.issubset(indexes), expected - indexes)


    def test_schema_health_detects_and_repairs_missing_tables(self):
        from server.data_health import expected_schema_issues, repair_schema
        self.db.execute("DROP TABLE IF EXISTS notification_events")
        self.db.commit()

        issues = expected_schema_issues(self.db)
        self.assertIn('notification_events', issues['missing_tables'])

        repair_schema()
        repaired = expected_schema_issues(self.db)
        self.assertNotIn('notification_events', repaired['missing_tables'])


    def test_financial_health_repairs_bill_status_from_payments(self):
        from server.data_health import financial_integrity_issues, repair_bill_payment_statuses
        rid = self.db.execute("INSERT INTO rooms (building, room_number, area) VALUES ('X','9',10)").lastrowid
        bid = self.db.execute(
            "INSERT INTO bills (room_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?,1,'2025-01',50,'2025-01-01','paid','HEALTH-PAID-NO-PAYMENT')",
            (rid,)
        ).lastrowid
        self.db.commit()

        issues = financial_integrity_issues(self.db)
        self.assertTrue(any(x['bill_id'] == bid for x in issues['paid_status_but_underpaid']))

        result = repair_bill_payment_statuses(self.db)
        self.db.commit()
        row = self.db.execute("SELECT status FROM bills WHERE id=?", (bid,)).fetchone()
        self.assertEqual(result['updated'], 1)
        self.assertEqual(row['status'], 'unpaid')


    def test_financial_health_removes_stale_payment_linked_to_reused_bill_id(self):
        from server.data_health import financial_integrity_issues, repair_bill_payment_statuses
        rid = self.db.execute("INSERT INTO rooms (building, room_number, area) VALUES ('X','91',10)").lastrowid
        reused_bid = 900001
        self.db.commit()

        raw = sqlite3.connect(db_module.DB_PATH)
        try:
            raw.execute("PRAGMA foreign_keys=OFF")
            raw.execute(
                "INSERT INTO payments (bill_id, amount_paid, payment_date, payment_method, created_at) "
                "VALUES (?,50,'2025-01-02','cash','2025-01-02 00:00:00')",
                (reused_bid,),
            )
            raw.commit()
        finally:
            raw.close()

        new_bid = self.db.execute(
            "INSERT INTO bills (id, room_id, fee_type_id, billing_period, amount, due_date, status, bill_number, created_at) "
            "VALUES (?, ?, 1, '2026-01', 50, '2026-01-31', 'paid', 'STALE-NEW', '2026-01-01 00:00:00')",
            (reused_bid, rid)
        ).lastrowid
        self.db.commit()

        self.assertEqual(new_bid, reused_bid)
        issues = financial_integrity_issues(self.db)
        self.assertTrue(any(x['bill_id'] == new_bid for x in issues['stale_linked_payments']))

        result = repair_bill_payment_statuses(self.db)
        self.db.commit()
        row = self.db.execute("SELECT status FROM bills WHERE id=?", (new_bid,)).fetchone()
        payment_count = self.db.execute("SELECT COUNT(*) FROM payments WHERE bill_id=?", (new_bid,)).fetchone()[0]
        self.assertEqual(result['invalid_payments_deleted'], 1)
        self.assertEqual(payment_count, 0)
        self.assertEqual(row['status'], 'unpaid')
