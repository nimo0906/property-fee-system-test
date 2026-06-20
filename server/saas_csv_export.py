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
    headers = ['receipt_number', 'bill_number', 'billing_period', 'building', 'unit', 'room_number', 'shop_name', 'tenant_name', 'owner_name', 'amount_paid', 'method', 'paid_amount', 'unpaid_amount']
    return headers, [{key: item.get(key, '') for key in headers} for item in items]


def report_breakdown_export_rows(breakdown):
    headers = ['group_type', 'name', 'bill_count', 'bill_amount_total', 'payment_amount_total', 'unpaid_amount_total', 'collection_rate']
    group_map = [
        ('building', breakdown.get('by_building', [])),
        ('unit', breakdown.get('by_unit', [])),
        ('fee_type', breakdown.get('by_fee_type', [])),
        ('category', breakdown.get('by_category', [])),
    ]
    rows = []
    for group_type, items in group_map:
        for item in items:
            rows.append({
                'group_type': group_type,
                'name': item.get('name', ''),
                'bill_count': item.get('bill_count', 0),
                'bill_amount_total': item.get('bill_amount_total', 0.0),
                'payment_amount_total': item.get('payment_amount_total', 0.0),
                'unpaid_amount_total': item.get('unpaid_amount_total', 0.0),
                'collection_rate': item.get('collection_rate', '0.00%'),
            })
    return headers, rows
