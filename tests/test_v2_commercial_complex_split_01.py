#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split tests from tests/test_v2_commercial_complex.py chunk 01."""

from tests.test_v2_commercial_complex_split_base import *


class TestCommercialComplexCloudV201(V2CommercialComplexTestBase):
    def test_postgres_schema_contains_cloud_contract_foundation(self):
        sql = build_postgres_schema()
        self.assertIn("CREATE TABLE IF NOT EXISTS merchant_contracts", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS cloud_bills", sql)
        self.assertIn("service_start DATE", sql)
        self.assertIn("service_end DATE", sql)
        self.assertIn("source TEXT", sql)
        self.assertIn("source_ref TEXT", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS cloud_users", sql)
        self.assertIn("project_id BIGINT NOT NULL", sql)
        self.assertIn("role_code TEXT NOT NULL", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS cloud_audit_logs", sql)
        self.assertNotIn("AUTOINCREMENT", sql)


    def test_merchant_contract_generates_rent_property_and_deposit_bills(self):
        room_id, owner_id = self._seed_mall_room()
        contract_id = create_merchant_contract({
            "room_id": room_id,
            "owner_id": owner_id,
            "merchant_name": "星河餐饮",
            "shop_name": "星河餐饮",
            "contract_no": "HT-2026-001",
            "rent_amount": 12000,
            "property_rate": 8.5,
            "deposit_amount": 30000,
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
        })
        result = generate_contract_bills(contract_id, "2026-06", operator="finance")
        self.assertEqual(result["generated_count"], 3)
        self.assertEqual(result["total_amount"], 43020.0)
        conn = get_db()
        rows = conn.execute(
            """SELECT f.name,b.amount,b.source,b.source_ref
               FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
               WHERE b.source='merchant_contract' ORDER BY f.name"""
        ).fetchall()
        conn.close()
        self.assertEqual([r["name"] for r in rows], ["合同押金", "合同物业费", "合同租金"])
        self.assertEqual([float(r["amount"]) for r in rows], [30000.0, 1020.0, 12000.0])
        self.assertTrue(all(r["source_ref"] == str(contract_id) for r in rows))


    def test_contract_billing_preview_uses_service_period_cycles_and_deposit_once(self):
        room_id, owner_id = self._seed_mall_room()
        contract_id = create_merchant_contract({
            "room_id": room_id,
            "owner_id": owner_id,
            "merchant_name": "星河餐饮",
            "shop_name": "星河餐饮",
            "contract_no": "HT-2026-CYCLE",
            "rent_amount": 12000,
            "rent_cycle": "quarterly",
            "property_rate": 8.5,
            "property_cycle": "semiannual",
            "deposit_amount": 30000,
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
        })

        preview = build_contract_billing_preview(contract_id, "2026-06-01")
        self.assertEqual([x["fee_name"] for x in preview["items"]], ["合同租金", "合同物业费", "合同押金"])
        rent, prop, deposit = preview["items"]
        self.assertEqual((rent["service_start"], rent["service_end"], rent["months"], rent["amount"]), ("2026-06-01", "2026-08-31", 3, 36000.0))
        self.assertEqual((prop["service_start"], prop["service_end"], prop["months"], prop["amount"]), ("2026-06-01", "2026-11-30", 6, 6120.0))
        self.assertEqual((deposit["service_start"], deposit["service_end"], deposit["months"], deposit["amount"]), ("2026-06-01", "2027-05-31", 0, 30000.0))

        result = confirm_contract_billing(contract_id, preview["items"], operator="finance")
        self.assertEqual(result["generated_count"], 3)
        self.assertEqual(result["total_amount"], 72120.0)

        second_preview = build_contract_billing_preview(contract_id, "2026-06-01")
        self.assertTrue(all(x["exists"] for x in second_preview["items"]))
        second_result = confirm_contract_billing(contract_id, second_preview["items"], operator="finance")
        self.assertEqual(second_result["generated_count"], 0)

        conn = get_db()
        rows = conn.execute(
            """SELECT f.name,b.amount,b.service_start,b.service_end,b.source,b.source_ref
               FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
               WHERE b.source='merchant_contract' ORDER BY f.name"""
        ).fetchall()
        conn.close()
        self.assertEqual([r["name"] for r in rows], ["合同押金", "合同物业费", "合同租金"])
        self.assertTrue(all(r["source_ref"] == str(contract_id) for r in rows))
        self.assertIn(("合同押金", 30000.0, "2026-06-01", "2027-05-31"), [(r["name"], float(r["amount"]), r["service_start"], r["service_end"]) for r in rows])


    def test_dashboard_counts_contract_arrears_and_expired_contract_risks(self):
        room_id, owner_id = self._seed_mall_room()
        contract_id = create_merchant_contract({
            "room_id": room_id,
            "owner_id": owner_id,
            "merchant_name": "星河餐饮",
            "shop_name": "星河餐饮",
            "contract_no": "HT-RISK-001",
            "rent_amount": 12000,
            "property_rate": 8.5,
            "deposit_amount": 30000,
            "start_date": "2026-06-01",
            "end_date": "2026-06-20",
        })
        confirm_contract_billing(contract_id, build_contract_billing_preview(contract_id, "2026-06-01")["items"])

        metrics = get_enterprise_dashboard_metrics("2026-06", today=date(2026, 7, 1))

        self.assertEqual(metrics["risk_counts"]["contract_unpaid_bills"], 3)
        self.assertEqual(metrics["risk_counts"]["expired_contracts"], 1)


    def test_job_roles_allow_expected_operations(self):
        self.assertTrue(role_allows("system_admin", "admin"))
        self.assertTrue(role_allows("finance", "finance"))
        self.assertTrue(role_allows("cashier", "cashier"))
        self.assertTrue(role_allows("frontdesk", "customer_service"))
        self.assertTrue(role_allows("executive", "readonly"))
        self.assertFalse(role_allows("frontdesk", "finance"))
        self.assertFalse(role_allows("cashier", "admin"))
        self.assertFalse(is_readonly_role("frontdesk"))
        self.assertTrue(is_readonly_role("executive"))
        self.assertTrue(is_readonly_role("readonly"))
        self.assertFalse(is_readonly_role("cashier"))
        self.assertTrue(role_allows("operator", "finance"))


    def test_enterprise_dashboard_metrics_compare_b_tower_and_mall(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO owners(name) VALUES('B座业主')")
        b_owner = cur.lastrowid
        cur.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id) VALUES('B座','1单元','1801','居民',88,?)", (b_owner,))
        b_room = cur.lastrowid
        cur.execute("INSERT INTO owners(name) VALUES('商场商户')")
        m_owner = cur.lastrowid
        cur.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id,shop_name) VALUES('商场','商场','A-101','商户',120,?,'商场商户')", (m_owner,))
        m_room = cur.lastrowid
        cur.execute("SELECT id FROM fee_types WHERE name='物业费(居民)' LIMIT 1")
        fee_id = cur.fetchone()[0]
        cur.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,due_date,bill_number) VALUES(?,?,?,?,?,?,?,?)", (b_room,b_owner,fee_id,'2026-06',100,'paid','2026-06-30','B001'))
        cur.execute("INSERT INTO payments(bill_id,amount_paid,payment_date) VALUES(?,100,'2026-06-10')", (cur.lastrowid,))
        cur.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,due_date,bill_number) VALUES(?,?,?,?,?,?,?,?)", (m_room,m_owner,fee_id,'2026-06',300,'unpaid','2026-06-30','M001'))
        conn.commit(); conn.close()
        metrics = get_enterprise_dashboard_metrics("2026-06", today=date(2026, 6, 8))
        self.assertEqual(metrics["total_due"], 400.0)
        self.assertEqual(metrics["total_paid"], 100.0)
        self.assertEqual(metrics["collection_rate"], 25.0)
        self.assertEqual(metrics["segments"]["B座"]["due"], 100.0)
        self.assertEqual(metrics["segments"]["商场"]["due"], 300.0)
        self.assertEqual(metrics["risk_counts"]["unpaid_bills"], 1)


    def test_enterprise_dashboard_metrics_include_analysis_cards(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO owners(name) VALUES('C1商场商户')")
        owner_id = cur.lastrowid
        cur.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id,shop_name) VALUES('商场','商场','C1-101','商户',120,?,'C1贡献店')", (owner_id,))
        mall_room = cur.lastrowid
        cur.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id) VALUES('B座','B座','C1-1801','居民',88,?)", (owner_id,))
        b_room = cur.lastrowid
        cur.execute("SELECT id FROM fee_types WHERE name='物业费(商户)' LIMIT 1")
        mall_fee = cur.fetchone()[0]
        cur.execute("SELECT id FROM fee_types WHERE name='物业费(居民)' LIMIT 1")
        b_fee = cur.fetchone()[0]
        cur.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)", (mall_room, owner_id, mall_fee, '2026-06', 900, 'unpaid', 'C1-MALL-001'))
        cur.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)", (b_room, owner_id, b_fee, '2026-06', 100, 'paid', 'C1-B-001'))
        b_bill = cur.lastrowid
        cur.execute("INSERT INTO payments(bill_id,amount_paid,payment_date) VALUES(?,100,'2026-06-10')", (b_bill,))
        cur.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)", (mall_room, owner_id, mall_fee, '2026-05', 500, 'unpaid', 'C1-MALL-OLD'))
        conn.commit(); conn.close()

        metrics = get_enterprise_dashboard_metrics("2026-06", today=date(2026, 6, 11))

        self.assertEqual(metrics["segments"]["商场"]["unpaid"], 900.0)
        self.assertEqual(metrics["segments"]["B座"]["collection_rate"], 100.0)
        self.assertEqual(metrics["arrears_trend"][-1]["period"], "2026-06")
        self.assertEqual(metrics["arrears_trend"][-1]["unpaid"], 900.0)
        self.assertEqual(metrics["merchant_contribution"][0]["merchant"], "C1贡献店")
        self.assertEqual(metrics["merchant_contribution"][0]["due"], 900.0)
        self.assertEqual(metrics["fee_structure"][0]["due"], 900.0)


    def test_commercial_spaces_are_independent_from_room_management_contract_billing(self):
        from server.commercial_spaces import create_commercial_space
        space_id = create_commercial_space({
            "space_no": "1F-108",
            "shop_name": "独立商铺",
            "merchant_name": "独立商铺",
            "business_type": "餐饮",
            "floor": 1,
            "area": 90,
            "water_rate_type": "特行",
        })
        contract_id = create_merchant_contract({
            "commercial_space_id": space_id,
            "contract_no": "HT-SPACE-001",
            "merchant_name": "独立商铺",
            "shop_name": "独立商铺",
            "rent_amount": 9000,
            "property_rate": 6,
            "deposit_amount": 10000,
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
        })
        result = generate_contract_bills(contract_id, "2026-06", operator="finance")
        self.assertEqual(result["generated_count"], 3)
        conn = get_db()
        contract = conn.execute("SELECT commercial_space_id,room_id FROM merchant_contracts WHERE id=?", (contract_id,)).fetchone()
        bills = conn.execute("SELECT commercial_space_id,room_id FROM bills WHERE source='merchant_contract' AND source_ref=?", (str(contract_id),)).fetchall()
        room_count = conn.execute("SELECT COUNT(*) FROM rooms WHERE room_number='1F-108' OR shop_name='独立商铺'").fetchone()[0]
        conn.close()
        self.assertEqual(contract["commercial_space_id"], space_id)
        self.assertIsNone(contract["room_id"])
        self.assertEqual(room_count, 0)
        self.assertTrue(bills)
        self.assertTrue(all(r["commercial_space_id"] == space_id and r["room_id"] is None for r in bills))


    def test_meter_readings_support_b_tower_rooms_and_mall_spaces_separately(self):
        from server.commercial_spaces import create_commercial_space
        conn = get_db()
        owner_id = conn.execute("INSERT INTO owners(name) VALUES('B座出租户')").lastrowid
        room_id = conn.execute("""INSERT INTO rooms(building,unit,room_number,category,area,owner_id,tenant_name,water_rate_type)
            VALUES('B座','B座','1201','居民',80,?,'B座租户','非居民')""", (owner_id,)).lastrowid
        water_fee = conn.execute("SELECT id FROM fee_types WHERE name='水费(非居民)' LIMIT 1").fetchone()[0]
        conn.commit(); conn.close()
        space_id = create_commercial_space({"space_no": "2F-201", "shop_name": "商场水表户", "area": 50, "water_rate_type": "非居民"})

        conn = get_db()
        conn.execute("""INSERT INTO meter_readings(room_id,fee_type_id,period,previous_reading,current_reading,consumption,reading_date,status)
            VALUES(?,?,?,?,?,?,?,'confirmed')""", (room_id, water_fee, '202606', 0, 12, 12, '2026-06-30'))
        conn.execute("""INSERT INTO meter_readings(commercial_space_id,fee_type_id,period,previous_reading,current_reading,consumption,reading_date,status)
            VALUES(?,?,?,?,?,?,?,'confirmed')""", (space_id, water_fee, '202606', 0, 33, 33, '2026-06-30'))
        rows = conn.execute("SELECT room_id,commercial_space_id,consumption FROM meter_readings ORDER BY id").fetchall()
        conn.close()
        self.assertEqual((rows[0]['room_id'], rows[0]['commercial_space_id'], rows[0]['consumption']), (room_id, None, 12))
        self.assertEqual((rows[1]['room_id'], rows[1]['commercial_space_id'], rows[1]['consumption']), (None, space_id, 33))

