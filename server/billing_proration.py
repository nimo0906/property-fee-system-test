#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Date-range proration helpers for manual billing."""

from datetime import datetime, timedelta

from server.db import add_months


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
    inclusive_end = end + timedelta(days=1)
    full_months = 0
    while add_months(start, full_months + 1) <= inclusive_end:
        full_months += 1
    anchor = add_months(start, full_months)
    if anchor == inclusive_end:
        return float(full_months) or 1.0
    next_anchor = add_months(anchor, 1)
    cycle_days = max(1, (next_anchor - anchor).days)
    tail_days = max(0, (inclusive_end - anchor).days)
    total = full_months + tail_days / cycle_days
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
