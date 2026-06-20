#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch bill generation helpers for SaaS billing."""

from calendar import monthrange
from datetime import date

from server.saas_fee_rules import calculate_bill_amount


def target_matches_category(target, category):
    return not category or target.get('category') == category


def target_matches_scope(target, building='', unit=''):
    if building and target.get('building') != building:
        return False
    if unit and target.get('unit') != unit:
        return False
    return True


CYCLE_MONTHS = {'monthly': 1, 'quarterly': 3, 'semiannual': 6, 'yearly': 12}


def bill_key(tenant_id, project_id, period, target_id, fee_type_id):
    return f"SaaS-{tenant_id}-{project_id}-{period}-{target_id}-{fee_type_id}"


def service_end_for_cycle(service_start, payment_cycle):
    months = CYCLE_MONTHS.get(str(payment_cycle or '').strip().lower(), 1)
    start = date.fromisoformat(str(service_start)[:10])
    month_index = start.month - 1 + months - 1
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = monthrange(year, month)[1]
    return date(year, month, day).isoformat()


def _effective_service_end(target, service_start, service_end, use_payment_cycle=False):
    if use_payment_cycle and service_start:
        return service_end_for_cycle(service_start, target.get('payment_cycle'))
    return service_end


def build_batch_bill_rows(targets, fee, tenant_id, project_id, period, service_start, service_end, category='', building='', unit='', use_payment_cycle=False):
    rows = []
    for target in targets:
        if not target_matches_category(target, category):
            continue
        if not target_matches_scope(target, building, unit):
            continue
        target_service_end = _effective_service_end(target, service_start, service_end, use_payment_cycle)
        rows.append({
            'tenant_id': tenant_id,
            'project_id': project_id,
            'target_id': target['id'],
            'fee_type_id': fee['id'],
            'bill_number': bill_key(tenant_id, project_id, period, target['id'], fee['id']),
            'billing_period': period,
            'service_start': service_start,
            'service_end': target_service_end,
            'amount': calculate_bill_amount(target, fee, service_start, target_service_end),
        })
    return rows
