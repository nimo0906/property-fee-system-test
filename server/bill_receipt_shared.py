#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-module receipt (print + CSV)."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs, add_months, date_to_period, period_to_date
from server.billing_periods import append_natural_date_range_filter
from server.base import BaseHandler
from server.print_helper import print_page, print_header_row
from datetime import datetime, date, timedelta
import urllib.parse, csv, io
from server.billing_proration import prorated_month_factor

from server.print_helper import print_page, print_header_row

def _receipt_service_period(bill):
    if bill['source'] == 'auto_contract' and bill['service_start'] and bill['service_end']:
        return f'<br><small>自动出账服务期 {h(bill["service_start"])} 至 {h(bill["service_end"])}</small>'
    return ''


def _receipt_period_label(bill):
    start = (bill['service_start'] or '').strip()
    end = (bill['service_end'] or '').strip()
    if start and end:
        return f'{start} 至 {end}'
    return bill['billing_period'] or ''


def _receipt_group_period_label(bills, fallback=''):
    starts = []
    ends = []
    for bill in bills:
        start = (bill['service_start'] or '').strip()
        end = (bill['service_end'] or '').strip()
        if not start or not end:
            return fallback
        starts.append(start)
        ends.append(end)
    if starts and ends:
        return f'{min(starts)} 至 {max(ends)}'
    return fallback


def receipt_object_label(row):
    if row['commercial_space_id']:
        return f"{h(row['building'] or '商场')}\\{h(row['room_number'] or row['space_no'] or '')}"
    return f"{h(row['building'] or '')}\\{h(row['unit'] or '')}\\{h(row['room_number'] or '')}"


def receipt_object_list(rows):
    seen = []
    for row in rows:
        label = receipt_object_label(row)
        if label not in seen:
            seen.append(label)
    return '、'.join(seen)


def receipt_number(value):
    try:
        num = float(value or 0)
    except Exception:
        return '0'
    if num.is_integer():
        return str(int(num))
    return f'{num:.2f}'.rstrip('0').rstrip('.')


def receipt_months(row):
    start = (row['service_start'] or '').strip()
    end = (row['service_end'] or '').strip()
    if start and end:
        return max(1, int(round(prorated_month_factor(start, end))))
    period = row['billing_period'] or ''
    if '~' not in period:
        return 1
    left, right = period.split('~', 1)
    try:
        ly, lm = [int(x) for x in left[:7].split('-')]
        ry, rm = [int(x) for x in right[:7].split('-')]
        return max(1, (ry - ly) * 12 + rm - lm + 1)
    except Exception:
        return 1


def receipt_usage(row):
    months = receipt_months(row)
    cm = row['calc_method']
    if cm in ('area', 'floor'):
        base = receipt_number(row['area'] or 0)
        return f'{base}×{months}' if months > 1 else base
    if cm == 'household':
        return f'1×{months}' if months > 1 else '1'
    if cm == 'meter':
        return '按抄表'
    return '1'


def receipt_customer_name(row):
    if row['space_merchant']:
        return row['space_merchant']
    if row['space_shop']:
        return row['space_shop']
    if 'oname' in row.keys():
        return row['oname'] or ''
    return row['owner_name'] or ''


def print_style_table(title, rows, print_type, back_url, payment_mode=False):
    first = rows[0]
    customer = receipt_customer_name(first)
    total_due = total_discount = total_waiver = total_paid = total_rem = 0
    body = ''
    for row in rows:
        paid = float(row['amount_paid'] if payment_mode else row['paid'] or 0)
        amount = float(row['amount'] or 0)
        waiver = float(row['waiver_amount'] or 0)
        discount = 0.0
        due_before_discount = amount + waiver + discount
        rem = max(0.0, due_before_discount - waiver - discount - paid)
        body += f'''<tr><td>{h(row['ft'] or '-')}</td><td>{h(_receipt_period_label(row) or '-')}</td>
            <td>{h(receipt_usage(row))}</td><td>1</td><td class="amt">{h(str(row['unit_price'] or ''))}</td>
            <td class="amt">{m(due_before_discount)}</td><td class="amt">{m(discount)}</td>
            <td class="amt">{m(waiver)}</td><td class="amt">{m(paid)}</td><td class="amt">{m(rem)}</td></tr>'''
        total_due += due_before_discount; total_discount += discount; total_waiver += waiver; total_paid += paid; total_rem += rem
    area = f"{receipt_number(first['area'])}m2"
    content = f'''<h1>陕西金莎国际物业管理有限公司</h1><h2 style="margin-top:0">{h(title)}</h2>
    <div style="text-align:center;margin-bottom:6pt;font-weight:bold">打印类型：{h(print_type)}</div>
    <table class="header-info receipt-head"><tr><td><strong>套户编号：</strong>{receipt_object_list(rows)}</td><td><strong>客户名称：</strong>{h(customer)}</td><td><strong>建筑面积：</strong>{area}</td></tr>
    <tr><td><strong>打印类型：</strong>{h(print_type)}</td><td><strong>流水号：</strong>{datetime.now().strftime('JS%Y%m%d%H%M%S')}</td><td><strong>打印时间：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr></table>
    <table class="detail receipt-new-detail"><thead><tr><th style="width:18%">收费项目</th><th style="width:18%">费用区间</th><th style="width:12%">使用量</th><th style="width:7%">系数</th><th style="width:8%">单价</th><th class="amt" style="width:10%">应收</th><th class="amt" style="width:9%">优惠</th><th class="amt" style="width:9%">减免</th><th class="amt" style="width:9%">缴费</th><th class="amt" style="width:9%">欠费</th></tr></thead>
    <tbody>{body}<tr class="total-row"><td colspan="5" style="text-align:center"><strong>缴费合计</strong></td><td class="amt"><strong>{m(total_due)}</strong></td><td class="amt"><strong>{m(total_discount)}</strong></td><td class="amt"><strong>{m(total_waiver)}</strong></td><td class="amt"><strong>{m(total_paid)}</strong></td><td class="amt"><strong>{m(total_rem)}</strong></td></tr></tbody></table>
    <table class="header-info receipt-foot"><tr><td><strong>收款对象：</strong>{receipt_object_list(rows)}</td><td><strong>客户名称：</strong>{h(customer)}</td><td><strong>打印类型：</strong>{h(print_type)}</td></tr></table>'''
    return print_page(title, content, back_url=back_url, body_class='receipt-print')


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
