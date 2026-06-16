#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Electronic invoice management."""

from server.db import get_db, get_period, h, m, qs, date_to_period, period_to_date, add_months
from server.billing_periods import append_period_filter, append_natural_date_range_filter
from server.invoice_requests import InvoiceRequestError, InvoiceRequestService
from server.base import BaseHandler
from datetime import date, datetime, timedelta
from urllib.parse import urlencode


def _rmb_upper(amount):
    nums = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
    int_units = ['', '拾', '佰', '仟', '万', '拾', '佰', '仟', '亿']
    try:
        cents = int(round(float(amount) * 100))
    except Exception:
        cents = 0
    if cents <= 0:
        return '零元整'
    yuan, cents = divmod(cents, 100)
    text = ''
    zero = False
    digits = str(yuan)
    for idx, ch in enumerate(digits):
        n = int(ch)
        unit = int_units[len(digits) - idx - 1]
        if n == 0:
            zero = True
            if unit in ('万', '亿') and not text.endswith(unit):
                text += unit
            continue
        if zero and text and not text.endswith(('万', '亿')):
            text += '零'
        text += nums[n] + unit
        zero = False
    text = text.rstrip('零') + '元'
    jiao, fen = divmod(cents, 10)
    if jiao:
        text += nums[jiao] + '角'
    if fen:
        text += nums[fen] + '分'
    return text if cents else text + '整'

__all__ = [name for name in globals() if not name.startswith('__')]
