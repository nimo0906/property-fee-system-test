import os
import tempfile
import unittest
from pathlib import Path

from server.saas_backoffice import (
    PermissionDenied,
    SaasBackofficeService,
    build_saas_postgres_schema,
    build_saas_migration_plan,
    validate_deployment_assets,
)
from server.db import db_init, get_db


class TestSaasCloudBackoffice(unittest.TestCase):
    def test_postgres_schema_defines_tenant_project_scoped_backoffice_tables(self):
        schema = build_saas_postgres_schema()
        for table in [
            "tenants", "projects", "users", "roles", "permissions", "role_permissions",
            "owners", "charge_targets", "fee_types", "bills", "payments", "imports", "audit_logs",
        ]:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)
        for table in ["projects", "users", "owners", "charge_targets", "fee_types", "bills", "payments", "imports", "audit_logs"]:
            block = schema.split(f"CREATE TABLE IF NOT EXISTS {table}", 1)[1].split(");", 1)[0]
            self.assertIn("tenant_id", block, table)
        for table in ["charge_targets", "fee_types", "bills", "payments", "imports"]:
            block = schema.split(f"CREATE TABLE IF NOT EXISTS {table}", 1)[1].split(");", 1)[0]
            self.assertIn("project_id", block, table)
        self.assertIn("UNIQUE(tenant_id, project_id, bill_number)", schema)

    def test_migration_plan_reports_counts_money_and_period_checks(self):
        with tempfile.TemporaryDirectory() as td:
            old_db = os.environ.get("PM_DB_PATH")
            os.environ["PM_DB_PATH"] = os.path.join(td, "property.db")
            import server.db as db_module
            db_module.DB_PATH = os.environ["PM_DB_PATH"]
            db_init()
            db = get_db()
            owner_id = db.execute("INSERT INTO owners(name,phone) VALUES('迁移客户','13900000000')").lastrowid
            room_id = db.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id) VALUES('住宅楼','1单元','101','居民',80,?)", (owner_id,)).lastrowid
            fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)' LIMIT 1").fetchone()[0]
            bill_id = db.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number,service_start,service_end) VALUES(?,?,?,?,?,?,?,?,?)", (room_id, owner_id, fee_id, '2026-06', 200, 'partial', 'S-001', '2026-06-01', '2026-06-30')).lastrowid
            db.execute("INSERT INTO payments(bill_id,amount_paid,payment_method,operator) VALUES(?,80,'cash','finance')", (bill_id,))
            db.commit(); db.close()
            try:
                plan = build_saas_migration_plan("测试物业", "默认项目")
            finally:
                if old_db is None:
                    os.environ.pop("PM_DB_PATH", None)
                else:
                    os.environ["PM_DB_PATH"] = old_db
                db_module.DB_PATH = os.environ.get("PM_DB_PATH") or db_module.DB_PATH
        self.assertEqual(plan["tenant_name"], "测试物业")
        self.assertEqual(plan["project_name"], "默认项目")
        self.assertEqual(plan["counts"]["owners"], 1)
        self.assertEqual(plan["counts"]["charge_targets"], 1)
        self.assertEqual(plan["money"]["bill_amount_total"], 200.0)
        self.assertEqual(plan["money"]["payment_amount_total"], 80.0)
        self.assertEqual(plan["money"]["unpaid_amount_total"], 120.0)
        names = [item["name"] for item in plan["checks"]]
        self.assertIn("账期一致", names)
        self.assertIn("服务期一致", names)

    def test_tenant_isolation_and_role_permissions(self):
        app = SaasBackofficeService.in_memory()
        tenant_a = app.create_tenant("A物业")
        tenant_b = app.create_tenant("B物业")
        project_a = app.create_project(tenant_a, "A项目")
        project_b = app.create_project(tenant_b, "B项目")
        admin_a = app.create_user(tenant_a, "admin_a", "system_admin")
        finance_a = app.create_user(tenant_a, "finance_a", "finance")
        cashier_a = app.create_user(tenant_a, "cashier_a", "cashier")
        executive_a = app.create_user(tenant_a, "readonly_a", "executive")
        app.create_charge_target(finance_a, project_a, "住宅楼", "1单元", "101", "居民", 80)
        app.create_charge_target(app.create_user(tenant_b, "finance_b", "finance"), project_b, "住宅楼", "1单元", "201", "居民", 90)
        self.assertEqual(len(app.list_charge_targets(admin_a, project_a)), 1)
        self.assertEqual(len(app.list_charge_targets(admin_a, project_b)), 0)
        with self.assertRaises(PermissionDenied):
            app.create_fee_type(cashier_a, project_a, "物业费", 2.5)
        with self.assertRaises(PermissionDenied):
            app.create_charge_target(executive_a, project_a, "住宅楼", "1单元", "102", "居民", 88)

    def test_backoffice_billing_payment_report_flow_and_idempotency(self):
        app = SaasBackofficeService.in_memory()
        tenant = app.create_tenant("云端物业")
        project = app.create_project(tenant, "云端项目")
        finance = app.create_user(tenant, "finance", "finance")
        cashier = app.create_user(tenant, "cashier", "cashier")
        target = app.create_charge_target(finance, project, "住宅楼", "1单元", "101", "居民", 100)
        fee = app.create_fee_type(finance, project, "物业费", 3)
        bill = app.generate_bill(finance, project, target, fee, "2026-06", "2026-06-01", "2026-06-30")
        self.assertEqual(bill["amount"], 300.0)
        payment1 = app.record_payment(cashier, bill["id"], 120, "cash", idempotency_key="PAY-001")
        payment2 = app.record_payment(cashier, bill["id"], 120, "cash", idempotency_key="PAY-001")
        self.assertEqual(payment1["id"], payment2["id"])
        report = app.report(finance, project, "2026-06")
        self.assertEqual(report["bill_count"], 1)
        self.assertEqual(report["bill_amount_total"], 300.0)
        self.assertEqual(report["payment_amount_total"], 120.0)
        self.assertEqual(report["unpaid_amount_total"], 180.0)

    def test_import_preview_does_not_write_until_confirmed(self):
        app = SaasBackofficeService.in_memory()
        tenant = app.create_tenant("导入物业")
        project = app.create_project(tenant, "导入项目")
        finance = app.create_user(tenant, "finance", "finance")
        rows = [
            {"building": "住宅楼", "unit": "1单元", "room_number": "101", "category": "居民", "area": "80"},
            {"building": "住宅楼", "unit": "1单元", "room_number": "102", "category": "居民", "area": "bad"},
        ]
        preview = app.preview_charge_target_import(finance, project, rows)
        self.assertEqual(preview["valid_count"], 1)
        self.assertEqual(preview["error_count"], 1)
        self.assertEqual(len(app.list_charge_targets(finance, project)), 0)
        result = app.confirm_charge_target_import(finance, project, preview["import_id"])
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(len(app.list_charge_targets(finance, project)), 1)

    def test_linux_vps_deployment_assets_are_present_and_safe(self):
        result = validate_deployment_assets(Path.cwd())
        self.assertTrue(result["ok"], result)
        for path in ["docker-compose.yml", ".env.example", "deploy/nginx/property-saas.conf", "deploy/systemd/property-saas.service", "scripts/saas_backup.sh", "scripts/saas_restore.sh"]:
            self.assertIn(path, result["files"])
        env_text = Path(".env.example").read_text(encoding="utf-8")
        self.assertNotIn("SECRET_KEY=changeme", env_text)
        self.assertIn("POSTGRES_DB=property_saas", env_text)


if __name__ == "__main__":
    unittest.main()
