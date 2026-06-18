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



def attach_billing_methods(cls):
    cls.generate_bill = generate_bill
    cls.list_bills = list_bills
    cls.approve_bill = approve_bill
    cls.record_payment = record_payment
    cls.report = report
    return cls
