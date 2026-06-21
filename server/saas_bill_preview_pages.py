#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch bill preview and confirm pages for SaaS backoffice."""

import urllib.parse

from server.saas_batch_billing import build_batch_bill_rows
from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _target_map(targets):
    return {int(target['id']): target for target in targets}


def _preview_items(rows, targets, existing_numbers):
    targets_by_id = _target_map(targets)
    create_items, skip_items, amount_total = [], [], 0.0
    for row in rows:
        target = targets_by_id.get(int(row.get('target_id') or 0), {})
        item = {
            'room_number': target.get('room_number', ''),
            'service_start': row.get('service_start'),
            'service_end': row.get('service_end'),
            'amount': row.get('amount'),
        }
        if row.get('bill_number') in existing_numbers:
            skip_items.append(item)
        else:
            create_items.append(item)
            amount_total = round(amount_total + float(row.get('amount') or 0), 2)
    return create_items, skip_items, amount_total


def _render_preview(user, create_items, skip_items, amount_total, form):
    create_rows = ''.join(
        f'<li>{_h(i["room_number"])} {_h(i["service_start"])}~{_h(i["service_end"])} {_h(i["amount"])}元</li>'
        for i in create_items
    ) or '<li>无新增账单</li>'
    skip_rows = ''.join(
        f'<li>{_h(i["room_number"])} 已存在账单，确认导入将跳过</li>'
        for i in skip_items
    ) or '<li>无重复账单</li>'
    hidden = ''.join(f'<input type="hidden" name="{_h(k)}" value="{_h(v)}">' for k, v in form.items())
    body = f'''
<section class="hero"><div><h1>批量出账预览</h1><div class="sub">预览不会写入账单；确认后才生成当前租户、当前项目范围内的新账单。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">预览结果</div><div class="card-b"><div class="badge">预计出账{len(create_items)}张</div> <div class="badge">跳过{len(skip_items)}张</div> <div class="badge">金额合计{_h(amount_total)}元</div><h3>将生成</h3><ul>{create_rows}</ul><h3>将跳过</h3><ul>{skip_rows}</ul><form method="post" action="/backoffice/bills/batch-generate-confirm">{hidden}<button class="primary">确认出账</button> <a class="ghost-link" href="/backoffice/bills">返回账单</a></form></div></section>'''
    return _page('批量出账预览', body)


def _context(service, repository, user):
    if repository:
        targets = repository.list_charge_targets(user['tenant_id'], user['project_id'])
        fees = repository.list_fee_types(user['tenant_id'], user['project_id'])
        bills = repository.list_bills(user['tenant_id'], user['project_id'], None, None)
    else:
        targets = service.list_charge_targets(user, user['project_id'])
        fees = service.list_fee_types(user, user['project_id'])
        bills = service.list_bills(user, user['project_id'], None, None)
    return targets, fees, bills


def register_batch_bill_preview_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _preview(user, fee_type_id, billing_period, service_start, service_end, category, building, unit, use_payment_cycle):
        targets, fees, bills = _context(service, repository, user)
        fee = next((item for item in fees if int(item['id']) == int(fee_type_id)), None)
        if not fee:
            raise HTTPException(status_code=404, detail='fee type not found')
        rows = build_batch_bill_rows(targets, fee, user['tenant_id'], user['project_id'], billing_period, service_start, service_end, category, building, unit, bool(use_payment_cycle))
        existing = {bill.get('bill_number') for bill in bills}
        return _preview_items(rows, targets, existing)

    @app.post('/backoffice/bills/batch-generate-preview', response_class=HTMLResponse)
    def preview_batch_generate_bill_page(fee_type_id: int = Form(...), billing_period: str = Form(...), service_start: str = Form(...), service_end: str = Form(''), category: str = Form(''), building: str = Form(''), unit: str = Form(''), use_payment_cycle: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            create_items, skip_items, amount_total = _preview(user, fee_type_id, billing_period, service_start, service_end, category, building, unit, use_payment_cycle)
            form = {'fee_type_id': fee_type_id, 'billing_period': billing_period, 'service_start': service_start, 'service_end': service_end, 'category': category, 'building': building, 'unit': unit, 'use_payment_cycle': use_payment_cycle}
            return HTMLResponse(_render_preview(user, create_items, skip_items, amount_total, form))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/bills/batch-generate-confirm')
    def confirm_batch_generate_bill_page(fee_type_id: int = Form(...), billing_period: str = Form(...), service_start: str = Form(...), service_end: str = Form(''), category: str = Form(''), building: str = Form(''), unit: str = Form(''), use_payment_cycle: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            if repository:
                result = repository.batch_generate_bills(user['tenant_id'], user['project_id'], fee_type_id, billing_period, service_start, service_end, category, building, unit, actor_user_id=user['id'], use_payment_cycle=bool(use_payment_cycle))
            else:
                result = service.batch_generate_bills(user, user['project_id'], fee_type_id, billing_period, service_start, service_end, category, building, unit, bool(use_payment_cycle))
            msg = f"批量出账{result['created_count']}张，跳过{result['skipped_count']}张，金额合计{result.get('amount_total', 0)}元"
            query = urllib.parse.urlencode({'period': billing_period, 'message': msg})
            return RedirectResponse(f'/backoffice/bills?{query}', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
