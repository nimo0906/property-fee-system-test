#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee rule calculation helpers for SaaS billing."""

VALID_BILLING_MODES = {"area", "fixed"}


def normalize_billing_mode(value):
    return value if value in VALID_BILLING_MODES else "area"


def calculate_bill_amount(target, fee):
    mode = normalize_billing_mode(fee.get("billing_mode"))
    unit_price = float(fee.get("unit_price") or 0)
    if mode == "fixed":
        return round(unit_price, 2)
    return round(float(target.get("area") or 0) * unit_price, 2)
