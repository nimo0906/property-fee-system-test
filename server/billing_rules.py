#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central fee scope rules for billing entry points."""

PROPERTY_FEE_NAMES = {
    '物业费(居民)', '物业费(商户)', '电梯费', '二次供水运行费',
    '水费(非居民)', '水费(特行)', '公摊能耗费', '生活垃圾费',
}
COMMERCIAL_FEE_NAMES = {
    '物业费(商业)', '电费(商业)', '水费(商业)', '垃圾清运费',
    '装修管理费', '装修押金', '泄水费', '空调能源费', '空调费(商业)',
}
OTHER_FEE_NAMES = {'垃圾清运费', '水费(非居民)', '水费(特行)', '停车费', '临时收费'}
WATER_FEE_NAMES = {'水费(非居民)', '水费(特行)'}
CONTRACT_ARCHIVE_FEE_NAMES = {'合同租金', '合同物业费', '合同押金'}


def fee_name(fee):
    return (fee.get('name') if isinstance(fee, dict) else fee['name']) or ''


def fee_sort_order(fee):
    try:
        value = fee.get('sort_order') if isinstance(fee, dict) else fee['sort_order']
    except Exception:
        value = 0
    return int(value or 0)


def fee_in_scope(fee, scope):
    name = fee_name(fee)
    sort_order = fee_sort_order(fee)
    if name in CONTRACT_ARCHIVE_FEE_NAMES:
        return False
    if sort_order == 29:
        return scope == 'property'
    if sort_order >= 50:
        return scope == 'other'
    if scope == 'property':
        return (
            name in PROPERTY_FEE_NAMES
            or ((sort_order == 0 or 1 <= sort_order < 30) and name not in COMMERCIAL_FEE_NAMES and name not in OTHER_FEE_NAMES)
        )
    if scope == 'commercial':
        return name in COMMERCIAL_FEE_NAMES or name in WATER_FEE_NAMES or (30 <= sort_order < 50 and name not in PROPERTY_FEE_NAMES)
    if scope == 'other':
        return name in OTHER_FEE_NAMES or sort_order >= 50
    return False
