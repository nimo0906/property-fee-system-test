#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enterprise dashboard metrics for generic commercial edition."""

from datetime import date

from server.alert_center import get_alert_center
from server.db import add_months, get_db, period_to_date


def _money(value):
    return round(float(value or 0), 2)


def _prev_periods(period, months=3):
    current = date.fromisoformat(period_to_date(period))
    return [add_months(current, offset).strftime("%Y-%m") for offset in range(-(months - 1), 1)]


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
        """SELECT CASE WHEN b.commercial_space_id IS NOT NULL THEN '商业空间'
                       WHEN r.category IN('商户','商业') THEN '商业对象'
                       WHEN COALESCE(r.building,'')<>'' THEN r.building
                       ELSE '其他' END segment,
                  COALESCE(SUM(b.amount),0) due,
                  COALESCE(SUM((SELECT COALESCE(SUM(p.amount_paid),0)
                                FROM payments p WHERE p.bill_id=b.id)),0) paid,
                  COUNT(b.id) bill_count
           FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
           WHERE b.billing_period=?
           GROUP BY segment""",
        (period,),
    ).fetchall()
    periods = _prev_periods(period)
    arrears_rows = db.execute(
        """SELECT b.billing_period period,
                  COALESCE(SUM(b.amount),0) due,
                  COALESCE(SUM((SELECT COALESCE(SUM(p.amount_paid),0)
                                FROM payments p WHERE p.bill_id=b.id)),0) paid
           FROM bills b
           WHERE b.billing_period IN ({})
           GROUP BY b.billing_period""".format(",".join("?" for _ in periods)),
        tuple(periods),
    ).fetchall()
    merchant_rows = db.execute(
        """SELECT COALESCE(NULLIF(s.shop_name,''),NULLIF(s.merchant_name,''),NULLIF(c.merchant_name,''),
                            NULLIF(r.shop_name,''),NULLIF(o.name,''),r.room_number,s.space_no) merchant,
                  COALESCE(SUM(b.amount),0) due,
                  COALESCE(SUM((SELECT COALESCE(SUM(p.amount_paid),0)
                                FROM payments p WHERE p.bill_id=b.id)),0) paid,
                  COUNT(b.id) bill_count
           FROM bills b
           LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
           LEFT JOIN merchant_contracts c ON b.source='merchant_contract' AND b.source_ref=CAST(c.id AS TEXT)
           LEFT JOIN rooms r ON b.room_id=r.id
           LEFT JOIN owners o ON b.owner_id=o.id
           WHERE b.billing_period=? AND (b.commercial_space_id IS NOT NULL OR r.category IN('商户','商业'))
           GROUP BY merchant
           ORDER BY due DESC, merchant
           LIMIT 5""",
        (period,),
    ).fetchall()
    fee_rows = db.execute(
        """SELECT f.name fee_name,
                  COALESCE(SUM(b.amount),0) due,
                  COUNT(b.id) bill_count
           FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
           WHERE b.billing_period=?
           GROUP BY f.id
           ORDER BY due DESC, f.sort_order
           LIMIT 6""",
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
    expired_contracts = db.execute(
        "SELECT COUNT(*) FROM merchant_contracts WHERE status='active' AND end_date < ?",
        (today.isoformat(),),
    ).fetchone()[0]
    contract_alerts = get_alert_center(period, today=today)
    db.close()
    total_due = _money(row["due"])
    total_paid = _money(row["paid"])
    segment_data = {}
    for r in segment_rows:
        due = _money(r["due"])
        paid = _money(r["paid"])
        segment_data[r["segment"]] = {
            "due": due,
            "paid": paid,
            "unpaid": _money(due - paid),
            "collection_rate": round(paid / due * 100, 1) if due else 0,
            "bill_count": int(r["bill_count"] or 0),
        }
    arrears_by_period = {r["period"]: r for r in arrears_rows}
    arrears_trend = []
    for month in periods:
        item = arrears_by_period.get(month) or {}
        due = _money(item.get("due") if hasattr(item, "get") else item["due"])
        paid = _money(item.get("paid") if hasattr(item, "get") else item["paid"])
        arrears_trend.append({"period": month, "due": due, "paid": paid, "unpaid": _money(due - paid)})
    return {
        "period": period,
        "total_due": total_due,
        "total_paid": total_paid,
        "unpaid_amount": _money(total_due - total_paid),
        "collection_rate": round(total_paid / total_due * 100, 1) if total_due else 0,
        "segments": segment_data,
        "arrears_trend": arrears_trend,
        "merchant_contribution": [
            {
                "merchant": r["merchant"],
                "due": _money(r["due"]),
                "paid": _money(r["paid"]),
                "unpaid": _money(float(r["due"] or 0) - float(r["paid"] or 0)),
                "bill_count": int(r["bill_count"] or 0),
            }
            for r in merchant_rows
        ],
        "fee_structure": [
            {"fee_name": r["fee_name"], "due": _money(r["due"]), "bill_count": int(r["bill_count"] or 0)}
            for r in fee_rows
        ],
        "risk_counts": {
            "unpaid_bills": int(unpaid_bills or 0),
            "contracts_expiring_30d": int(expiring_contracts or 0),
            "expired_contracts": int(expired_contracts or 0),
            "contract_unpaid_bills": int(contract_alerts["summary"]["unpaid_contract_bills"] or 0),
        },
    }
