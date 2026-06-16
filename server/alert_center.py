#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Risk and alert center for commercial-complex v2."""

from datetime import date, timedelta

from server.db import add_months, get_db


def _rows_to_dicts(rows):
    return [dict(row) for row in rows]


def get_alert_center(period, today=None):
    today = today or date.today()
    today_text = today.isoformat()
    period_start = f"{period}-01" if len(str(period or "")) == 7 else str(period or "")
    try:
        period_end = (add_months(date.fromisoformat(period_start), 1) - timedelta(days=1)).isoformat()
    except Exception:
        period_end = period_start
    db = get_db()
    expiring = db.execute(
        """SELECT c.id,c.contract_no,c.merchant_name,c.shop_name,c.end_date,
                  COALESCE(r.building,'空间档案') building,
                  COALESCE(r.room_number,s.space_no,'') room_number,
                  COALESCE(r.area,s.area,0) area
           FROM merchant_contracts c
           LEFT JOIN rooms r ON c.room_id=r.id
           LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
           WHERE c.status='active' AND c.end_date BETWEEN ? AND date(?, '+30 days')
           ORDER BY c.end_date,c.id LIMIT 20""",
        (today_text, today_text),
    ).fetchall()
    expired = db.execute(
        """SELECT c.id,c.contract_no,c.merchant_name,c.shop_name,c.end_date,
                  COALESCE(r.building,'空间档案') building,
                  COALESCE(r.room_number,s.space_no,'') room_number
           FROM merchant_contracts c
           LEFT JOIN rooms r ON c.room_id=r.id
           LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
           WHERE c.status='active' AND c.end_date < ?
           ORDER BY c.end_date,c.id LIMIT 20""",
        (today_text,),
    ).fetchall()
    unpaid_contract_bills = db.execute(
        """SELECT b.id,b.bill_number,b.amount,b.status,b.due_date,
                  f.name fee_name,c.contract_no,c.merchant_name,
                  COALESCE(r.building,'空间档案') building,
                  COALESCE(r.room_number,s.space_no,'') room_number
           FROM bills b
           JOIN fee_types f ON b.fee_type_id=f.id
           JOIN merchant_contracts c ON b.source='merchant_contract' AND b.source_ref=CAST(c.id AS TEXT)
           LEFT JOIN rooms r ON b.room_id=r.id
           LEFT JOIN commercial_spaces s ON COALESCE(b.commercial_space_id,c.commercial_space_id)=s.id
           WHERE b.status IN('unpaid','overdue','partial')
             AND (
               b.billing_period=?
               OR (b.service_start IS NOT NULL AND b.service_end IS NOT NULL
                   AND b.service_start<=? AND b.service_end>=?)
             )
           ORDER BY CASE b.status WHEN 'overdue' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END,b.due_date,b.id
           LIMIT 30""",
        (period, period_end, period_start),
    ).fetchall()
    zero_amount = db.execute(
        """SELECT b.id,b.bill_number,b.amount,b.status,f.name fee_name,
                  COALESCE(r.building,'空间档案') building,
                  COALESCE(r.room_number,s.space_no,'') room_number
           FROM bills b
           JOIN fee_types f ON b.fee_type_id=f.id
           LEFT JOIN rooms r ON b.room_id=r.id
           LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
           WHERE b.billing_period=? AND b.amount<=0
           ORDER BY b.id LIMIT 30""",
        (period,),
    ).fetchall()
    duplicate_rows = db.execute(
        """SELECT room_id,commercial_space_id,fee_type_id,billing_period,COUNT(*) cnt,COALESCE(SUM(amount),0) amount_total
           FROM bills WHERE billing_period=?
           GROUP BY room_id,commercial_space_id,fee_type_id,billing_period HAVING COUNT(*)>1
           ORDER BY cnt DESC LIMIT 20""",
        (period,),
    ).fetchall()
    db.close()
    summary = {
        "contracts_expiring_30d": len(expiring),
        "expired_contracts": len(expired),
        "unpaid_contract_bills": len(unpaid_contract_bills),
        "zero_amount_bills": len(zero_amount),
        "duplicate_bill_groups": len(duplicate_rows),
    }
    danger = summary["expired_contracts"] or summary["unpaid_contract_bills"] or summary["zero_amount_bills"]
    warning = summary["contracts_expiring_30d"] or summary["duplicate_bill_groups"]
    severity = "danger" if danger else "warning" if warning else "success"
    return {
        "period": period,
        "today": today_text,
        "severity": severity,
        "summary": summary,
        "expiring_contracts": _rows_to_dicts(expiring),
        "expired_contracts": _rows_to_dicts(expired),
        "unpaid_contract_bills": _rows_to_dicts(unpaid_contract_bills),
        "zero_amount_bills": _rows_to_dicts(zero_amount),
        "duplicate_bill_groups": _rows_to_dicts(duplicate_rows),
    }
