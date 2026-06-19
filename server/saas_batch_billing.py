#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch bill generation helpers for SaaS billing."""

from server.saas_fee_rules import calculate_bill_amount


def target_matches_category(target, category):
    return not category or target.get('category') == category


def bill_key(tenant_id, project_id, period, target_id, fee_type_id):
    return f"SaaS-{tenant_id}-{project_id}-{period}-{target_id}-{fee_type_id}"


def build_batch_bill_rows(targets, fee, tenant_id, project_id, period, service_start, service_end, category=''):
    rows = []
    for target in targets:
        if not target_matches_category(target, category):
            continue
        rows.append({
            'tenant_id': tenant_id,
            'project_id': project_id,
            'target_id': target['id'],
            'fee_type_id': fee['id'],
            'bill_number': bill_key(tenant_id, project_id, period, target['id'], fee['id']),
            'billing_period': period,
            'service_start': service_start,
            'service_end': service_end,
            'amount': calculate_bill_amount(target, fee, service_start, service_end),
        })
    return rows
