#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract pages for commercial-complex v2."""

from datetime import date

from server.base import BaseHandler
from server.contract_billing import (
    build_contract_billing_preview,
    confirm_contract_billing,
    create_merchant_contract,
    generate_contract_bills,
)
from server.db import get_db, h, m, n, qs


CYCLE_LABELS = {
    "monthly": "月付",
    "quarterly": "季付",
    "semiannual": "半年付",
    "yearly": "年付",
}


CONTRACT_STATUS_LABELS = {
    "active": "启用",
    "inactive": "停用",
    "expired": "到期",
}


def contract_status_label(status):
    return CONTRACT_STATUS_LABELS.get(str(status or "").strip(), status or "-")


def _cycle_options(selected="monthly"):
    return "".join(
        f'<option value="{h(code)}" {"selected" if code == selected else ""}>{h(label)}</option>'
        for code, label in CYCLE_LABELS.items()
    )


def _rent_mode_options(selected="fixed"):
    labels = [("fixed", "固定租金"), ("fixed_plus_turnover", "固定租金+销售额分成"),
              ("higher_of_fixed_or_turnover", "保底租金与销售额分成取高"), ("turnover_only", "纯销售额分成")]
    return "".join(f'<option value="{h(code)}" {"selected" if code == selected else ""}>{h(label)}</option>' for code, label in labels)


def _contract_billing_badges(row):
    bill_count = int(row["bill_count"] or 0)
    unpaid_count = int(row["unpaid_count"] or 0)
    if bill_count <= 0:
        return '<span class="badge status-neutral">未出账</span>'
    unpaid = f'<div class="small text-danger">欠费 {unpaid_count} 笔</div>' if unpaid_count else '<div class="small text-success">无欠费</div>'
    return f'<span class="badge status-info">已出账 {bill_count} 笔</span>{unpaid}'


def _contract_service_period(row):
    if row["service_start_min"] and row["service_end_max"]:
        return f'{h(row["service_start_min"])} 至 {h(row["service_end_max"])}'
    return '<span class="text-muted">待出账</span>'


def _contract_expiry_badge(end_date):
    try:
        days = (date.fromisoformat(str(end_date)[:10]) - date.today()).days
    except Exception:
        return '<span class="badge status-neutral">待核对</span>'
    if days < 0:
        return '<span class="badge bg-danger">已过期</span>'
    if days <= 30:
        return f'<span class="badge bg-warning text-dark">{days} 天后到期</span>'
    return '<span class="badge status-success">正常</span>'




def _rent_unit_price(monthly_total, area):
    area_value = float(area or 0)
    total_value = float(monthly_total or 0)
    if area_value <= 0:
        return total_value
    return total_value / area_value


def _rent_monthly_total_from_form(d):
    value = float(qs(d, "rent_amount") or 0)
    if qs(d, "space_no").strip() or qs(d, "target_kind") == "room":
        return value * float(qs(d, "area") or 0)
    return value


def _deposit_unit_price(total, area):
    return _rent_unit_price(total, area)


def _deposit_total_from_form(d):
    value = float(qs(d, "deposit_amount") or 0)
    if qs(d, "space_no").strip() or qs(d, "target_kind") == "room":
        return value * float(qs(d, "area") or 0)
    return value

def _space_id_from_contract_form(d):
    existing_id = qs(d, "commercial_space_id")
    if existing_id:
        return int(existing_id)
    space_no = qs(d, "space_no").strip()
    if not space_no:
        return None
    shop_name = qs(d, "shop_name") or qs(d, "merchant_name")
    merchant_name = qs(d, "merchant_name") or shop_name
    try:
        floor = int(float(qs(d, "floor") or 1))
    except ValueError:
        floor = 1
    try:
        area = float(qs(d, "area") or 0)
    except ValueError:
        area = 0
    db = get_db()
    row = db.execute("SELECT id FROM commercial_spaces WHERE space_no=?", (space_no,)).fetchone()
    if row:
        space_id = row["id"]
        db.execute(
            """UPDATE commercial_spaces
               SET floor=?,area=?,shop_name=?,merchant_name=?,business_type=?,water_rate_type=?,status=?,notes=?
               WHERE id=?""",
            (floor, area, shop_name, merchant_name, qs(d, "business_type"),
             qs(d, "water_rate_type") or "非居民", "active", qs(d, "space_notes") or qs(d, "notes"), space_id),
        )
    else:
        cur = db.execute(
            """INSERT INTO commercial_spaces(project_id,space_no,floor,area,shop_name,merchant_name,business_type,water_rate_type,status,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (1, space_no, floor, area, shop_name, merchant_name, qs(d, "business_type"),
             qs(d, "water_rate_type") or "非居民", "active", qs(d, "space_notes") or ""),
        )
        space_id = cur.lastrowid
    db.commit()
    db.close()
    return space_id




def _contract_matches_keyword(row, keyword):
    needle = str(keyword or '').strip().lower()
    if not needle:
        return True
    fields = [
        row['contract_no'], row['room_number'], row['building'], row['unit'], row['floor'],
        row['space_shop_name'], row['space_merchant_name'], row['merchant_name'], row['shop_name'],
        row['owner_name'], row['business_type'], row['water_rate_type'], row['status'],
    ]
    return any(needle in str(value or '').lower() for value in fields)

__all__ = [name for name in globals() if not name.startswith('__')]
