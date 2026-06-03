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
        self.db.execute("DELETE FROM payments")
        self.db.execute("DELETE FROM invoices")
        self.db.execute("DELETE FROM invoice_requests")
        self.db.execute("DELETE FROM bills")
        self.db.execute("DELETE FROM auto_billing_runs")
        self.db.execute("DELETE FROM rooms")
        self.db.execute("DELETE FROM owners")
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

    def test_financial_health_repair_preserves_overdue_without_payments(self):
        from server.data_health import repair_bill_payment_statuses
        rid = self.db.execute("INSERT INTO rooms (building, room_number, area) VALUES ('X','10',10)").lastrowid
        bid = self.db.execute(
            "INSERT INTO bills (room_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?,1,'2025-01',50,'2025-01-01','overdue','HEALTH-OVERDUE-NO-PAYMENT')",
            (rid,)
        ).lastrowid
        self.db.commit()

        result = repair_bill_payment_statuses(self.db)
        self.db.commit()

        row = self.db.execute("SELECT status FROM bills WHERE id=?", (bid,)).fetchone()
        self.assertEqual(result['updated'], 0)
        self.assertEqual(row['status'], 'overdue')


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

    def test_auto_billing_quarterly_service_period_uses_contract_day_range(self):
        from server.auto_billing import next_service_period
        start, end, due = next_service_period('2026-06-27', '2027-06-26', 'quarterly', '2026-05-28')
        self.assertEqual(start.isoformat(), '2026-06-27')
        self.assertEqual(end.isoformat(), '2026-09-26')
        self.assertEqual(due.isoformat(), '2026-06-26')

    def test_auto_billing_preview_can_override_room_cycle_for_this_run(self):
        from server.auto_billing import build_auto_billing_preview
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('自定义账期业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOCYCLE', '商场', 'C101', 1, '商户', 100, owner_id, '自定义账期租户', '2026-06-08', '2027-06-07', 'monthly')
        ).lastrowid
        fee_id = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        self.db.commit()

        items = build_auto_billing_preview(
            self.db, today='2026-05-09', advance_days=30, fee_ids=[fee_id], period_cycle='quarterly'
        )
        item = next(x for x in items if x['room_id'] == room_id and x['fee_type_id'] == fee_id)

        self.assertEqual(item['cycle'], 'quarterly')
        self.assertEqual(item['service_start'], '2026-06-08')
        self.assertEqual(item['service_end'], '2026-09-07')
        self.assertEqual(item['billing_period'], '2026-06~2026-09')
        self.assertEqual(item['amount'], 1500)

    def test_auto_billing_cycle_override_keeps_next_due_start_from_room_cycle(self):
        from server.auto_billing import build_auto_billing_preview
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('历史月付商户业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOCYCLE2', 'B座', '1401', 1, '商户', 100, owner_id, '历史月付商户', '2024-11-08', '2027-11-07', 'monthly')
        ).lastrowid
        fee_id = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        self.db.commit()

        items = build_auto_billing_preview(
            self.db, today='2026-06-03', advance_days=30, fee_ids=[fee_id], period_cycle='quarterly'
        )
        item = next(x for x in items if x['room_id'] == room_id and x['fee_type_id'] == fee_id)

        self.assertEqual(item['service_start'], '2026-06-08')
        self.assertEqual(item['service_end'], '2026-09-07')
        self.assertEqual(item['billing_period'], '2026-06~2026-09')
        self.assertEqual(item['amount'], 1500)

    def test_auto_billing_supports_yearly_service_period(self):
        from server.auto_billing import next_service_period
        start, end, due = next_service_period('2026-06-27', '2028-06-26', 'yearly', '2026-05-28')
        self.assertEqual(start.isoformat(), '2026-06-27')
        self.assertEqual(end.isoformat(), '2027-06-26')
        self.assertEqual(due.isoformat(), '2026-06-26')

    def test_auto_billing_preview_and_confirm_do_not_duplicate_service_period(self):
        from server.auto_billing import build_auto_billing_preview, confirm_auto_billing
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('自动出账业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTO', 'A座', '2701', 27, '居民', 100, owner_id, '自动租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        self.db.commit()

        preview = build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30)
        item = next(x for x in preview if x['room_id'] == room_id and x['fee_type_id'] == fee_id)
        self.assertEqual(item['service_start'], '2026-06-27')
        self.assertEqual(item['service_end'], '2026-09-26')
        self.assertEqual(item['due_date'], '2026-06-26')
        self.assertEqual(item['billing_period'], '2026-06~2026-09')
        self.assertTrue(item['can_generate'])

        result = confirm_auto_billing(self.db, [item['item_key']], today='2026-05-28', advance_days=30)
        self.assertEqual(result['generated'], 1)
        bill = self.db.execute(
            "SELECT service_start,service_end,due_date,billing_period,amount,status FROM bills WHERE room_id=? AND fee_type_id=?",
            (room_id, fee_id)
        ).fetchone()
        self.assertEqual(bill['service_start'], '2026-06-27')
        self.assertEqual(bill['service_end'], '2026-09-26')
        self.assertEqual(bill['due_date'], '2026-06-26')
        self.assertEqual(bill['billing_period'], '2026-06~2026-09')
        self.assertEqual(bill['amount'], 570)
        self.assertEqual(bill['status'], 'unpaid')

        result = confirm_auto_billing(self.db, [item['item_key']], today='2026-05-28', advance_days=30)
        self.assertEqual(result['generated'], 0)
        self.assertEqual(result['skipped_existing'], 1)

    def test_auto_billing_confirm_applies_editable_amount_and_due_date(self):
        from server.auto_billing import build_auto_billing_preview, confirm_auto_billing
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('确认编辑业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOEDIT', 'B座', '2501', 25, '居民', 100, owner_id, '确认编辑租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        self.db.commit()

        item = next(x for x in build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30) if x['room_id'] == room_id and x['fee_type_id'] == fee_id)
        result = confirm_auto_billing(
            self.db, [item['item_key']], today='2026-05-28', advance_days=30,
            adjustments={item['item_key']: {'amount': '618.88', 'due_date': '2026-07-05'}}
        )

        self.assertEqual(result['generated'], 1)
        bill = self.db.execute("SELECT amount,due_date FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        self.assertEqual(bill['amount'], 618.88)
        self.assertEqual(bill['due_date'], '2026-07-05')

    def test_auto_billing_confirm_records_batch_and_rollback_only_safe_bills(self):
        from server.auto_billing import build_auto_billing_preview, confirm_auto_billing, rollback_auto_billing_batch
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('批次业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOBATCH', 'A座', '2601', 26, '居民', 100, owner_id, '批次租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        self.db.commit()

        item = next(x for x in build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30) if x['room_id'] == room_id and x['fee_type_id'] == fee_id)
        result = confirm_auto_billing(self.db, [item['item_key']], today='2026-05-28', advance_days=30, operator='tester')
        self.assertEqual(result['generated'], 1)
        self.assertTrue(result['batch_no'].startswith('AUTO-'))
        batch = self.db.execute("SELECT batch_no,operator,generated_count,status FROM auto_billing_runs WHERE batch_no=?", (result['batch_no'],)).fetchone()
        self.assertEqual(batch['operator'], 'tester')
        self.assertEqual(batch['generated_count'], 1)
        self.assertEqual(batch['status'], 'generated')
        bill = self.db.execute("SELECT id,auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        self.assertEqual(bill['auto_batch_no'], result['batch_no'])

        rb = rollback_auto_billing_batch(self.db, result['batch_no'])
        self.assertEqual(rb['deleted'], 1)
        self.assertEqual(rb['blocked'], 0)
        self.assertIsNone(self.db.execute("SELECT id FROM bills WHERE id=?", (bill['id'],)).fetchone())
        status = self.db.execute("SELECT status,rollback_count FROM auto_billing_runs WHERE batch_no=?", (result['batch_no'],)).fetchone()
        self.assertEqual(status['status'], 'rolled_back')
        self.assertEqual(status['rollback_count'], 1)

    def test_auto_billing_rollback_keeps_paid_bills(self):
        from server.auto_billing import build_auto_billing_preview, confirm_auto_billing, rollback_auto_billing_batch
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('批次缴费业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOPAID', 'A座', '2602', 26, '居民', 100, owner_id, '批次缴费租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        self.db.commit()

        item = next(x for x in build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30) if x['room_id'] == room_id and x['fee_type_id'] == fee_id)
        result = confirm_auto_billing(self.db, [item['item_key']], today='2026-05-28', advance_days=30)
        bill_id = self.db.execute("SELECT id FROM bills WHERE auto_batch_no=?", (result['batch_no'],)).fetchone()['id']
        self.db.execute("INSERT INTO payments(bill_id,amount_paid,payment_method,operator) VALUES(?,?,?,?)", (bill_id, 10, 'cash', 'tester'))
        self.db.commit()

        rb = rollback_auto_billing_batch(self.db, result['batch_no'])
        self.assertEqual(rb['deleted'], 0)
        self.assertEqual(rb['blocked'], 1)
        self.assertIsNotNone(self.db.execute("SELECT id FROM bills WHERE id=?", (bill_id,)).fetchone())

    def test_auto_billing_fee_selection_controls_preview_items(self):
        from server.auto_billing import build_auto_billing_preview
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('自动项目业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOSEL', 'B座', '1801', 18, '居民', 100, owner_id, '项目租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        property_fee = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        elevator_fee = self.db.execute("SELECT id FROM fee_types WHERE name='电梯费'").fetchone()['id']
        self.db.commit()

        default_items = build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30)
        default_for_room = [x['fee_type_id'] for x in default_items if x['room_id'] == room_id]
        self.assertEqual(default_for_room, [property_fee])

        selected_items = build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30, fee_ids=[property_fee, elevator_fee])
        selected_for_room = [x['fee_type_id'] for x in selected_items if x['room_id'] == room_id]
        self.assertEqual(selected_for_room, [property_fee, elevator_fee])


if __name__ == '__main__':
    unittest.main()
