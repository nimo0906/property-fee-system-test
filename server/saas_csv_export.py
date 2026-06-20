#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSV export helpers for SaaS backoffice."""

import csv
import io


def csv_content(headers, rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(key, '') for key in headers])
    return out.getvalue()


def bill_export_rows(items):
    headers = ['bill_number', 'billing_period', 'building', 'unit', 'room_number', 'shop_name', 'tenant_name', 'owner_name', 'fee_name', 'amount', 'paid_amount', 'unpaid_amount', 'status']
    return headers, [{key: item.get(key, '') for key in headers} for item in items]


def payment_export_rows(items):
    headers = ['receipt_number', 'bill_number', 'billing_period', 'building', 'unit', 'room_number', 'owner_name', 'amount_paid', 'method']
    return headers, [{key: item.get(key, '') for key in headers} for item in items]
