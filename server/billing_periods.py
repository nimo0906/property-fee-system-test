#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central billing period helpers for single-month and range periods."""

from server.db import date_to_period, get_period


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
        return f'{column}=?', [period]
    return f'({column}=? OR {column} LIKE ?)', [period, f'{period}~%']


def append_period_filter(sql, params, value, column='billing_period'):
    clause, clause_params = period_filter_clause(value, column)
    return sql + ' AND ' + clause, list(params) + clause_params
