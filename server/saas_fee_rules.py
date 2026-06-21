#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee rule calculation helpers for SaaS billing."""

from datetime import date, timedelta
import calendar

VALID_BILLING_MODES = {"area", "fixed"}


def normalize_billing_mode(value):
    return value if value in VALID_BILLING_MODES else "area"


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def service_months(service_start=None, service_end=None):
    start = _parse_date(service_start)
    end = _parse_date(service_end)
    if not start or not end or end < start:
        return 1
    total = 0.0
    current = start
    while current <= end:
        days_in_month = calendar.monthrange(current.year, current.month)[1]
        month_end = date(current.year, current.month, days_in_month)
        segment_end = min(month_end, end)
        if current.day == 1 and segment_end.day >= min(28, days_in_month):
            total += 1
        else:
            total += ((segment_end - current).days + 1) / days_in_month
        current = segment_end + timedelta(days=1)
    return max(total, 1 / calendar.monthrange(start.year, start.month)[1])


def effective_unit_price(target, fee):
    if normalize_billing_mode(fee.get("billing_mode")) == "fixed":
        return float(fee.get("unit_price") or 0)
    override = target.get("unit_price_override")
    if override not in (None, ""):
        return float(override)
    return float(fee.get("unit_price") or 0)


def fee_applies_to_target(fee, target, selected_category=''):
    fee_name = str(fee.get('name') or '')
    category = str(target.get('category') or '居民')
    if '(商业)' in fee_name:
        return category in {'商户', '商业'}
    if '(商户)' in fee_name:
        return category == '商户'
    if '(居民)' in fee_name:
        return category == '居民'
    if selected_category == '商业':
        return category in {'商户', '商业'}
    return not selected_category or category == selected_category

def calculate_bill_amount(target, fee, service_start=None, service_end=None):
    mode = normalize_billing_mode(fee.get("billing_mode"))
    unit_price = effective_unit_price(target, fee)
    amount = unit_price if mode == "fixed" else float(target.get("area") or 0) * unit_price
    return round(amount * service_months(service_start, service_end), 2)
