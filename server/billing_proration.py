#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Date-range proration helpers for manual billing."""

from calendar import monthrange
from datetime import date, datetime, timedelta


def parse_date(value):
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def prorated_month_factor(start_value, end_value):
    start = parse_date(start_value)
    end = parse_date(end_value)
    if not start or not end:
        return 1.0
    if end < start:
        start, end = end, start
    total = 0.0
    cur = date(start.year, start.month, 1)
    while cur <= end:
        days_in_month = monthrange(cur.year, cur.month)[1]
        month_start = cur
        month_end = date(cur.year, cur.month, days_in_month)
        seg_start = max(start, month_start)
        seg_end = min(end, month_end)
        if seg_start <= seg_end:
            if seg_start == month_start and seg_end == month_end:
                total += 1.0
            else:
                total += ((seg_end - seg_start).days + 1) / days_in_month
        cur = month_end + timedelta(days=1)
    return round(total, 6) or 1.0


def factor_label(factor):
    if abs(float(factor or 1) - round(float(factor or 1))) < 0.000001:
        return f"{int(round(float(factor or 1)))}个月"
    return f"{float(factor):.4f}".rstrip('0').rstrip('.') + "个月"


def is_one_time_fee(fee_type):
    try:
        cycle = fee_type.get('billing_cycle') if isinstance(fee_type, dict) else fee_type['billing_cycle']
    except Exception:
        cycle = ''
    return str(cycle or '').strip() in ('once', 'one_time', 'fixed_once')
