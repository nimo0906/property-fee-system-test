#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee types, tiers, late fee configuration."""

from server.db import get_db, get_period, get_fee_type_rate, h, m, price, qs
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


def fee_admin_group(row):
    """Fee Types admin grouping follows the operator-selected company bucket.

    Billing scopes still use billing_rules.fee_in_scope(); the fee maintenance
    page must not reassign a manually-added item just because its name matches
    a commercial template such as 装修押金 or 装修管理费.
    """
    sort_order = _to_int(row.get('sort_order') if isinstance(row, dict) else row['sort_order'], 0)
    if sort_order == 0 or 1 <= sort_order < 30:
        return 'property'
    if 30 <= sort_order < 50:
        return 'commercial'
    return 'other'


FEE_ADMIN_GROUP_NAMES = {
    'property': ['物业费(居民)', '物业费(商户)', '电梯费', '二次供水运行费', '公摊能耗费', '生活垃圾费'],
    'commercial': ['电费(商业)', '装修管理费', '装修押金', '泄水费', '空调能源费', '空调费(商业)'],
    'other': ['垃圾清运费', '水费(非居民)', '水费(特行)', '停车费', '临时收费'],
}


def fee_admin_display_rows(rows, group_key):
    rows_by_name = {r['name']: r for r in rows}
    ordered = []
    seen_ids = set()

    def add(row):
        if row['id'] in seen_ids:
            return
        ordered.append(row)
        seen_ids.add(row['id'])

    for name in FEE_ADMIN_GROUP_NAMES.get(group_key, []):
        if name in rows_by_name:
            add(rows_by_name[name])
    for row in rows:
        if fee_admin_group(row) == group_key:
            add(row)
    return ordered


def _infer_fee_group(row):
    for group in ('property', 'commercial', 'other'):
        if fee_in_scope(row, group):
            return group
    return fee_admin_group(row)

__all__ = [name for name in globals() if not name.startswith('__')]
