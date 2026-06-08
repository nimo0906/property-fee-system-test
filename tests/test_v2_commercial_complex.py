import os
import tempfile
import unittest
from datetime import date

from server.db import db_init, get_db
from server.contract_billing import create_merchant_contract, generate_contract_bills
from server.cloud_schema import build_postgres_schema
from server.dashboard_v2 import get_enterprise_dashboard_metrics
from server.permissions import role_allows


class TestCommercialComplexCloudV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("PM_DB_PATH")
        os.environ["PM_DB_PATH"] = os.path.join(self.tmp.name, "property.db")
        import server.db as db
        db.DB_PATH = os.environ["PM_DB_PATH"]
        db_init()

    def tearDown(self):
        if self.old_db is None:
            os.environ.pop("PM_DB_PATH", None)
        else:
            os.environ["PM_DB_PATH"] = self.old_db
        import server.db as db
        db.DB_PATH = os.environ.get("PM_DB_PATH") or db.DB_PATH
        self.tmp.cleanup()

    def _seed_mall_room(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO owners(name,phone) VALUES('星河餐饮','13800000000')")
        owner_id = cur.lastrowid
        cur.execute(
            """INSERT INTO rooms(building,unit,room_number,category,area,owner_id,shop_name,custom_rate,payment_cycle)
               VALUES('商场','商场','A-101','商户',120,?,?,8.5,'monthly')""",
            (owner_id, "星河餐饮"),
        )
        room_id = cur.lastrowid
        conn.commit()
        conn.close()
        return room_id, owner_id

    def test_postgres_schema_contains_cloud_contract_foundation(self):
        sql = build_postgres_schema()
        self.assertIn("CREATE TABLE IF NOT EXISTS merchant_contracts", sql)
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

    def test_job_roles_allow_expected_operations(self):
        self.assertTrue(role_allows("system_admin", "admin"))
        self.assertTrue(role_allows("finance", "finance"))
        self.assertTrue(role_allows("cashier", "cashier"))
        self.assertTrue(role_allows("frontdesk", "readonly"))
        self.assertTrue(role_allows("executive", "readonly"))
        self.assertFalse(role_allows("frontdesk", "finance"))
        self.assertFalse(role_allows("cashier", "admin"))

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


if __name__ == "__main__":
    unittest.main()
