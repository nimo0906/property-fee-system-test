#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Service-period selection helpers for tenant contract auto billing."""

from datetime import date, datetime, timedelta

from server.db import add_months


CYCLE_MONTHS = {'monthly': 1, 'quarterly': 3, 'semiannual': 6, 'yearly': 12}
AUTO_BILLING_LATE_GRACE_DAYS = 7


def as_date(value):
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def cycle_months(cycle):
    return CYCLE_MONTHS.get(str(cycle or '').strip(), 1)


def billing_period(start, end):
    first = f'{start.year}-{start.month:02d}'
    last = f'{end.year}-{end.month:02d}'
    return first if first == last else f'{first}~{last}'


def next_service_period(contract_start, contract_end, cycle, today=None):
    """Return the active or next contract period based on the contract cycle."""
    start = as_date(contract_start)
    end = as_date(contract_end)
    cursor = start
    current = as_date(today or date.today())
    service_end = add_months(cursor, cycle_months(cycle)) - timedelta(days=1)
    while service_end < current:
        cursor = add_months(cursor, cycle_months(cycle))
        service_end = add_months(cursor, cycle_months(cycle)) - timedelta(days=1)
    if service_end > end:
        return None
    return cursor, service_end, cursor - timedelta(days=1)


def period_exists(db, room_id, fee_id, service_start, service_end, period):
    return db.execute(
        """SELECT id FROM bills WHERE room_id=? AND fee_type_id=?
        AND ((service_start=? AND service_end=?)
          OR ((service_start IS NULL OR service_start='') AND billing_period=?))""",
        (room_id, fee_id, service_start.isoformat(), service_end.isoformat(), period)
    ).fetchone()


def next_bill_preview_period(db, room, fee, current, cutoff, schedule_cycle, cycle):
    service = next_service_period(room['contract_start'], room['contract_end'], schedule_cycle, current)
    if not service:
        return None
    cursor, _schedule_end, due_date = service
    stale_before = current - timedelta(days=AUTO_BILLING_LATE_GRACE_DAYS)
    while due_date < stale_before:
        cursor = add_months(cursor, cycle_months(schedule_cycle))
        due_date = cursor - timedelta(days=1)
    months = cycle_months(cycle)
    contract_end = as_date(room['contract_end'])
    last_existing = None
    while cursor <= cutoff:
        service_end = add_months(cursor, months) - timedelta(days=1)
        if service_end > contract_end:
            return last_existing
        period = billing_period(cursor, service_end)
        exists = period_exists(db, room['id'], fee['id'], cursor, service_end, period)
        candidate = (cursor, service_end, due_date, period, exists)
        if not exists:
            return candidate
        last_existing = candidate
        cursor = add_months(cursor, cycle_months(schedule_cycle))
        due_date = cursor - timedelta(days=1)
    return last_existing
