#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enterprise dashboard metrics for B tower + mall commercial-complex v2."""

from datetime import date

from server.db import get_db


def _money(value):
    return round(float(value or 0), 2)


def get_enterprise_dashboard_metrics(period, today=None):
    today = today or date.today()
    db = get_db()
    row = db.execute(
        """SELECT COALESCE(SUM(b.amount),0) due,
                  COALESCE((SELECT SUM(p.amount_paid)
                            FROM payments p JOIN bills pb ON p.bill_id=pb.id
                            WHERE pb.billing_period=?),0) paid
           FROM bills b WHERE b.billing_period=?""",
        (period, period),
    ).fetchone()
    segment_rows = db.execute(
        """SELECT CASE WHEN r.building='B座' THEN 'B座'
                       WHEN r.building='商场' OR r.unit='商场' THEN '商场'
                       ELSE '其他' END segment,
                  COALESCE(SUM(b.amount),0) due,
                  COALESCE(SUM((SELECT COALESCE(SUM(p.amount_paid),0)
                                FROM payments p WHERE p.bill_id=b.id)),0) paid,
                  COUNT(b.id) bill_count
           FROM bills b JOIN rooms r ON b.room_id=r.id
           WHERE b.billing_period=?
           GROUP BY segment""",
        (period,),
    ).fetchall()
    unpaid_bills = db.execute(
        "SELECT COUNT(*) FROM bills WHERE billing_period=? AND status IN('unpaid','overdue','partial')",
        (period,),
    ).fetchone()[0]
    expiring_contracts = db.execute(
        """SELECT COUNT(*) FROM merchant_contracts
           WHERE status='active' AND end_date BETWEEN ? AND date(?, '+30 days')""",
        (today.isoformat(), today.isoformat()),
    ).fetchone()[0]
    db.close()
    total_due = _money(row["due"])
    total_paid = _money(row["paid"])
    return {
        "period": period,
        "total_due": total_due,
        "total_paid": total_paid,
        "unpaid_amount": _money(total_due - total_paid),
        "collection_rate": round(total_paid / total_due * 100, 1) if total_due else 0,
        "segments": {
            r["segment"]: {
                "due": _money(r["due"]),
                "paid": _money(r["paid"]),
                "bill_count": int(r["bill_count"] or 0),
            }
            for r in segment_rows
        },
        "risk_counts": {
            "unpaid_bills": int(unpaid_bills or 0),
            "contracts_expiring_30d": int(expiring_contracts or 0),
        },
    }
