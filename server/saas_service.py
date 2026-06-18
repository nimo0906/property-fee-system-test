#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-memory SaaS backoffice domain service for first cloud slice tests."""


class PermissionDenied(Exception):
    pass


ROLE_PERMISSIONS = {
    "system_admin": {"read", "write", "manage_users", "backup"},
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

    def create_tenant(self, name):
        tid = self._id()
        self.tenants[tid] = {"id": tid, "name": name}
        return tid

    def create_project(self, tenant_id, name):
        pid = self._id()
        self.projects[pid] = {"id": pid, "tenant_id": tenant_id, "name": name}
        return pid

    def create_user(self, tenant_id, username, role_code):
        uid = self._id()
        user = {"id": uid, "tenant_id": tenant_id, "username": username, "role_code": role_code}
        self.users[uid] = user
        return user

    def create_charge_target(self, user, project_id, building, unit, room_number, category, area):
        self._require(user, "write")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        tid = self._id()
        target = {"id": tid, "tenant_id": user["tenant_id"], "project_id": project_id,
                  "building": building, "unit": unit, "room_number": room_number,
                  "category": category, "area": float(area)}
        self.targets[tid] = target
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
        return fee

    def generate_bill(self, user, project_id, target, fee, period, service_start, service_end):
        self._require(user, "billing")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        amount = round(float(target["area"]) * float(fee["unit_price"]), 2)
        bid = self._id()
        bill = {"id": bid, "tenant_id": user["tenant_id"], "project_id": project_id,
                "charge_target_id": target["id"], "fee_type_id": fee["id"],
                "billing_period": period, "service_start": service_start, "service_end": service_end,
                "bill_number": f"BILL-{bid:06d}", "amount": amount, "status": "unpaid"}
        self.bills[bid] = bill
        return bill

    def record_payment(self, user, bill_id, amount, method, idempotency_key=None):
        self._require(user, "payment")
        bill = self.bills[bill_id]
        if bill["tenant_id"] != user["tenant_id"]:
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
        valid, errors = [], []
        for idx, row in enumerate(rows, start=1):
            try:
                area = float(row.get("area") or 0)
                if area <= 0:
                    raise ValueError("area must be positive")
                valid.append({**row, "area": area})
            except Exception:
                errors.append({"row": idx, "error": "面积必须是数字且大于0"})
        iid = self._id()
        self.imports[iid] = {"id": iid, "tenant_id": user["tenant_id"], "project_id": project_id,
                             "valid_rows": valid, "errors": errors, "confirmed": False}
        return {"import_id": iid, "valid_count": len(valid), "error_count": len(errors), "errors": errors}

    def confirm_charge_target_import(self, user, project_id, import_id):
        self._require(user, "import")
        imp = self.imports[import_id]
        if imp["confirmed"]:
            return {"created_count": 0, "skipped_count": len(imp["errors"])}
        created = 0
        for row in imp["valid_rows"]:
            self.create_charge_target(user, project_id, row["building"], row.get("unit", ""),
                                      row["room_number"], row.get("category", "居民"), row["area"])
            created += 1
        imp["confirmed"] = True
        return {"created_count": created, "skipped_count": len(imp["errors"])}
