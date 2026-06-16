#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee types, tiers, late fee configuration."""

from server.db import get_db, get_period, get_fee_type_rate, h, m, qs
from server.base import BaseHandler
from server.billing_rules import fee_in_scope
import json


def _to_float(value, default=0.0):
    try:
        return float(value if str(value).strip() != '' else default)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(value if str(value).strip() != '' else default)
    except (TypeError, ValueError):
        return default


def _infer_fee_group(row):
    for group in ('property', 'commercial', 'other'):
        if fee_in_scope(row, group):
            return group
    return ''

__all__ = [name for name in globals() if not name.startswith('__')]
