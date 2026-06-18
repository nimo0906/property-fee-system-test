#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Billing methods mixed into SaaS backoffice service."""

from server.saas_service import PermissionDenied


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
                "bill_number": f"BILL-{bid:06d}", "amount": amount, "status": "pending_review"}
        self.bills[bid] = bill
        self._log(user, project_id, 'bill.generate', 'bill', bid, {'bill_number': bill['bill_number'], 'amount': amount, 'billing_period': period})
        return bill

def list_bills(self, user, project_id, period=None, status=None):
        self._require(user, "read")
        if not self._same_tenant_project(user, project_id):
            return []
        rows = [b for b in self.bills.values() if b["tenant_id"] == user["tenant_id"] and b["project_id"] == project_id]
        if period:
            rows = [b for b in rows if b["billing_period"] == period]
        if status:
            rows = [b for b in rows if b["status"] == status]
        return sorted(rows, key=lambda b: b["id"])

def approve_bill(self, user, project_id, bill_id):
        self._require(user, "billing")
        bill = self.bills[bill_id]
        if bill["tenant_id"] != user["tenant_id"] or bill["project_id"] != project_id:
            raise PermissionDenied("cross tenant bill")
        if bill["status"] == "pending_review":
            bill["status"] = "unpaid"
            self._log(user, project_id, 'bill.approve', 'bill', bill_id, {'bill_number': bill['bill_number']})
        return bill

def record_payment(self, user, bill_id, amount, method, idempotency_key=None):
        self._require(user, "payment")
        bill = self.bills[bill_id]
        if bill["tenant_id"] != user["tenant_id"] or bill["project_id"] != user["project_id"]:
            raise PermissionDenied("cross tenant bill")
        if bill["status"] == "pending_review":
            raise PermissionDenied("bill pending review")
        key = (user["tenant_id"], idempotency_key) if idempotency_key else None
        if key and key in self.payment_keys:
            return self.payments[self.payment_keys[key]]
        pid = self._id()
        receipt_number = f"RCPT-{user['tenant_id']}-{bill['project_id']}-{pid:06d}"
        payment = {"id": pid, "tenant_id": user["tenant_id"], "project_id": bill["project_id"],
                   "bill_id": bill_id, "amount_paid": float(amount), "method": method,
                   "idempotency_key": idempotency_key, "receipt_number": receipt_number}
        self.payments[pid] = payment
        if key:
            self.payment_keys[key] = pid
        paid = sum(p["amount_paid"] for p in self.payments.values() if p["bill_id"] == bill_id)
        bill["status"] = "paid" if paid >= bill["amount"] else "partial"
        self._log(user, bill['project_id'], 'payment.record', 'payment', pid, {'bill_id': bill_id, 'amount_paid': float(amount), 'method': method, 'idempotency_key': idempotency_key, 'receipt_number': receipt_number})
        return payment

def _csv(lines):
        return "\n".join(",".join(str(v) for v in row) for row in lines) + "\n"

def export_bills(self, user, project_id, period=None, status=None):
        rows = [["bill_number", "billing_period", "amount", "status"]]
        for bill in self.list_bills(user, project_id, period, status):
            rows.append([bill["bill_number"], bill["billing_period"], bill["amount"], bill["status"]])
        return {"filename": f"bills-{period or 'all'}.csv", "content": _csv(rows)}

def export_payments(self, user, project_id, period=None):
        self._require(user, "read")
        bills = {b["id"]: b for b in self.list_bills(user, project_id, period, None)}
        rows = [["receipt_number", "bill_number", "amount_paid", "method"]]
        for payment in sorted(self.payments.values(), key=lambda p: p["id"]):
            bill = bills.get(payment["bill_id"])
            if bill and payment["tenant_id"] == user["tenant_id"] and payment["project_id"] == project_id:
                rows.append([payment.get("receipt_number", ""), bill["bill_number"], payment["amount_paid"], payment.get("method", "")])
        return {"filename": f"payments-{period or 'all'}.csv", "content": _csv(rows)}


def _paginate(rows, page, page_size):
        page = max(int(page or 1), 1)
        page_size = max(min(int(page_size or 20), 100), 1)
        start = (page - 1) * page_size
        return {"total": len(rows), "page": page, "page_size": page_size, "items": rows[start:start + page_size]}

def search_bills(self, user, project_id, keyword="", period=None, status=None, page=1, page_size=20):
        rows = []
        keyword = str(keyword or "").lower()
        for bill in self.list_bills(user, project_id, period, status):
            target = self.targets.get(bill["charge_target_id"], {})
            item = {**bill, "building": target.get("building", ""), "unit": target.get("unit", ""), "room_number": target.get("room_number", "")}
            haystack = " ".join(str(item.get(k, "")) for k in ["bill_number", "billing_period", "status", "building", "unit", "room_number"]).lower()
            if not keyword or keyword in haystack:
                rows.append(item)
        return _paginate(rows, page, page_size)

def search_payments(self, user, project_id, keyword="", period=None, page=1, page_size=20):
        self._require(user, "read")
        bills = {b["id"]: b for b in self.list_bills(user, project_id, period, None)}
        keyword = str(keyword or "").lower()
        rows = []
        for payment in sorted(self.payments.values(), key=lambda p: p["id"]):
            bill = bills.get(payment["bill_id"])
            if not bill or payment["tenant_id"] != user["tenant_id"] or payment["project_id"] != project_id:
                continue
            item = {**payment, "bill_number": bill["bill_number"], "billing_period": bill["billing_period"]}
            haystack = " ".join(str(item.get(k, "")) for k in ["receipt_number", "bill_number", "method", "billing_period"]).lower()
            if not keyword or keyword in haystack:
                rows.append(item)
        return _paginate(rows, page, page_size)

def report(self, user, project_id, period):
        self._require(user, "read")
        bills = [b for b in self.bills.values() if b["tenant_id"] == user["tenant_id"] and b["project_id"] == project_id and b["billing_period"] == period]
        bill_ids = {b["id"] for b in bills}
        payments = [p for p in self.payments.values() if p["tenant_id"] == user["tenant_id"] and p["bill_id"] in bill_ids]
        due = round(sum(b["amount"] for b in bills), 2)
        paid = round(sum(p["amount_paid"] for p in payments), 2)
        return {"bill_count": len(bills), "bill_amount_total": due,
                "payment_amount_total": paid, "unpaid_amount_total": round(due - paid, 2)}



def attach_billing_methods(cls):
    cls.generate_bill = generate_bill
    cls.list_bills = list_bills
    cls.approve_bill = approve_bill
    cls.record_payment = record_payment
    cls.export_bills = export_bills
    cls.export_payments = export_payments
    cls.search_bills = search_bills
    cls.search_payments = search_payments
    cls.report = report
    return cls
