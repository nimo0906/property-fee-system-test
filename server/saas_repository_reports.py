#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report aggregation repository methods."""

from sqlalchemy import text


def _money(value):
    return round(float(value or 0), 2)


def _summary_rows(rows):
    items = []
    for row in rows:
        due = _money(row["due"])
        paid = _money(row["paid"])
        items.append({
            "name": row["name"] or "未填写",
            "bill_count": int(row["bill_count"] or 0),
            "bill_amount_total": due,
            "payment_amount_total": paid,
            "unpaid_amount_total": round(due - paid, 2),
            "collection_rate": f"{(paid / due * 100):.2f}%" if due else "0.00%",
            "arrears_rate": f"{((due - paid) / due * 100):.2f}%" if due else "0.00%",
        })
    return items


def attach_report_repository_methods(cls):
    def report_breakdown(self, tenant_id, project_id, period):
        self._require_project_scope(tenant_id, project_id)
        params = {"tenant_id": tenant_id, "project_id": project_id, "period": period}
        payment_subquery = """SELECT bill_id,COALESCE(SUM(amount_paid),0) paid FROM payments
            WHERE tenant_id=:tenant_id AND project_id=:project_id GROUP BY bill_id"""
        with self.engine.begin() as conn:
            by_building = conn.execute(text(f"""SELECT ct.building name,COUNT(*) bill_count,COALESCE(SUM(b.amount),0) due,COALESCE(SUM(paid_by_bill.paid),0) paid
                FROM bills b JOIN charge_targets ct ON b.charge_target_id=ct.id AND b.tenant_id=ct.tenant_id AND b.project_id=ct.project_id
                LEFT JOIN ({payment_subquery}) paid_by_bill ON paid_by_bill.bill_id=b.id
                WHERE b.tenant_id=:tenant_id AND b.project_id=:project_id AND b.billing_period=:period
                GROUP BY ct.building ORDER BY MIN(b.id)"""), params).mappings().all()
            by_unit = conn.execute(text(f"""SELECT ct.unit name,COUNT(*) bill_count,COALESCE(SUM(b.amount),0) due,COALESCE(SUM(paid_by_bill.paid),0) paid
                FROM bills b JOIN charge_targets ct ON b.charge_target_id=ct.id AND b.tenant_id=ct.tenant_id AND b.project_id=ct.project_id
                LEFT JOIN ({payment_subquery}) paid_by_bill ON paid_by_bill.bill_id=b.id
                WHERE b.tenant_id=:tenant_id AND b.project_id=:project_id AND b.billing_period=:period
                GROUP BY ct.unit ORDER BY MIN(b.id)"""), params).mappings().all()
            by_fee_type = conn.execute(text(f"""SELECT ft.name name,COUNT(*) bill_count,COALESCE(SUM(b.amount),0) due,COALESCE(SUM(paid_by_bill.paid),0) paid
                FROM bills b JOIN fee_types ft ON b.fee_type_id=ft.id AND b.tenant_id=ft.tenant_id AND b.project_id=ft.project_id
                LEFT JOIN ({payment_subquery}) paid_by_bill ON paid_by_bill.bill_id=b.id
                WHERE b.tenant_id=:tenant_id AND b.project_id=:project_id AND b.billing_period=:period
                GROUP BY ft.name ORDER BY MIN(b.id)"""), params).mappings().all()
            by_category = conn.execute(text(f"""SELECT ct.category name,COUNT(*) bill_count,COALESCE(SUM(b.amount),0) due,COALESCE(SUM(paid_by_bill.paid),0) paid
                FROM bills b JOIN charge_targets ct ON b.charge_target_id=ct.id AND b.tenant_id=ct.tenant_id AND b.project_id=ct.project_id
                LEFT JOIN ({payment_subquery}) paid_by_bill ON paid_by_bill.bill_id=b.id
                WHERE b.tenant_id=:tenant_id AND b.project_id=:project_id AND b.billing_period=:period
                GROUP BY ct.category ORDER BY MIN(b.id)"""), params).mappings().all()
        return {"by_building": _summary_rows(by_building), "by_unit": _summary_rows(by_unit), "by_fee_type": _summary_rows(by_fee_type), "by_category": _summary_rows(by_category)}

    cls.report_breakdown = report_breakdown
