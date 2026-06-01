#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared billing calculation rules."""

from server.db import get_fee_type_rate, calc_elevator_fee


def fee_applies_to_category(fee_name, room_category):
    rcat = room_category or '居民'
    if '(居民)' in fee_name and rcat != '居民':
        return False
    if '(商户)' in fee_name and rcat != '商户':
        return False
    if '(非居民)' in fee_name and rcat == '居民':
        return False
    if '(特行)' in fee_name and rcat == '居民':
        return False
    if '(商业)' in fee_name and rcat not in ('商户', '商业'):
        return False
    return True


def fee_applies_to_room(fee_name, room):
    rcat = room['category'] or '居民'
    water_rate = '非居民'
    try:
        if 'water_rate_type' in room.keys():
            water_rate = room['water_rate_type'] or '非居民'
    except Exception:
        water_rate = '非居民'
    if '(非居民)' in fee_name:
        return rcat != '居民' and water_rate == '非居民'
    if '(特行)' in fee_name:
        return rcat != '居民' and water_rate == '特行'
    return fee_applies_to_category(fee_name, rcat)


def calculate_bill_amount(db, room, fee_type, period, months=1, custom_amount=None):
    """Return amount details for one room and one active fee type."""
    if custom_amount not in (None, ''):
        custom = float(custom_amount)
        if custom > 0:
            amount = round(custom, 2)
            return {'amount': amount, 'monthly_amount': amount, 'formula': '自定义'}

    fid = fee_type['id']
    fee_name = fee_type['name'] or ''
    rcat = room['category'] or '居民'
    method = fee_type['calc_method']
    monthly = 0
    formula = '-'

    if method == 'area':
        rate = _room_custom_rate(room) if _uses_room_property_rate(fee_name, room) else get_fee_type_rate(fid, rcat)
        monthly = round(float(room['area']) * float(rate), 2)
        formula = f"面积{float(room['area']):.2f}×单价{float(rate):.2f}" if _uses_room_property_rate(fee_name, room) else f"{room['area']}×{rate}"
    elif method == 'floor':
        monthly = calc_elevator_fee(room['floor'], room['area'])
        formula = f"楼层{room['floor']}阶梯×{room['area']}"
    elif method == 'meter':
        cp = period.split('~')[0].replace('-', '')
        mr = db.execute(
            "SELECT consumption FROM meter_readings WHERE room_id=? AND fee_type_id=? AND period=? AND status='confirmed' LIMIT 1",
            (room['id'], fid, cp)
        ).fetchone()
        rate = get_fee_type_rate(fid, rcat)
        consumption = mr[0] if mr else 0
        monthly = round(consumption * rate, 2)
        formula = f"{consumption}×{rate}"
    elif method == 'fixed':
        monthly = fee_type['unit_price']
        formula = f"固定{fee_type['unit_price']}"
    elif method == 'household':
        monthly = fee_type['unit_price']
        formula = f"按户{fee_type['unit_price']}"

    month_count = max(1, int(months or 1))
    amount = round(float(monthly or 0) * month_count, 2)
    if month_count > 1 and formula != '自定义':
        formula = f"{formula}×{month_count}个月"
    return {'amount': amount, 'monthly_amount': monthly, 'formula': formula}


def _room_custom_rate(room):
    try:
        return float(room['custom_rate'] or 0)
    except Exception:
        return 0


def _uses_room_property_rate(fee_name, room):
    if '物业费' not in fee_name:
        return False
    try:
        has_rate = 'custom_rate' in room.keys() and _room_custom_rate(room) > 0
    except Exception:
        has_rate = False
    return has_rate
