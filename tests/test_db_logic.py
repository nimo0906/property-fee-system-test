#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for database-dependent business logic.

These tests use a real SQLite database (in-memory or temp file).
"""

import unittest, os, tempfile, time

# Ensure project root is on path
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Redirect DB before importing server modules
_db_path = os.path.join(tempfile.gettempdir(), f'test_property_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups')

from server.db import (
    get_db, db_init, get_period,
    calc_elevator_fee, calc_bill_late_fee,
    is_period_closed, get_fee_type_rate,
    update_overdue_bills, BACKUP_DIR,
)


class TestDBLogic(unittest.TestCase):
    """Tests that require a populated test database."""

    @classmethod
    def setUpClass(cls):
        db_init()
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        if os.path.exists(_db_path):
            os.remove(_db_path)
        # clean WAL/SHM files
        for ext in ('-wal', '-shm'):
            p = _db_path + ext
            if os.path.exists(p):
                os.remove(p)

    def setUp(self):
        # Start each test with a clean slate by deleting test data
        self.db.execute("DELETE FROM bills")
        self.db.execute("DELETE FROM rooms")
        self.db.execute("DELETE FROM owners")
        self.db.execute("DELETE FROM payments")
        self.db.execute("DELETE FROM meter_readings")
        self.db.execute("DELETE FROM closing_records")
        self.db.commit()

    # ── Elevator fee ────────────────────────────────────────────

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

    # ── Late fee ────────────────────────────────────────────────

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

    # ── Period closing ──────────────────────────────────────────

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

    # ── Fee type rate ───────────────────────────────────────────

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

    # ── Overdue update ──────────────────────────────────────────

    def test_update_overdue_bills(self):
        """Bills with due_date in the past get status 'overdue'."""
        rid = self.db.execute("INSERT INTO rooms (building, room_number, area) VALUES ('X','3',10)").lastrowid
        self.db.execute(
            "INSERT INTO bills (room_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?,1,'2025-01',50,'2025-01-01','unpaid','OD-TEST')",
            (rid,)
        )
        self.db.commit()

        update_overdue_bills()

        row = self.db.execute("SELECT status FROM bills WHERE bill_number='OD-TEST'").fetchone()
        self.assertEqual(row['status'], 'overdue')

    def test_update_overdue_bills_does_not_affect_paid(self):
        """Paid bills stay 'paid' even if due_date is in the past."""
        rid = self.db.execute("INSERT INTO rooms (building, room_number, area) VALUES ('X','4',10)").lastrowid
        self.db.execute(
            "INSERT INTO bills (room_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?,1,'2025-01',50,'2025-01-01','paid','OD-TEST2')",
            (rid,)
        )
        self.db.commit()

        update_overdue_bills()

        row = self.db.execute("SELECT status FROM bills WHERE bill_number='OD-TEST2'").fetchone()
        self.assertEqual(row['status'], 'paid')


if __name__ == '__main__':
    unittest.main()
