#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared billing calculation rules."""

from server.db import get_fee_type_rate, calc_elevator_fee
from server.billing_proration import prorated_month_factor, factor_label, is_one_time_fee


def fee_applies_to_category(fee_name, room_category):
    rcat = room_category or '居民'
    if '(居民)' in fee_name and rcat != '居民':
        return False
    if '(商户)' in fee_name and rcat != '商户':
        return False
    if '(商业)' in fee_name and rcat not in ('商户', '商业'):
        return False
    return True


def fee_applies_to_room(fee_name, room):
    rcat = room['category'] or '居民'
    unit = (room['unit'] or '').strip() if 'unit' in room.keys() else ''
    if '(商业)' in fee_name and unit != '商场':
        return False
    water_rate = '非居民'
    try:
        if 'water_rate_type' in room.keys():
            water_rate = room['water_rate_type'] or '非居民'
    except Exception:
        water_rate = '非居民'
    if '(非居民)' in fee_name:
        return water_rate == '非居民'
    if '(特行)' in fee_name:
        return water_rate == '特行'
    return fee_applies_to_category(fee_name, rcat)


def calculate_bill_amount(db, room, fee_type, period, months=1, custom_amount=None, period_start=None, period_end=None):
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
        periods = _period_compact_months(period)
        placeholders = ','.join('?' for _ in periods)
        commercial_space_id = _room_value(room, 'commercial_space_id')
        if commercial_space_id:
            mr = db.execute(
                f"""SELECT COALESCE(SUM(consumption),0) FROM meter_readings
                    WHERE commercial_space_id=? AND fee_type_id=? AND period IN ({placeholders}) AND status='confirmed'""",
                (commercial_space_id, fid, *periods)
            ).fetchone()
        else:
            mr = db.execute(
                f"""SELECT COALESCE(SUM(consumption),0) FROM meter_readings
                    WHERE room_id=? AND fee_type_id=? AND period IN ({placeholders}) AND status='confirmed'""",
                (room['id'], fid, *periods)
            ).fetchone()
        rate = get_fee_type_rate(fid, rcat)
        consumption = mr[0] if mr else 0
        monthly = round(consumption * rate, 2)
        formula = f"用量合计{_fmt_num(consumption)}×{rate}"
    elif method == 'fixed':
        monthly = fee_type['unit_price']
        formula = f"固定{fee_type['unit_price']}"
    elif method == 'household':
        monthly = fee_type['unit_price']
        formula = f"按户{fee_type['unit_price']}"

    month_count = 1 if method == 'meter' else max(1, int(months or 1))
    factor = float(month_count)
    if method == 'meter' or is_one_time_fee(fee_type):
        factor = 1.0
    elif period_start and period_end:
        factor = prorated_month_factor(period_start, period_end)
    amount = round(float(monthly or 0) * factor, 2)
    if formula != '自定义' and method != 'meter':
        if is_one_time_fee(fee_type):
            pass
        elif factor != 1:
            formula = f"{formula}×{factor_label(factor)}"
        elif period_start and period_end:
            formula = f"{formula}×1个月"
    return {'amount': amount, 'monthly_amount': monthly, 'formula': formula}


def _room_value(room, key, default=None):
    try:
        if hasattr(room, 'keys') and key not in room.keys():
            return default
        return room[key]
    except Exception:
        return default


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


def _period_compact_months(period):
    """Return compact YYYYMM months covered by a billing period label."""
    text = str(period or '').strip()
    parts = [p.strip() for p in text.split('~') if p.strip()]
    start = _parse_period_month(parts[0] if parts else '')
    end = _parse_period_month(parts[-1] if len(parts) > 1 else (parts[0] if parts else ''))
    if not start:
        return ['']
    if not end:
        end = start
    sy, sm = start
    ey, em = end
    if (ey, em) < (sy, sm):
        ey, em = sy, sm
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(f'{y}{m:02d}')
        m += 1
        if m > 12:
            y += 1
            m = 1
    return out


def _parse_period_month(value):
    text = str(value or '').strip()
    if len(text) >= 7 and text[4] == '-':
        try:
            return int(text[:4]), int(text[5:7])
        except ValueError:
            return None
    if len(text) >= 6 and text[:6].isdigit():
        return int(text[:4]), int(text[4:6])
    return None


def _fmt_num(value):
    try:
        num = float(value or 0)
    except Exception:
        return '0'
    if num.is_integer():
        return str(int(num))
    return f'{num:.2f}'.rstrip('0').rstrip('.')
