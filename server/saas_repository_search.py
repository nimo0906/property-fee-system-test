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
            b.charge_target_id,b.fee_type_id,t.building,t.unit,t.room_number,t.category,t.shop_name,t.tenant_name,o.name owner_name,o.phone owner_phone,f.name fee_name
            FROM bills b JOIN charge_targets t ON b.charge_target_id=t.id
            LEFT JOIN owners o ON t.owner_id=o.id AND t.tenant_id=o.tenant_id AND t.project_id=o.project_id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id AND b.tenant_id=f.tenant_id AND b.project_id=f.project_id
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
            rows = [r for r in rows if keyword in " ".join(str(r.get(k, "")) for k in ["bill_number", "billing_period", "status", "building", "unit", "room_number", "shop_name", "tenant_name", "owner_name", "owner_phone"]).lower()]
        return self._paged(rows, page, page_size)

def search_payments(self, tenant_id, project_id, keyword="", period=None, page=1, page_size=20):
        self._require_project_scope(tenant_id, project_id)
        sql = """SELECT p.id,p.tenant_id,p.project_id,p.receipt_number,p.amount_paid,p.method,p.bill_id,
            b.bill_number,b.billing_period,b.service_start,b.service_end,b.amount bill_amount,
            f.name fee_name,
            t.building,t.unit,t.room_number,t.category,t.shop_name,t.tenant_name,o.name owner_name
            FROM payments p JOIN bills b ON p.bill_id=b.id
            JOIN charge_targets t ON b.charge_target_id=t.id
            JOIN fee_types f ON b.fee_type_id=f.id AND b.tenant_id=f.tenant_id AND b.project_id=f.project_id
            LEFT JOIN owners o ON t.owner_id=o.id AND t.tenant_id=o.tenant_id AND t.project_id=o.project_id
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
            paid_map = {int(r['bill_id']): float(r['paid'] or 0) for r in paid_rows}
            for row in rows:
                bill_id = int(row.get('bill_id') or 0)
                current_paid = round(paid_map.get(bill_id, 0), 2)
                paid_after = conn.execute(text("""SELECT COALESCE(SUM(amount_paid),0) FROM payments
                    WHERE tenant_id=:tenant_id AND project_id=:project_id AND bill_id=:bill_id AND id<=:payment_id"""),
                    {"tenant_id": tenant_id, "project_id": project_id, "bill_id": bill_id, "payment_id": row.get('id')}).scalar_one()
                row['current_paid_amount'] = current_paid
                row['paid_amount'] = round(float(paid_after or 0), 2)
                row['unpaid_amount'] = round(max(float(row.get('bill_amount') or 0) - float(paid_after or 0), 0), 2)
        keyword = str(keyword or "").lower()
        if keyword:
            rows = [r for r in rows if keyword in " ".join(str(r.get(k, "")) for k in ["receipt_number", "bill_number", "method", "billing_period", "shop_name", "tenant_name"]).lower()]
        return self._paged(rows, page, page_size)



def attach_repository_search(cls):
    cls._paged = _paged
    cls.search_bills = search_bills
    cls.search_payments = search_payments
    return cls
