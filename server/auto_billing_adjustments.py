#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Editable auto-billing confirmation helpers."""

from datetime import datetime

from server.db import h, m, qs


def adjustments_from_form(data, keys):
    out = {}
    for key in keys:
        out[key] = {
            'amount': qs(data, f'amount__{key}'),
            'due_date': qs(data, f'due_date__{key}'),
        }
    return out


def safe_amount(value, fallback):
    try:
        amount = round(float(value), 2)
        return amount if amount > 0 else float(fallback)
    except (TypeError, ValueError):
        return float(fallback)


def safe_due_date(value, fallback):
    try:
        datetime.strptime(str(value), '%Y-%m-%d')
        return str(value)
    except (TypeError, ValueError):
        return fallback


def confirm_edit_row(x):
    disabled = '' if x['can_generate'] else ' disabled'
    return f'''<tr><td>{h(x.get('customer_name_snapshot') or x['tenant_name'])}</td><td>{h(x['room_name'])}</td><td>{h(x['fee_name'])}</td>
    <td>{h(x['service_start'])} 至 {h(x['service_end'])}</td>
    <td><input type="date" class="form-control form-control-sm" name="due_date__{h(x['item_key'])}" value="{h(x['due_date'])}"{disabled}></td>
    <td class="text-end"><input type="number" class="form-control form-control-sm text-end" name="amount__{h(x['item_key'])}" value="{m(x['amount'])}" min="0.01" step="0.01"{disabled}></td>
    <td>{'将生成，可修改' if x['can_generate'] else '已存在，跳过'}</td></tr>'''
