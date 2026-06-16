#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scope helpers for contract auto billing."""

from server.billing_rules import fee_in_scope


CONTRACT_ARCHIVE_FEE_NAMES = {'合同租金', '合同物业费', '合同押金'}

SCOPE_OPTIONS = [
    ('all', '全部范围'),
    ('a', 'A座'),
    ('b', 'B座'),
    ('mall', '商场商户'),
]


def room_in_auto_scope(room, target_scope='all'):
    scope = str(target_scope or 'all').strip()
    if scope == 'all':
        return True
    unit = (room['unit'] or '').strip()
    building = (room['building'] or '').strip()
    category = (room['category'] or '').strip()
    if scope == 'a':
        return unit == 'A座' or building == 'A座'
    if scope == 'b':
        return unit == 'B座' or building == 'B座'
    if scope == 'mall':
        is_mall_space = unit == '商场' or building == '商场' or '商场' in unit or '商场' in building
        return is_mall_space and category in ('商户', '商业')
    return True


def grouped_auto_fees(fees):
    groups = [
        ('property', '物业收费项目', []),
        ('commercial', '商业收费项目', []),
        ('other', '其他收费项目', []),
    ]
    seen = set()
    daily_fees = [fee for fee in fees if (fee['name'] or '') not in CONTRACT_ARCHIVE_FEE_NAMES]
    for key, _label, bucket in groups:
        for fee in daily_fees:
            fid = int(fee['id'])
            if fid in seen:
                continue
            matched = fee_in_scope(fee, key) if key != 'other' else False
            if matched:
                bucket.append(fee)
                seen.add(fid)
    groups[-1][2].extend([fee for fee in daily_fees if int(fee['id']) not in seen])
    return groups
