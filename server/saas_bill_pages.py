#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML bill generation and list pages for SaaS backoffice."""

from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _target_label(item):
    return f"{item.get('building', '')} {item.get('unit', '')} {item.get('room_number', '')}".strip()


def _options(items, label_func):
    return ''.join(f'<option value="{_h(i.get("id"))}">{_h(label_func(i))}</option>' for i in items)


def _bill_rows(bills, targets, fees):
    target_map = {int(i['id']): i for i in targets}
    fee_map = {int(i['id']): i for i in fees}
    rows = []
    for bill in bills:
        target = target_map.get(int(bill.get('charge_target_id') or 0), {})
        fee = fee_map.get(int(bill.get('fee_type_id') or 0), {})
        rows.append(f'''<tr><td>{_h(bill.get('bill_number'))}</td><td>{_h(bill.get('billing_period'))}</td><td>{_h(_target_label(target))}</td><td>{_h(fee.get('name'))}</td><td>{_h(bill.get('amount'))}</td><td>{_h(bill.get('status'))}</td></tr>''')
    return ''.join(rows) or '<tr><td colspan="6">暂无账单</td></tr>'


def _render_bills(user, bills, targets, fees, filters=None, message=''):
    filters = filters or {}
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_generate = user.get('role_code') in {'platform_admin', 'system_admin', 'finance'}
    form = _create_form(targets, fees) if can_generate else '<div class="hint">当前角色只能查看账单，不能生成账单。</div>'
    rows = _bill_rows(bills, targets, fees)
    body = f'''
<section class="hero"><div><h1>账单生成</h1><div class="sub">从当前项目的收费对象和收费项目生成应收账单。账单、金额和筛选结果都按当前租户和项目隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
<section class="card" style="margin-bottom:18px"><div class="card-b"><form method="get" action="/backoffice/bills" class="filters"><div><label>账期</label><input name="period" value="{_h(filters.get('period', ''))}" placeholder="例如 2026-06"></div><div><label>状态</label><select name="status">{_status_options(filters.get('status', ''))}</select></div><div><button class="primary">查询账单</button></div></form></div></section>
<section class="grid"><div class="card"><div class="card-h">账单列表</div><div class="card-b"><table><thead><tr><th>账单号</th><th>账期</th><th>收费对象</th><th>收费项目</th><th>金额</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<aside class="card"><div class="card-h">生成账单</div><div class="card-b">{form}</div></aside></section>'''
    return _page('账单生成', body)


def _status_options(selected):
    items = [('', '全部状态'), ('pending_review', '待审核'), ('unpaid', '未收款'), ('partial', '部分收款'), ('paid', '已收款')]
    return ''.join(f'<option value="{_h(v)}"{" selected" if selected == v else ""}>{_h(label)}</option>' for v, label in items)


def _create_form(targets, fees):
    if not targets or not fees:
        return '<div class="hint">请先维护收费对象和收费项目，再生成账单。</div>'
    target_options = _options(targets, _target_label)
    fee_options = _options(fees, lambda item: f"{item.get('name')} · {item.get('unit_price')}")
    return f'''<form method="post" action="/backoffice/bills/generate"><label>收费对象</label><select name="target_id" required>{target_options}</select><label>收费项目</label><select name="fee_type_id" required>{fee_options}</select><label>账期</label><input name="billing_period" required placeholder="例如 2026-06"><label>服务开始日期</label><input name="service_start" required type="date"><label>服务结束日期</label><input name="service_end" required type="date"><button class="primary">生成账单</button><div class="hint">当前版本金额 = 面积 × 收费项目单价，生成后进入待审核状态。</div></form>'''


def register_bill_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _context(user, period='', status=''):
        service._require(user, 'read')
        if repository:
            targets = repository.list_charge_targets(user['tenant_id'], user['project_id'])
            fees = repository.list_fee_types(user['tenant_id'], user['project_id'])
            bills = repository.list_bills(user['tenant_id'], user['project_id'], period or None, status or None)
        else:
            targets = service.list_charge_targets(user, user['project_id'])
            fees = service.list_fee_types(user, user['project_id'])
            bills = service.list_bills(user, user['project_id'], period or None, status or None)
        return bills, targets, fees

    @app.get('/backoffice/bills', response_class=HTMLResponse)
    def bill_page(period: str = '', status: str = '', message: str = '', user=Depends(current_user)):
        try:
            bills, targets, fees = _context(user, period, status)
            return HTMLResponse(_render_bills(user, bills, targets, fees, {'period': period, 'status': status}, message))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/bills/generate')
    def generate_bill_page(target_id: int = Form(...), fee_type_id: int = Form(...), billing_period: str = Form(...), service_start: str = Form(...), service_end: str = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            if repository:
                target = repository.get_charge_target(user['tenant_id'], user['project_id'], target_id)
                fee = repository.get_fee_type(user['tenant_id'], user['project_id'], fee_type_id)
                if not target or not fee:
                    raise HTTPException(status_code=404, detail='target or fee type not found')
                amount = round(float(target['area']) * float(fee['unit_price']), 2)
                repository.create_bill(user['tenant_id'], user['project_id'], target_id, fee_type_id, billing_period, service_start, service_end, amount, actor_user_id=user['id'])
            else:
                service.generate_bill(user, user['project_id'], service.targets[target_id], service.fees[fee_type_id], billing_period, service_start, service_end)
            return RedirectResponse(f'/backoffice/bills?period={_h(billing_period)}&message=账单已生成', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
