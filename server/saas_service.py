#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-memory SaaS backoffice domain service for first cloud slice tests."""


class PermissionDenied(Exception):
    pass


ROLE_PERMISSIONS = {
    "system_admin": {"read", "write", "manage_users", "backup", "billing", "payment", "import"},
    "finance": {"read", "write", "billing", "payment", "import"},
    "cashier": {"read", "payment"},
    "frontdesk": {"read", "write", "import"},
    "executive": {"read"},
}


class SaasBackofficeService:
    @classmethod
    def in_memory(cls):
        return cls()

    def __init__(self):
        self._seq = 1
        self.tenants = {}
        self.projects = {}
        self.users = {}
        self.targets = {}
        self.fees = {}
        self.bills = {}
        self.payments = {}
        self.payment_keys = {}
        self.imports = {}
        self.backup_records = {}
        self.restore_drills = {}
        self.audit_logs = []

    def _id(self):
        value = self._seq
        self._seq += 1
        return value

    def _require(self, user, perm):
        if perm not in ROLE_PERMISSIONS.get(user["role_code"], set()):
            raise PermissionDenied(f"{user['role_code']} lacks {perm}")

    def _same_tenant_project(self, user, project_id):
        project = self.projects.get(project_id)
        return bool(project and project["tenant_id"] == user["tenant_id"])

    def _log(self, user, project_id, action, entity_type=None, entity_id=None, detail=None):
        row = {
            "id": self._id(),
            "tenant_id": user["tenant_id"],
            "project_id": project_id,
            "user_id": user["id"],
            "username": user["username"],
            "role_code": user["role_code"],
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "detail": detail or {},
        }
        self.audit_logs.append(row)
        return row

    def create_tenant(self, name):
        tid = self._id()
        self.tenants[tid] = {"id": tid, "name": name}
        return tid

    def create_project(self, tenant_id, name):
        pid = self._id()
        self.projects[pid] = {"id": pid, "tenant_id": tenant_id, "name": name}
        return pid

    def _default_project_id(self, tenant_id):
        return next((p["id"] for p in self.projects.values() if p["tenant_id"] == tenant_id), None)

    def _validate_role(self, role_code):
        if role_code not in ROLE_PERMISSIONS:
            raise ValueError("unknown role")

    def create_user(self, tenant_id, username, role_code):
        self._validate_role(role_code)
        uid = self._id()
        user = {
            "id": uid,
            "tenant_id": tenant_id,
            "project_id": self._default_project_id(tenant_id),
            "username": username,
            "role_code": role_code,
        }
        self.users[uid] = user
        return user

    def create_staff_user(self, user, project_id, username, role_code):
        self._require(user, "manage_users")
        self._validate_role(role_code)
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        new_user = self.create_user(user["tenant_id"], username, role_code)
        new_user["project_id"] = project_id
        self._log(user, project_id, 'user.create', 'user', new_user['id'], {'username': username, 'role_code': role_code})
        return new_user

    def create_charge_target(self, user, project_id, building, unit, room_number, category, area):
        self._require(user, "write")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        tid = self._id()
        target = {"id": tid, "tenant_id": user["tenant_id"], "project_id": project_id,
                  "building": building, "unit": unit, "room_number": room_number,
                  "category": category, "area": float(area)}
        self.targets[tid] = target
        self._log(user, project_id, 'charge_target.create', 'charge_target', tid, {'building': building, 'room_number': room_number})
        return target

    def list_charge_targets(self, user, project_id):
        self._require(user, "read")
        if not self._same_tenant_project(user, project_id):
            return []
        return [t for t in self.targets.values() if t["tenant_id"] == user["tenant_id"] and t["project_id"] == project_id]

    def create_fee_type(self, user, project_id, name, unit_price):
        self._require(user, "write")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        fid = self._id()
        fee = {"id": fid, "tenant_id": user["tenant_id"], "project_id": project_id,
               "name": name, "unit_price": float(unit_price)}
        self.fees[fid] = fee
        self._log(user, project_id, 'fee_type.create', 'fee_type', fid, {'name': name, 'unit_price': float(unit_price)})
        return fee

    def generate_bill(self, user, project_id, target, fee, period, service_start, service_end):
        self._require(user, "billing")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        if target["tenant_id"] != user["tenant_id"] or target["project_id"] != project_id:
            raise PermissionDenied("cross tenant target")
        if fee["tenant_id"] != user["tenant_id"] or fee["project_id"] != project_id:
            raise PermissionDenied("cross tenant fee")
        amount = round(float(target["area"]) * float(fee["unit_price"]), 2)
        bid = self._id()
        bill = {"id": bid, "tenant_id": user["tenant_id"], "project_id": project_id,
                "charge_target_id": target["id"], "fee_type_id": fee["id"],
                "billing_period": period, "service_start": service_start, "service_end": service_end,
                "bill_number": f"BILL-{bid:06d}", "amount": amount, "status": "unpaid"}
        self.bills[bid] = bill
        self._log(user, project_id, 'bill.generate', 'bill', bid, {'bill_number': bill['bill_number'], 'amount': amount, 'billing_period': period})
        return bill

    def record_payment(self, user, bill_id, amount, method, idempotency_key=None):
        self._require(user, "payment")
        bill = self.bills[bill_id]
        if bill["tenant_id"] != user["tenant_id"] or bill["project_id"] != user["project_id"]:
            raise PermissionDenied("cross tenant bill")
        key = (user["tenant_id"], idempotency_key) if idempotency_key else None
        if key and key in self.payment_keys:
            return self.payments[self.payment_keys[key]]
        pid = self._id()
        payment = {"id": pid, "tenant_id": user["tenant_id"], "project_id": bill["project_id"],
                   "bill_id": bill_id, "amount_paid": float(amount), "method": method,
                   "idempotency_key": idempotency_key}
        self.payments[pid] = payment
        if key:
            self.payment_keys[key] = pid
        paid = sum(p["amount_paid"] for p in self.payments.values() if p["bill_id"] == bill_id)
        bill["status"] = "paid" if paid >= bill["amount"] else "partial"
        self._log(user, bill['project_id'], 'payment.record', 'payment', pid, {'bill_id': bill_id, 'amount_paid': float(amount), 'method': method, 'idempotency_key': idempotency_key})
        return payment

    def report(self, user, project_id, period):
        self._require(user, "read")
        bills = [b for b in self.bills.values() if b["tenant_id"] == user["tenant_id"] and b["project_id"] == project_id and b["billing_period"] == period]
        bill_ids = {b["id"] for b in bills}
        payments = [p for p in self.payments.values() if p["tenant_id"] == user["tenant_id"] and p["bill_id"] in bill_ids]
        due = round(sum(b["amount"] for b in bills), 2)
        paid = round(sum(p["amount_paid"] for p in payments), 2)
        return {"bill_count": len(bills), "bill_amount_total": due,
                "payment_amount_total": paid, "unpaid_amount_total": round(due - paid, 2)}

    def preview_charge_target_import(self, user, project_id, rows):
        self._require(user, "import")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        valid, errors = [], []
        for idx, row in enumerate(rows, start=1):
            try:
                building = str(row.get("building") or "").strip()
                room_number = str(row.get("room_number") or "").strip()
                if not building:
                    raise ValueError("楼栋/区域不能为空")
                if not room_number:
                    raise ValueError("房号/铺位号不能为空")
                area = float(row.get("area") or 0)
                if area <= 0:
                    raise ValueError("面积必须是数字且大于0")
                valid.append({**row, "building": building, "room_number": room_number, "area": area})
            except ValueError as exc:
                errors.append({"row": idx, "error": str(exc)})
        iid = self._id()
        self.imports[iid] = {"id": iid, "tenant_id": user["tenant_id"], "project_id": project_id,
                             "valid_rows": valid, "errors": errors, "confirmed": False}
        self._log(user, project_id, 'import.preview', 'import', iid, {'valid_count': len(valid), 'error_count': len(errors)})
        return {"import_id": iid, "valid_count": len(valid), "error_count": len(errors), "errors": errors}

    def get_import_review(self, user, project_id, import_id):
        self._require(user, "import")
        imp = self.imports[import_id]
        if imp["tenant_id"] != user["tenant_id"] or imp["project_id"] != project_id:
            raise PermissionDenied("cross tenant import")
        return {
            "import_id": import_id,
            "tenant_id": imp["tenant_id"],
            "project_id": imp["project_id"],
            "valid_count": len(imp["valid_rows"]),
            "error_count": len(imp["errors"]),
            "valid_rows": imp["valid_rows"],
            "errors": imp["errors"],
            "confirmed": imp["confirmed"],
        }

    def confirm_charge_target_import(self, user, project_id, import_id):
        self._require(user, "import")
        imp = self.imports[import_id]
        if imp["tenant_id"] != user["tenant_id"] or imp["project_id"] != project_id:
            raise PermissionDenied("cross tenant import")
        if imp["confirmed"]:
            return {"created_count": 0, "skipped_count": len(imp["errors"])}
        created = 0
        for row in imp["valid_rows"]:
            self.create_charge_target(user, project_id, row["building"], row.get("unit", ""),
                                      row["room_number"], row.get("category", "居民"), row["area"])
            created += 1
        imp["confirmed"] = True
        self._log(user, project_id, 'import.confirm', 'import', import_id, {'created_count': created, 'skipped_count': len(imp['errors'])})
        return {"created_count": created, "skipped_count": len(imp["errors"])}

    def list_audit_logs(self, user, project_id):
        self._require(user, 'read')
        if not self._same_tenant_project(user, project_id):
            return []
        return [row for row in self.audit_logs if row['tenant_id'] == user['tenant_id'] and row['project_id'] == project_id]

    def create_backup_marker(self, user, project_id):
        if user['role_code'] != 'system_admin':
            raise PermissionDenied('backup requires admin')
        backup_id = f"backup-{self._id():06d}"
        record = {
            'backup_id': backup_id,
            'tenant_id': user['tenant_id'],
            'project_id': project_id,
            'status': 'created',
            'created_at': backup_id.replace('backup-', ''),
        }
        self.backup_records[backup_id] = record
        self._log(user, project_id, 'backup.create', 'backup', None, {'kind': 'manual', 'backup_id': backup_id})
        return {'backup_id': backup_id}

    def list_backup_records(self, user, project_id):
        if user['role_code'] != 'system_admin':
            raise PermissionDenied('backup requires admin')
        if not self._same_tenant_project(user, project_id):
            return []
        return [r for r in self.backup_records.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == project_id]

    def record_restore_drill(self, user, project_id, backup_id, scope):
        if user['role_code'] != 'system_admin':
            raise PermissionDenied('restore drill requires admin')
        if scope not in {'database', 'tenant-files', 'system-files'}:
            raise ValueError('invalid restore drill scope')
        drill_id = f"restore-drill-{self._id():06d}"
        drill = {'id': drill_id, 'tenant_id': user['tenant_id'], 'project_id': project_id, 'backup_id': backup_id, 'scope': scope, 'status': 'recorded'}
        self.restore_drills[drill_id] = drill
        self._log(user, project_id, 'restore.drill', 'restore_drill', None, {'backup_id': backup_id, 'scope': scope})
        return drill

    def reset_user_password(self, user, target_user_id, new_password):
        self._require(user, "manage_users")
        target = self.users[target_user_id]
        if target["tenant_id"] != user["tenant_id"]:
            raise PermissionDenied("cross tenant user")
        target['password_hash'] = f"hash:{new_password}"
        project_id = target.get('project_id') or self._default_project_id(target['tenant_id']) or target['tenant_id']
        self._log(user, project_id, 'user.password_reset', 'user', target_user_id, {'target_user_id': target_user_id})
        return {'user_id': target_user_id}
