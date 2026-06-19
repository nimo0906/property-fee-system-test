#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee rule calculation helpers for SaaS billing."""

from datetime import date

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
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    return max(months, 1)


def effective_unit_price(target, fee):
    override = target.get("unit_price_override")
    if override not in (None, ""):
        return float(override)
    return float(fee.get("unit_price") or 0)


def calculate_bill_amount(target, fee, service_start=None, service_end=None):
    mode = normalize_billing_mode(fee.get("billing_mode"))
    unit_price = effective_unit_price(target, fee)
    amount = unit_price if mode == "fixed" else float(target.get("area") or 0) * unit_price
    return round(amount * service_months(service_start, service_end), 2)
