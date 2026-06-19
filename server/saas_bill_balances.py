#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill balance helpers for SaaS billing."""


def attach_bill_balances(bills, paid_by_bill):
    rows = []
    for bill in bills:
        item = dict(bill)
        paid = round(float(paid_by_bill.get(int(item.get('id') or 0), 0) or 0), 2)
        amount = round(float(item.get('amount') or 0), 2)
        item['paid_amount'] = paid
        item['unpaid_amount'] = round(max(amount - paid, 0), 2)
        rows.append(item)
    return rows


def service_paid_by_bill(payments, tenant_id, project_id):
    result = {}
    for payment in payments:
        if int(payment.get('tenant_id')) != int(tenant_id) or int(payment.get('project_id')) != int(project_id):
            continue
        bill_id = int(payment.get('bill_id') or 0)
        result[bill_id] = result.get(bill_id, 0) + float(payment.get('amount_paid') or 0)
    return result
