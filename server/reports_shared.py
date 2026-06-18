#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reports, statistics, and exports."""

import csv
import io
from datetime import date, timedelta

import openpyxl
import openpyxl.styles

from server.base import BaseHandler
from server.db import add_months, get_db, get_period, h, m, qs, date_to_period, period_to_date
from server.billing_periods import period_filter_clause, natural_date_range_filter_clause
from server.dashboard_v2 import get_enterprise_dashboard_metrics
from server.dashboard_analysis import render_enterprise_analysis
from server.enterprise_analysis_export import build_enterprise_analysis_xlsx


def _report_target_label(row):
    if row['commercial_space_id']:
        return f"商场-{row['space_no'] or ''}"
    return f"{row['building'] or ''}-{row['unit'] or ''}-{row['room_number'] or ''}"


def _report_customer_name(row):
    owner = row['owner_name'] if 'owner_name' in row.keys() else ''
    tenant = row['tenant'] if 'tenant' in row.keys() else ''
    return row['space_merchant'] or row['space_shop'] or owner or tenant or '未知'


def _report_charge_customer_name(row):
    owner = row['owner_name'] if 'owner_name' in row.keys() else ''
    tenant = row['tenant'] if 'tenant' in row.keys() else ''
    return row['space_merchant'] or row['space_shop'] or tenant or owner or '未知'


def _stable_income_bucket(row):
    fee_name = row['fee_name'] or ''
    unit = row['unit'] or ''
    building = row['building'] or ''
    category = row['category'] if 'category' in row.keys() else ''
    is_commercial = bool(row['commercial_space_id']) or category in ('商户', '商业') or unit == '商场' or building == '商场'
    is_water = '水费' in fee_name or '电费' in fee_name or '水电' in fee_name
    if is_commercial and is_water:
        return '商业水电收入'
    if is_commercial:
        if '租金' in fee_name:
            return '商业租金收入'
        if '物业费' in fee_name:
            return '商业物业费收入'
        return '商业综合收入'
    return '住宅水电收入' if is_water else '住宅物业收入'

def _stable_income_breakdown(rows):
    buckets = {
        '住宅物业收入': {'amount': 0.0, 'paid': 0.0, 'count': 0},
        '住宅水电收入': {'amount': 0.0, 'paid': 0.0, 'count': 0},
        '商业租金收入': {'amount': 0.0, 'paid': 0.0, 'count': 0},
        '商业物业费收入': {'amount': 0.0, 'paid': 0.0, 'count': 0},
        '商业综合收入': {'amount': 0.0, 'paid': 0.0, 'count': 0},
        '商业水电收入': {'amount': 0.0, 'paid': 0.0, 'count': 0},
    }
    for row in rows:
        name = _stable_income_bucket(row)
        if name not in buckets:
            buckets[name] = {'amount': 0.0, 'paid': 0.0, 'count': 0}
        buckets[name]['amount'] += float(row['amount'] or 0)
        buckets[name]['paid'] += float(row['paid'] or 0)
        buckets[name]['count'] += 1
    return buckets

__all__ = [name for name in globals() if not name.startswith('__')]
