import os
import tempfile
import unittest

from server.cloud_migration import build_migration_summary, export_postgres_seed_sql
from server.db import db_init, get_db


class TestCloudMigration(unittest.TestCase):
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

    def _seed(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO owners(name,phone) VALUES('迁移业主','13900000000')")
        owner_id = cur.lastrowid
        cur.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id,shop_name) VALUES('商场','商场','M-101','商户',100,?,'迁移商户')", (owner_id,))
        room_id = cur.lastrowid
        cur.execute("SELECT id FROM fee_types WHERE name='物业费(商户)' LIMIT 1")
        fee_type_id = cur.fetchone()[0]
        cur.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)", (room_id, owner_id, fee_type_id, '2026-06', 500, 'partial', 'MIG-001'))
        bill_id = cur.lastrowid
        cur.execute("INSERT INTO payments(bill_id,amount_paid,payment_method,operator) VALUES(?,200,'cash','finance')", (bill_id,))
        cur.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id) VALUES('B座','1单元','1801','居民',88,?)", (owner_id,))
        b_room_id = cur.lastrowid
        cur.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number,service_start,service_end) VALUES(?,?,?,?,?,?,?,'2026-06-01','2026-06-30')", (b_room_id, owner_id, fee_type_id, '2026-06', 300, 'unpaid', 'MIG-B-001'))
        cur.execute("""INSERT INTO merchant_contracts(room_id,owner_id,contract_no,merchant_name,shop_name,rent_amount,rent_cycle,property_rate,property_cycle,deposit_amount,start_date,end_date,status,notes)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (room_id, owner_id, 'MIG-HT-001', '迁移商户', '迁移店铺', 3000, 'monthly', 5, 'monthly', 1000, '2026-01-01', '2026-12-31', 'active', '迁移备注'))
        contract_id = cur.lastrowid
        cur.execute("""INSERT INTO contract_attachments(contract_id,attachment_type,original_name,stored_name,file_ext,mime_type,file_size,uploaded_by)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (contract_id, '续签合同', 'renew.pdf', 'stored-renew.pdf', '.pdf', 'application/pdf', 128, 'admin'))
        conn.commit(); conn.close()

    def test_migration_summary_reports_core_counts_and_money(self):
        self._seed()
        summary = build_migration_summary()
        self.assertGreaterEqual(summary["tables"]["owners"], 1)
        self.assertGreaterEqual(summary["tables"]["rooms"], 1)
        self.assertGreaterEqual(summary["tables"]["bills"], 1)
        self.assertEqual(summary["money"]["bill_amount_total"], 800.0)
        self.assertEqual(summary["money"]["payment_amount_total"], 200.0)
        self.assertEqual(summary["scope"]["residential_rooms"], 1)
        self.assertEqual(summary["scope"]["commercial_rooms"], 1)
        self.assertEqual(summary["reconciliation"]["residential_bill_total"], 300.0)
        self.assertEqual(summary["reconciliation"]["commercial_bill_total"], 500.0)
        self.assertEqual(summary["reconciliation"]["service_period_bill_count"], 1)
        self.assertEqual(summary["tables"]["merchant_contracts"], 1)
        self.assertEqual(summary["tables"]["contract_attachments"], 1)
        self.assertIn("PostgreSQL", summary["target"])

    def test_migration_summary_includes_enterprise_reconciliation_checklist(self):
        self._seed()
        summary = build_migration_summary()

        checks = summary["validation_checks"]
        check_names = [item["name"] for item in checks]
        for name in ["业主数量一致", "房间数量一致", "账单数量一致", "收款数量一致", "账单金额一致", "收款金额一致", "欠费金额一致"]:
            self.assertIn(name, check_names)
        bill_check = next(item for item in checks if item["name"] == "账单金额一致")
        self.assertEqual(bill_check["sqlite_value"], 800.0)
        self.assertEqual(bill_check["postgres_expected"], 800.0)
        self.assertEqual(bill_check["status"], "待导入后核对")
        self.assertIn("PostgreSQL", bill_check["description"])
        self.assertEqual(summary["validation_totals"]["owner_count"], 1)
        self.assertEqual(summary["validation_totals"]["room_count"], 2)
        self.assertEqual(summary["validation_totals"]["bill_count"], 2)
        self.assertEqual(summary["validation_totals"]["payment_count"], 1)
        self.assertEqual(summary["validation_totals"]["unpaid_amount_total"], 600.0)

    def test_export_postgres_seed_sql_quotes_values_and_keeps_order(self):
        self._seed()
        sql = export_postgres_seed_sql()
        self.assertIn("-- owners", sql)
        self.assertIn("INSERT INTO owners", sql)
        self.assertIn("迁移业主", sql)
        self.assertIn("迁移商户", sql)
        self.assertIn("MIG-001", sql)
        self.assertIn("-- contract_attachments", sql)
        self.assertIn("续签合同", sql)
        self.assertIn("renew.pdf", sql)
        self.assertIn("-- migration_summary", sql)
        self.assertNotIn("AUTOINCREMENT", sql)

    def test_postgres_schema_includes_contract_lifecycle_and_attachment_tables(self):
        from server.cloud_schema import build_postgres_schema

        schema = build_postgres_schema()
        self.assertIn("CREATE TABLE IF NOT EXISTS contract_attachments", schema)
        self.assertIn("attachment_type TEXT", schema)
        self.assertIn("original_name TEXT NOT NULL", schema)
        self.assertIn("file_size BIGINT NOT NULL DEFAULT 0", schema)
        self.assertIn("notes TEXT", schema)
        self.assertIn("REFERENCES merchant_contracts(id)", schema)

    def test_postgres_schema_seeds_enterprise_job_roles(self):
        from server.cloud_schema import build_postgres_schema

        schema = build_postgres_schema()
        for role_code, role_name in (
            ("system_admin", "系统管理员"),
            ("finance", "财务"),
            ("cashier", "收费员"),
            ("frontdesk", "客服业务编辑"),
            ("executive", "管理层只读"),
        ):
            self.assertIn(role_code, schema)
            self.assertIn(role_name, schema)
        self.assertIn("INSERT INTO cloud_roles", schema)
        self.assertIn("ON CONFLICT (role_code) DO NOTHING", schema)


if __name__ == "__main__":
    unittest.main()
