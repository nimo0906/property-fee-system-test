#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLAlchemy-backed repository for SaaS tenant/project/RBAC seed data."""

from sqlalchemy import create_engine, text

from server.saas_repository_errors import TenantScopeError
from server.saas_repository_guards import validate_bill_scope, validate_import_storage_key
from server.saas_repository_passwords import reset_user_password_record
from server.saas_service import PermissionDenied

class SaasRepository:
    def __init__(self, url):
        self.engine = create_engine(url, future=True)
        self._init_schema()

    def close(self):
        self.engine.dispose()

    def _init_schema(self):
        stmts = [
            "CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active')",
            "CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,name TEXT NOT NULL,code TEXT,is_active INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,name))",
            "CREATE TABLE IF NOT EXISTS roles(code TEXT PRIMARY KEY,name TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS permissions(code TEXT PRIMARY KEY,name TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS role_permissions(role_code TEXT NOT NULL,permission_code TEXT NOT NULL,PRIMARY KEY(role_code,permission_code))",
            "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,username TEXT NOT NULL,role_code TEXT NOT NULL,password_hash TEXT,is_active INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,username))",
            "CREATE TABLE IF NOT EXISTS charge_targets(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,building TEXT NOT NULL,unit TEXT,room_number TEXT NOT NULL,category TEXT NOT NULL,area REAL NOT NULL DEFAULT 0,UNIQUE(tenant_id,project_id,building,unit,room_number))",
            "CREATE TABLE IF NOT EXISTS fee_types(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,name TEXT NOT NULL,unit_price REAL NOT NULL DEFAULT 0,UNIQUE(tenant_id,project_id,name))",
            "CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,charge_target_id INTEGER NOT NULL,fee_type_id INTEGER NOT NULL,bill_number TEXT NOT NULL,billing_period TEXT NOT NULL,service_start TEXT,service_end TEXT,amount REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'pending_review',UNIQUE(tenant_id,project_id,bill_number))",
            "CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,bill_id INTEGER NOT NULL,amount_paid REAL NOT NULL,method TEXT,idempotency_key TEXT,receipt_number TEXT,UNIQUE(tenant_id,idempotency_key))",
            "CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,import_type TEXT NOT NULL,status TEXT NOT NULL,original_name TEXT,storage_key TEXT,file_size INTEGER,content_type TEXT,summary_json TEXT NOT NULL DEFAULT '{}')",
            "CREATE TABLE IF NOT EXISTS backup_records(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,backup_id TEXT NOT NULL,status TEXT NOT NULL,created_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(tenant_id,backup_id))",
            "CREATE TABLE IF NOT EXISTS restore_drills(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,backup_id TEXT NOT NULL,scope TEXT NOT NULL,status TEXT NOT NULL,created_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,user_id INTEGER,action TEXT NOT NULL,entity_type TEXT,entity_id INTEGER,detail_json TEXT NOT NULL DEFAULT '{}')",
        ]
        with self.engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))

    def _row(self, sql, params):
        with self.engine.begin() as conn:
            row = conn.execute(text(sql), params).mappings().first()
            return dict(row) if row else None

    def create_tenant(self, name):
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO tenants(name) VALUES(:name)"), {"name": name})
            return {"id": result.lastrowid, "name": name, "status": "active"}

    def get_tenant(self, tenant_id):
        return self._row("SELECT id,name,status FROM tenants WHERE id=:id", {"id": tenant_id})

    def create_project(self, tenant_id, name, code=None):
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO projects(tenant_id,name,code) VALUES(:tenant_id,:name,:code)"), {"tenant_id": tenant_id, "name": name, "code": code})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "name": name, "code": code}

    def get_project(self, project_id):
        return self._row("SELECT id,tenant_id,name,code,is_active FROM projects WHERE id=:id", {"id": project_id})

    def _require_project_scope(self, tenant_id, project_id):
        project = self.get_project(project_id)
        if not project or int(project["tenant_id"]) != int(tenant_id):
            raise TenantScopeError("project does not belong to tenant")

    def upsert_role(self, code, name):
        with self.engine.begin() as conn:
            conn.execute(text("INSERT OR REPLACE INTO roles(code,name) VALUES(:code,:name)"), {"code": code, "name": name})
        return {"code": code, "name": name}

    def upsert_permission(self, code, name):
        with self.engine.begin() as conn:
            conn.execute(text("INSERT OR REPLACE INTO permissions(code,name) VALUES(:code,:name)"), {"code": code, "name": name})
        return {"code": code, "name": name}

    def grant_permission(self, role_code, permission_code):
        with self.engine.begin() as conn:
            conn.execute(text("INSERT OR IGNORE INTO role_permissions(role_code,permission_code) VALUES(:role_code,:permission_code)"), {"role_code": role_code, "permission_code": permission_code})
        return {"role_code": role_code, "permission_code": permission_code}

    def list_permissions_for_role(self, role_code):
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT permission_code FROM role_permissions WHERE role_code=:role_code ORDER BY permission_code"), {"role_code": role_code}).fetchall()
            return [row[0] for row in rows]

    def _validate_role(self, role_code):
        if role_code not in {"system_admin", "finance", "cashier", "frontdesk", "executive"}:
            raise ValueError("unknown role")

    def create_user(self, tenant_id, username, role_code, password_hash=None):
        self._validate_role(role_code)
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO users(tenant_id,username,role_code,password_hash) VALUES(:tenant_id,:username,:role_code,:password_hash)"), {"tenant_id": tenant_id, "username": username, "role_code": role_code, "password_hash": password_hash})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "username": username, "role_code": role_code}

    def create_staff_user(self, tenant_id, project_id, username, role_code):
        self._require_project_scope(tenant_id, project_id)
        user = self.create_user(tenant_id, username, role_code)
        user["project_id"] = project_id
        return user

    def get_user(self, user_id):
        return self._row("SELECT id,tenant_id,username,role_code,password_hash,is_active FROM users WHERE id=:id", {"id": user_id})

    def create_charge_target(self, tenant_id, project_id, building, unit, room_number, category, area):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            result = conn.execute(text("""INSERT INTO charge_targets(tenant_id,project_id,building,unit,room_number,category,area)
                VALUES(:tenant_id,:project_id,:building,:unit,:room_number,:category,:area)"""),
                {"tenant_id": tenant_id, "project_id": project_id, "building": building, "unit": unit, "room_number": room_number, "category": category, "area": float(area)})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "building": building, "unit": unit, "room_number": room_number, "category": category, "area": float(area)}

    def get_charge_target(self, tenant_id, project_id, target_id):
        return self._row("""SELECT id,tenant_id,project_id,building,unit,room_number,category,area FROM charge_targets
            WHERE tenant_id=:tenant_id AND project_id=:project_id AND id=:id""", {"tenant_id": tenant_id, "project_id": project_id, "id": target_id})

    def list_charge_targets(self, tenant_id, project_id):
        with self.engine.begin() as conn:
            rows = conn.execute(text("""SELECT id,tenant_id,project_id,building,unit,room_number,category,area FROM charge_targets
                WHERE tenant_id=:tenant_id AND project_id=:project_id ORDER BY id"""), {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
            return [dict(r) for r in rows]

    def create_fee_type(self, tenant_id, project_id, name, unit_price):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO fee_types(tenant_id,project_id,name,unit_price) VALUES(:tenant_id,:project_id,:name,:unit_price)"),
                {"tenant_id": tenant_id, "project_id": project_id, "name": name, "unit_price": float(unit_price)})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "name": name, "unit_price": float(unit_price)}

    def get_fee_type(self, tenant_id, project_id, fee_type_id):
        return self._row("""SELECT id,tenant_id,project_id,name,unit_price FROM fee_types
            WHERE tenant_id=:tenant_id AND project_id=:project_id AND id=:id""", {"tenant_id": tenant_id, "project_id": project_id, "id": fee_type_id})

    def create_bill(self, tenant_id, project_id, target_id, fee_type_id, period, service_start, service_end, amount, actor_user_id=None):
        self._require_project_scope(tenant_id, project_id)
        validate_bill_scope(self, tenant_id, project_id, target_id, fee_type_id)
        with self.engine.begin() as conn:
            bill_number = f"SaaS-{tenant_id}-{project_id}-{period}-{target_id}-{fee_type_id}"
            result = conn.execute(text("""INSERT INTO bills(tenant_id,project_id,charge_target_id,fee_type_id,bill_number,billing_period,service_start,service_end,amount,status)
                VALUES(:tenant_id,:project_id,:target_id,:fee_type_id,:bill_number,:period,:service_start,:service_end,:amount,'pending_review')"""),
                {"tenant_id": tenant_id, "project_id": project_id, "target_id": target_id, "fee_type_id": fee_type_id, "bill_number": bill_number, "period": period, "service_start": service_start, "service_end": service_end, "amount": float(amount)})
            item = {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "charge_target_id": target_id, "fee_type_id": fee_type_id, "bill_number": bill_number, "billing_period": period, "amount": float(amount), "status": "pending_review"}
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'bill.generate', 'bill', item['id'], {'bill_number': bill_number, 'amount': float(amount), 'billing_period': period})
        return item

    def approve_bill(self, tenant_id, project_id, bill_id, actor_user_id=None):
        self._require_project_scope(tenant_id, project_id)
        bill = self._row("SELECT id,tenant_id,project_id,charge_target_id,fee_type_id,bill_number,billing_period,service_start,service_end,amount,status FROM bills WHERE id=:id", {"id": bill_id})
        if not bill or int(bill["tenant_id"]) != int(tenant_id) or int(bill["project_id"]) != int(project_id):
            raise TenantScopeError("bill does not belong to tenant")
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE bills SET status='unpaid' WHERE id=:id AND tenant_id=:tenant_id AND project_id=:project_id"), {"id": bill_id, "tenant_id": tenant_id, "project_id": project_id})
        bill["status"] = "unpaid"
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'bill.approve', 'bill', bill_id, {'bill_number': bill['bill_number']})
        return bill

    def list_bills(self, tenant_id, project_id, period=None, status=None):
        self._require_project_scope(tenant_id, project_id)
        sql = "SELECT id,tenant_id,project_id,charge_target_id,fee_type_id,bill_number,billing_period,service_start,service_end,amount,status FROM bills WHERE tenant_id=:tenant_id AND project_id=:project_id"
        params = {"tenant_id": tenant_id, "project_id": project_id}
        if period:
            sql += " AND billing_period=:period"
            params["period"] = period
        if status:
            sql += " AND status=:status"
            params["status"] = status
        sql += " ORDER BY id"
        with self.engine.begin() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
            return [dict(r) for r in rows]

    def create_payment(self, tenant_id, project_id, bill_id, amount, method, idempotency_key, actor_user_id=None):
        self._require_project_scope(tenant_id, project_id)
        bill = self._row("SELECT id,tenant_id,project_id,status FROM bills WHERE id=:id", {"id": bill_id})
        if not bill or int(bill["tenant_id"]) != int(tenant_id) or int(bill["project_id"]) != int(project_id):
            raise TenantScopeError("bill does not belong to tenant")
        if bill["status"] == "pending_review":
            raise PermissionDenied("bill pending review")
        existing = self._row("SELECT id,tenant_id,project_id,bill_id,amount_paid,method,idempotency_key,receipt_number FROM payments WHERE tenant_id=:tenant_id AND idempotency_key=:key", {"tenant_id": tenant_id, "key": idempotency_key}) if idempotency_key else None
        if existing:
            return existing
        with self.engine.begin() as conn:
            seq = conn.execute(text("SELECT COALESCE(MAX(id),0)+1 FROM payments")).scalar_one()
            receipt_number = f"RCPT-{tenant_id}-{project_id}-{int(seq):06d}"
            result = conn.execute(text("""INSERT INTO payments(tenant_id,project_id,bill_id,amount_paid,method,idempotency_key,receipt_number)
                VALUES(:tenant_id,:project_id,:bill_id,:amount,:method,:key,:receipt_number)"""),
                {"tenant_id": tenant_id, "project_id": project_id, "bill_id": bill_id, "amount": float(amount), "method": method, "key": idempotency_key, "receipt_number": receipt_number})
            item = {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "bill_id": bill_id, "amount_paid": float(amount), "method": method, "idempotency_key": idempotency_key, "receipt_number": receipt_number}
            paid = conn.execute(text("SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE tenant_id=:tenant_id AND project_id=:project_id AND bill_id=:bill_id"), {"tenant_id": tenant_id, "project_id": project_id, "bill_id": bill_id}).scalar_one()
            bill_amount = conn.execute(text("SELECT amount FROM bills WHERE id=:bill_id AND tenant_id=:tenant_id AND project_id=:project_id"), {"tenant_id": tenant_id, "project_id": project_id, "bill_id": bill_id}).scalar_one()
            status = "paid" if float(paid or 0) >= float(bill_amount or 0) else "partial"
            conn.execute(text("UPDATE bills SET status=:status WHERE id=:bill_id AND tenant_id=:tenant_id AND project_id=:project_id"), {"status": status, "bill_id": bill_id, "tenant_id": tenant_id, "project_id": project_id})
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'payment.record', 'payment', item['id'], {'bill_id': bill_id, 'amount_paid': float(amount), 'method': method, 'idempotency_key': idempotency_key, 'receipt_number': receipt_number})
        return item

    def report_summary(self, tenant_id, project_id, period):
        with self.engine.begin() as conn:
            bill_row = conn.execute(text("""SELECT COUNT(*) bill_count,COALESCE(SUM(amount),0) due FROM bills
                WHERE tenant_id=:tenant_id AND project_id=:project_id AND billing_period=:period"""), {"tenant_id": tenant_id, "project_id": project_id, "period": period}).mappings().first()
            pay_row = conn.execute(text("""SELECT COALESCE(SUM(p.amount_paid),0) paid FROM payments p JOIN bills b ON p.bill_id=b.id
                WHERE p.tenant_id=:tenant_id AND p.project_id=:project_id AND b.billing_period=:period"""), {"tenant_id": tenant_id, "project_id": project_id, "period": period}).mappings().first()
        due = round(float(bill_row["due"] or 0), 2)
        paid = round(float(pay_row["paid"] or 0), 2)
        return {"bill_count": int(bill_row["bill_count"] or 0), "bill_amount_total": due, "payment_amount_total": paid, "unpaid_amount_total": round(due - paid, 2)}

    def create_audit_log(self, tenant_id, project_id, user_id, action, entity_type, entity_id, detail):
        self._require_project_scope(tenant_id, project_id)
        import json
        with self.engine.begin() as conn:
            result = conn.execute(text("""INSERT INTO audit_logs(tenant_id,project_id,user_id,action,entity_type,entity_id,detail_json)
                VALUES(:tenant_id,:project_id,:user_id,:action,:entity_type,:entity_id,:detail)"""),
                {"tenant_id": tenant_id, "project_id": project_id, "user_id": user_id, "action": action, "entity_type": entity_type, "entity_id": entity_id, "detail": json.dumps(detail, ensure_ascii=False)})
            return {"id": result.lastrowid, "action": action, "detail": detail}

    def list_audit_logs(self, tenant_id, project_id):
        import json
        with self.engine.begin() as conn:
            rows = conn.execute(text("""SELECT id,tenant_id,project_id,user_id,action,entity_type,entity_id,detail_json FROM audit_logs
                WHERE tenant_id=:tenant_id AND project_id=:project_id ORDER BY id"""), {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
            return [{**dict(r), "detail": json.loads(r["detail_json"] or "{}")} for r in rows]

    def create_import_file(self, tenant_id, project_id, import_type, original_name, storage_key, file_size, content_type):
        self._require_project_scope(tenant_id, project_id)
        validate_import_storage_key(tenant_id, project_id, storage_key)
        with self.engine.begin() as conn:
            result = conn.execute(text("""INSERT INTO imports(tenant_id,project_id,import_type,status,original_name,storage_key,file_size,content_type)
                VALUES(:tenant_id,:project_id,:import_type,'uploaded',:original_name,:storage_key,:file_size,:content_type)"""),
                {"tenant_id": tenant_id, "project_id": project_id, "import_type": import_type, "original_name": original_name, "storage_key": storage_key, "file_size": int(file_size), "content_type": content_type})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "import_type": import_type, "status": "uploaded", "original_name": original_name, "storage_key": storage_key, "file_size": int(file_size), "content_type": content_type}

    def list_import_files(self, tenant_id, project_id):
        with self.engine.begin() as conn:
            rows = conn.execute(text("""SELECT id,tenant_id,project_id,import_type,status,original_name,storage_key,file_size,content_type FROM imports
                WHERE tenant_id=:tenant_id AND project_id=:project_id ORDER BY id"""), {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
            return [dict(r) for r in rows]

    def list_tenants(self):
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT id,name,status FROM tenants ORDER BY id")).mappings().all()
            return [dict(r) for r in rows]

    def list_projects(self):
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT id,tenant_id,name,code,is_active FROM projects ORDER BY id")).mappings().all()
            return [dict(r) for r in rows]

    def list_users(self):
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT id,tenant_id,username,role_code,is_active FROM users ORDER BY id")).mappings().all()
            return [dict(r) for r in rows]

    def reset_user_password(self, tenant_id, user_id, new_password, actor_user_id=None, project_id=None):
        target = reset_user_password_record(self, tenant_id, user_id, new_password)
        if actor_user_id and project_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'user.password_reset', 'user', user_id, {
                'target_user_id': user_id,
                'target_username': target.get('username'),
                'target_role_code': target.get('role_code'),
                'password_changed': True,
            })
        return {"user_id": user_id}

    def create_backup_record(self, tenant_id, project_id, user_id):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            seq = conn.execute(text("SELECT COALESCE(MAX(id),0)+1 FROM backup_records")).scalar_one()
            backup_id = f"backup-{int(seq):06d}"
            result = conn.execute(text("""INSERT INTO backup_records(tenant_id,project_id,backup_id,status,created_by)
                VALUES(:tenant_id,:project_id,:backup_id,'created',:user_id)"""),
                {"tenant_id": tenant_id, "project_id": project_id, "backup_id": backup_id, "user_id": user_id})
        self.create_audit_log(tenant_id, project_id, user_id, 'backup.create', 'backup', result.lastrowid, {'backup_id': backup_id, 'kind': 'manual'})
        return {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "backup_id": backup_id, "status": "created"}

    def list_backup_records(self, tenant_id, project_id):
        with self.engine.begin() as conn:
            rows = conn.execute(text("""SELECT id,tenant_id,project_id,backup_id,status,created_by,created_at FROM backup_records
                WHERE tenant_id=:tenant_id AND project_id=:project_id ORDER BY id"""), {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
            return [dict(r) for r in rows]

    def create_restore_drill(self, tenant_id, project_id, user_id, backup_id, scope):
        self._require_project_scope(tenant_id, project_id)
        if scope not in {'database', 'tenant-files', 'system-files'}:
            raise ValueError('invalid restore drill scope')
        with self.engine.begin() as conn:
            result = conn.execute(text("""INSERT INTO restore_drills(tenant_id,project_id,backup_id,scope,status,created_by)
                VALUES(:tenant_id,:project_id,:backup_id,:scope,'recorded',:user_id)"""),
                {"tenant_id": tenant_id, "project_id": project_id, "backup_id": backup_id, "scope": scope, "user_id": user_id})
        self.create_audit_log(tenant_id, project_id, user_id, 'restore.drill', 'restore_drill', result.lastrowid, {'backup_id': backup_id, 'scope': scope})
        return {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "backup_id": backup_id, "scope": scope, "status": "recorded"}

def create_saas_repository(url):
    return SaasRepository(url)

from server.saas_repository_search import attach_repository_search
attach_repository_search(SaasRepository)
