#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Search helpers for SaaS repository."""

from sqlalchemy import text

from server.saas_bill_balances import attach_bill_balances


def _paged(self, rows, page, page_size):
        page = max(int(page or 1), 1)
        page_size = max(min(int(page_size or 20), 100), 1)
        start = (page - 1) * page_size
        return {"total": len(rows), "page": page, "page_size": page_size, "items": rows[start:start + page_size]}

def search_bills(self, tenant_id, project_id, keyword="", period=None, status=None, page=1, page_size=20):
        self._require_project_scope(tenant_id, project_id)
        sql = """SELECT b.id,b.tenant_id,b.project_id,b.bill_number,b.billing_period,b.amount,b.status,
            t.building,t.unit,t.room_number FROM bills b JOIN charge_targets t ON b.charge_target_id=t.id
            WHERE b.tenant_id=:tenant_id AND b.project_id=:project_id"""
        params = {"tenant_id": tenant_id, "project_id": project_id}
        if period:
            sql += " AND b.billing_period=:period"
            params["period"] = period
        if status:
            sql += " AND b.status=:status"
            params["status"] = status
        sql += " ORDER BY b.id"
        with self.engine.begin() as conn:
            rows = [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
            paid_rows = conn.execute(text("""SELECT bill_id,COALESCE(SUM(amount_paid),0) paid FROM payments
                WHERE tenant_id=:tenant_id AND project_id=:project_id GROUP BY bill_id"""),
                {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
        rows = attach_bill_balances(rows, {int(r['bill_id']): float(r['paid'] or 0) for r in paid_rows})
        keyword = str(keyword or "").lower()
        if keyword:
            rows = [r for r in rows if keyword in " ".join(str(r.get(k, "")) for k in ["bill_number", "billing_period", "status", "building", "unit", "room_number"]).lower()]
        return self._paged(rows, page, page_size)

def search_payments(self, tenant_id, project_id, keyword="", period=None, page=1, page_size=20):
        self._require_project_scope(tenant_id, project_id)
        sql = """SELECT p.id,p.tenant_id,p.project_id,p.receipt_number,p.amount_paid,p.method,
            b.bill_number,b.billing_period FROM payments p JOIN bills b ON p.bill_id=b.id
            WHERE p.tenant_id=:tenant_id AND p.project_id=:project_id"""
        params = {"tenant_id": tenant_id, "project_id": project_id}
        if period:
            sql += " AND b.billing_period=:period"
            params["period"] = period
        sql += " ORDER BY p.id"
        with self.engine.begin() as conn:
            rows = [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
            paid_rows = conn.execute(text("""SELECT bill_id,COALESCE(SUM(amount_paid),0) paid FROM payments
                WHERE tenant_id=:tenant_id AND project_id=:project_id GROUP BY bill_id"""),
                {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
        rows = attach_bill_balances(rows, {int(r['bill_id']): float(r['paid'] or 0) for r in paid_rows})
        keyword = str(keyword or "").lower()
        if keyword:
            rows = [r for r in rows if keyword in " ".join(str(r.get(k, "")) for k in ["receipt_number", "bill_number", "method", "billing_period"]).lower()]
        return self._paged(rows, page, page_size)



def attach_repository_search(cls):
    cls._paged = _paged
    cls.search_bills = search_bills
    cls.search_payments = search_payments
    return cls
