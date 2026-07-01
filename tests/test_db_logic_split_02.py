#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split tests from tests/test_db_logic.py chunk 02."""

from tests.test_db_logic_split_base import *


class TestDBLogic02(DBLogicTestBase):
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


    def test_auto_billing_keeps_current_period_after_service_start(self):
        from server.auto_billing import next_service_period
        start, end, due = next_service_period('2026-06-27', '2027-06-26', 'quarterly', '2026-06-29')
        self.assertEqual(start.isoformat(), '2026-06-27')
        self.assertEqual(end.isoformat(), '2026-09-26')
        self.assertEqual(due.isoformat(), '2026-06-26')


    def test_auto_billing_advances_after_current_period_ends(self):
        from server.auto_billing import next_service_period
        start, end, due = next_service_period('2026-06-27', '2027-06-26', 'quarterly', '2026-09-27')
        self.assertEqual(start.isoformat(), '2026-09-27')
        self.assertEqual(end.isoformat(), '2026-12-26')
        self.assertEqual(due.isoformat(), '2026-09-26')


    def test_auto_billing_preview_includes_active_unbilled_period_with_no_advance_days(self):
        from server.auto_billing import build_auto_billing_preview
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('当前期补账业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOACTIVE', 'B座', '2705', 27, '居民', 100, owner_id, '当前期补账租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        self.db.commit()

        items = build_auto_billing_preview(
            self.db, today='2026-06-29', advance_days=0, fee_ids=[fee_id]
        )
        item = next(x for x in items if x['room_id'] == room_id and x['fee_type_id'] == fee_id)

        self.assertEqual(item['service_start'], '2026-06-27')
        self.assertEqual(item['service_end'], '2026-09-26')
        self.assertEqual(item['due_date'], '2026-06-26')
        self.assertTrue(item['can_generate'])


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
        self.assertEqual(bill['amount'], 618.9)
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


    def test_auto_billing_target_scope_filters_a_b_and_mall_rooms(self):
        from server.auto_billing import build_auto_billing_preview
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('范围筛选业主')").lastrowid
        rows = [
            ('AUTOSCOPE', 'A座', 'A101', '居民', 'A座租户'),
            ('AUTOSCOPE', 'B座', 'B201', '居民', 'B座租户'),
            ('AUTOSCOPE', '商场', 'M301', '商户', '商场租户'),
        ]
        for building, unit, number, category, tenant in rows:
            self.db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (building, unit, number, 1, category, 100, owner_id, tenant, '2026-06-27', '2027-06-26', 'quarterly')
            )
        property_fee = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        merchant_fee = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        self.db.commit()

        b_items = build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30, fee_ids=[property_fee, merchant_fee], target_scope='b')
        mall_items = build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30, fee_ids=[property_fee, merchant_fee], target_scope='mall')

        self.assertEqual({x['room_name'] for x in b_items}, {'AUTOSCOPE-B座-B201'})
        self.assertEqual({x['room_name'] for x in mall_items}, {'AUTOSCOPE-商场-M301'})
