#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill generation — grouped by fee type category."""

from server.db import get_db, get_period, is_period_closed, h, m, qs, date_to_period, period_to_date, add_months
from server.base import BaseHandler
from server.billing_engine import calculate_bill_amount, fee_applies_to_category, fee_applies_to_room
from server.backups import create_db_backup
from datetime import datetime, date, timedelta


def _cycle_month_count(cycle):
    return {'monthly': 1, 'quarterly': 3, 'semiannual': 6}.get(str(cycle or '').strip(), 1)


def _calc_month_count(start_str, end_str):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        ed = datetime.strptime(end_str, '%Y-%m-%d').date()
    except Exception:
        return 1
    if ed <= sd:
        return 1
    if sd.day == 1 and ed.day == 1:
        return max(1, (ed.year - sd.year) * 12 + ed.month - sd.month + 1)
    days = (ed - sd).days
    return max(1, (days + 15) // 30)


def _period_label(start_str, end_str):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        ed = datetime.strptime(end_str, '%Y-%m-%d').date()
        if sd.year == ed.year and sd.month == ed.month:
            return f"{sd.year}-{sd.month:02d}"
        return f"{sd.year}-{sd.month:02d}~{ed.year}-{ed.month:02d}"
    except Exception:
        return get_period()


def _month_end(start_str, months):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        return (add_months(sd, max(1, int(months or 1))) - timedelta(days=1)).isoformat()
    except Exception:
        return start_str


def _room_active_in_date_range(room, start_str, end_str):
    try:
        period_start = datetime.strptime(start_str, '%Y-%m-%d').date()
        period_end = datetime.strptime(end_str, '%Y-%m-%d').date()
    except Exception:
        return True
    start = room['contract_start'] if 'contract_start' in room.keys() else None
    end = room['contract_end'] if 'contract_end' in room.keys() else None
    try:
        if start and datetime.strptime(start[:10], '%Y-%m-%d').date() > period_end:
            return False
        if end and datetime.strptime(end[:10], '%Y-%m-%d').date() < period_start:
            return False
    except Exception:
        return True
    return True


def _resolve_generation_period(data):
    start = qs(data, 'period_start', '').strip()
    end = qs(data, 'period_end', '').strip()
    raw_period = qs(data, 'period', '').strip()
    if raw_period and not start and not end:
        start = period_to_date(date_to_period(raw_period))
        try:
            y, mo = [int(x) for x in start[:7].split('-')]
            end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
        except Exception:
            end = start
    if not start:
        start = period_to_date(get_period())
    if not end:
        try:
            y, mo = [int(x) for x in start[:7].split('-')]
            end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
        except Exception:
            end = start
    if end < start:
        start, end = end, start
    return start, end, _period_label(start, end), _calc_month_count(start, end)


def _room_billing_months(room, fallback_months=1):
    try:
        if room['unit'] == '商场' and room['category'] in ('商户', '商业'):
            cycle_months = _cycle_month_count(room['payment_cycle'])
            return cycle_months if cycle_months > 1 else max(1, int(fallback_months or 1))
    except Exception:
        pass
    return max(1, int(fallback_months or 1))


def _cycle_period_label(period, months):
    months = max(1, int(months or 1))
    if months == 1:
        return period
    try:
        y, mo = [int(x) for x in period[:7].split('-')]
        end = add_months(__import__('datetime').date(y, mo, 1), months - 1)
        return f"{y}-{mo:02d}~{end.year}-{end.month:02d}"
    except Exception:
        return period


def _cycle_due_date(period, fallback_due):
    if '~' not in period:
        return fallback_due
    try:
        y, mo = [int(x) for x in period.split('~')[-1].split('-')]
        return (add_months(__import__('datetime').date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
    except Exception:
        return fallback_due

__all__ = [name for name in globals() if not name.startswith('__')]
