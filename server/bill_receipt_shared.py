#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-module receipt (print + CSV)."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs, add_months, date_to_period, period_to_date
from server.billing_periods import append_natural_date_range_filter
from server.base import BaseHandler
from server.print_helper import print_page, print_header_row
from datetime import datetime, date, timedelta
import urllib.parse, csv, io

from server.print_helper import print_page, print_header_row

def _receipt_service_period(bill):
    if bill['source'] == 'auto_contract' and bill['service_start'] and bill['service_end']:
        return f'<br><small>自动出账服务期 {h(bill["service_start"])} 至 {h(bill["service_end"])}</small>'
    return ''


def _month_range(period=''):
    p = date_to_period(period or get_period())
    start = period_to_date(p)
    try:
        y, mo = [int(x) for x in start[:7].split('-')]
        end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
    except Exception:
        end = start
    return start, end


def _receipt_date_range(q):
    start = qs(q, 'period_start', '').strip()
    end = qs(q, 'period_end', '').strip()
    legacy = qs(q, 'period', '').strip()
    if legacy and not start and not end:
        start, end = _month_range(legacy)
    return start, end

__all__ = [name for name in globals() if not name.startswith('__')]
