#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment processing, records, and quick billing."""

from server.db import get_db, get_period, calc_bill_late_fee, is_period_closed, h, m, qs, date_to_period, period_to_date, add_months
from server.billing_periods import append_period_filter, append_natural_date_range_filter
from server.base import BaseHandler
from datetime import datetime, date, timedelta
import urllib.parse, csv, io, re
from server.billing_engine import calculate_bill_amount, fee_applies_to_category, fee_applies_to_room
from server.print_helper import print_page
from server.backups import create_db_backup
from server.services import Actor, PaymentService, ServiceError


def _calc_month_count(start_str, end_str):
    """计算日期区间包含的月数。按天数÷30四舍五入。
    eg: 2026-01-28 ~ 2026-05-28 = 120天÷30 = 4个月
        2026-01-01 ~ 2026-12-31 = 364天÷30 ≈ 12个月
    """
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        ed = datetime.strptime(end_str, '%Y-%m-%d').date()
    except:
        return 1
    if ed <= sd:
        return 1
    if sd.day == 1 and ed.day == 1:
        return max(1, (ed.year - sd.year) * 12 + ed.month - sd.month + 1)
    days = (ed - sd).days
    return max(1, (days + 15) // 30)


def _period_label(start_str, end_str):
    """生成账期标签。单月: 2026-06, 多月: 2026-05~2026-08"""
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        ed = datetime.strptime(end_str, '%Y-%m-%d').date()
        if sd.year == ed.year and sd.month == ed.month:
            return f"{sd.year}-{sd.month:02d}"
        return f"{sd.year}-{sd.month:02d}~{ed.year}-{ed.month:02d}"
    except:
        return get_period()


def _cycle_month_count(cycle):
    return {'monthly': 1, 'quarterly': 3, 'semiannual': 6}.get(str(cycle or '').strip(), 0)


def _is_mall_commercial_room(room):
    try:
        return room['unit'] == '商场' and room['category'] in ('商户', '商业')
    except Exception:
        return False


def _room_billing_months(room, fallback_months):
    try:
        cycle = room['payment_cycle'] if 'payment_cycle' in room.keys() else ''
    except Exception:
        cycle = ''
    if _is_mall_commercial_room(room):
        cycle_months = _cycle_month_count(cycle)
        return cycle_months if cycle_months > 1 else max(1, int(fallback_months or 1))
    return max(1, int(fallback_months or 1))


def _cycle_period_label(start_str, months):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
    except Exception:
        return get_period()
    months = max(1, int(months or 1))
    if months == 1:
        return f"{sd.year}-{sd.month:02d}"
    ed = add_months(sd.replace(day=1), months - 1)
    return f"{sd.year}-{sd.month:02d}~{ed.year}-{ed.month:02d}"


def _cycle_due_date(start_str, months, fallback_end):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        return (add_months(sd, max(1, int(months or 1))) - timedelta(days=1)).isoformat()
    except Exception:
        return fallback_end


def _bill_target_label(row):
    if row['commercial_space_id']:
        return f"商场-{row['space_no'] or ''}"
    return f"{row['building'] or ''}-{row['unit'] or ''}-{row['room_number'] or ''}"


def _bill_customer_label(row):
    return row['space_merchant'] or row['space_shop'] or row['tenant_name'] or row['owner_name'] or '未知'


def _extract_ids(data, key):
    raw = data.get(key, []) if data else []
    if isinstance(raw, str):
        raw = [raw]
    ids = []
    for item in raw:
        for part in str(item).split(','):
            cleaned = part.strip().strip('[]').strip().strip("'\"")
            if cleaned.isdigit():
                ids.append(cleaned)
    return ids

__all__ = [name for name in globals() if not name.startswith('__')]
