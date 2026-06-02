#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central billing period helpers for single-month and range periods."""

from server.db import date_to_period, get_period


def _month_range(start, end):
    try:
        sy, sm = [int(x) for x in start.split('-', 1)]
        ey, em = [int(x) for x in end.split('-', 1)]
    except Exception:
        return [start]
    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append(f'{y:04d}-{m:02d}')
        m += 1
        if m > 12:
            y += 1
            m = 1
    return months[:60]


def normalize_period(value):
    text = str(value or '').strip()
    if '~' in text:
        left, right = text.split('~', 1)
        start = date_to_period(left)
        end = date_to_period(right)
        return f'{start}~{end}' if end != get_period() or right.strip() else start
    return date_to_period(text or get_period())


def period_start_month(value):
    return normalize_period(value).split('~', 1)[0]


def period_filter_clause(value, column='billing_period'):
    period = normalize_period(value)
    if '~' in period:
        start, end = period.split('~', 1)
        months = _month_range(start, end)
        single_placeholders = ','.join('?' * len(months))
        return (
            f'({column}=? OR {column} IN ({single_placeholders}) OR '
            f'(instr({column}, "~")>0 AND substr({column},1,7)<=? AND substr({column},9,7)>=?))'
        ), [period] + months + [end, start]
    return (
        f'({column}=? OR (instr({column}, "~")>0 AND substr({column},1,7)<=? AND substr({column},9,7)>=?))'
    ), [period, period, period]


def append_period_filter(sql, params, value, column='billing_period'):
    clause, clause_params = period_filter_clause(value, column)
    return sql + ' AND ' + clause, list(params) + clause_params
