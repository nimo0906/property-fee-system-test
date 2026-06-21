#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML bill generation and list pages for SaaS backoffice."""

import urllib.parse

from server.saas_business_closure import render_business_closure
from server.saas_repository import TenantScopeError
from server.saas_fee_rules import calculate_bill_amount
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _target_label(item):
    base = f"{item.get('building', '')} {item.get('unit', '')} {item.get('room_number', '')}".strip()
    extra = ' / '.join(str(item.get(k) or '').strip() for k in ['shop_name', 'tenant_name'] if str(item.get(k) or '').strip())
    return f"{base} / {extra}" if extra else base


def _options(items, label_func):
    return ''.join(f'<option value="{_h(i.get("id"))}">{_h(label_func(i))}</option>' for i in items)


def _bill_rows(bills, targets, fees):
    target_map = {int(i['id']): i for i in targets}
    fee_map = {int(i['id']): i for i in fees}
    rows = []
    for bill in bills:
        target = target_map.get(int(bill.get('charge_target_id') or 0), {})
        fee = fee_map.get(int(bill.get('fee_type_id') or 0), {})
        approve_action = ''
        checkbox = ''
        if bill.get('status') == 'pending_review':
            checkbox = f'<input type="checkbox" name="bill_ids" value="{_h(bill.get("id"))}">'
            approve_action = f'<form method="post" action="/backoffice/bills/{_h(bill.get("id"))}/approve" class="inline"><button class="primary">审核通过</button></form>'
        rows.append(f'''<tr><td>{checkbox}</td><td>{_h(bill.get('bill_number'))}</td><td>{_h(bill.get('billing_period'))}</td><td>{_h(_target_label(target))}</td><td>{_h(fee.get('name'))}</td><td>{_h(bill.get('amount'))}</td><td>{_h(bill.get('paid_amount', 0))}</td><td>{_h(bill.get('unpaid_amount', bill.get('amount')))}</td><td>{_h(bill.get('status'))}</td><td>{approve_action}</td></tr>''')
    return ''.join(rows) or '<tr><td colspan="10">暂无账单</td></tr>'


def _render_bills(user, bills, targets, fees, filters=None, message='', page=1, page_size=20, total=0):
    filters = filters or {}
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_generate = user.get('role_code') in {'platform_admin', 'system_admin', 'finance'}
    form = _create_form(targets, fees) if can_generate else '<div class="hint">当前角色只能查看账单，不能生成账单。</div>'
    batch_form = _batch_generate_form(fees) if can_generate else ''
    rows = _bill_rows(bills, targets, fees)
    pager = _pager(filters, page, page_size, total)
    batch = _batch_approve_bar(user, filters)
    body = f'''
<section class="hero"><div><h1>账单生成</h1><div class="sub">从当前项目的收费对象和收费项目生成应收账单。账单、金额和筛选结果都按当前租户和项目隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{render_business_closure('bills')}
{_filter_form(filters, page_size)}
<section class="grid"><div class="card"><div class="card-h">账单列表</div><div class="card-b"><form method="post" action="/backoffice/bills/batch-approve">{batch}{pager}<table><thead><tr><th>批量审核</th><th>账单号</th><th>账期</th><th>收费对象</th><th>收费项目</th><th>金额</th><th>已收</th><th>欠费</th><th>状态</th><th>审核</th></tr></thead><tbody>{rows}</tbody></table>{pager}</form></div></div>
<aside class="card"><div class="card-h">生成账单</div><div class="card-b">{form}</div></aside></section>
<section class="card" style="margin-top:18px"><div class="card-h">批量出账</div><div class="card-b">{batch_form}</div></section>'''
    return _page('账单生成', body)


def _bill_export_href(filters):
    params = {key: value for key, value in filters.items() if value}
    query = urllib.parse.urlencode(params)
    return '/api/exports/bills?' + query if query else '/api/exports/bills'


def _filter_form(filters, page_size):
    page_size_options = ''.join(
        f'<option value="{n}"{" selected" if int(page_size) == n else ""}>{n}</option>'
        for n in [10, 20, 50]
    )
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">高级筛选</div><div class="card-b"><form method="get" action="/backoffice/bills" class="filters"><input type="hidden" name="page" value="1"><div><label>账期</label><input name="period" value="{_h(filters.get('period'))}" placeholder="例如 2026-06"></div><div><label>状态</label><select name="status">{_status_options(filters.get('status', ''))}</select></div><div><label>房号 / 铺位号</label><input name="room_number" value="{_h(filters.get('room_number'))}" placeholder="房号关键词"></div><div><label>最低金额</label><input name="amount_min" type="number" step="0.01" min="0" value="{_h(filters.get('amount_min'))}"></div><div><label>最高金额</label><input name="amount_max" type="number" step="0.01" min="0" value="{_h(filters.get('amount_max'))}"></div><div><label>每页数量</label><select name="page_size">{page_size_options}</select></div><div><button class="primary">查询账单</button></div><div><a class="ghost-link" href="{_h(_bill_export_href(filters))}">导出账单</a></div></form></div></section>'''


def _batch_approve_bar(user, filters):
    if user.get('role_code') not in {'platform_admin', 'system_admin', 'finance'}:
        return ''
    hidden = ''.join(f'<input type="hidden" name="{_h(key)}" value="{_h(filters.get(key, ""))}">' for key in ['period', 'status', 'room_number', 'amount_min', 'amount_max'])
    return f'''<div class="actions" style="margin-bottom:12px">{hidden}<button class="primary">批量审核选中账单</button><button class="ghost" formaction="/backoffice/bills/batch-approve-filtered">批量审核当前筛选待审核账单</button><span class="hint">批量审核仅处理待审核账单。</span></div>'''


def _status_options(selected):
    items = [('', '全部状态'), ('pending_review', '待审核'), ('unpaid', '未收款'), ('partial', '部分收款'), ('paid', '已收款')]
    return ''.join(f'<option value="{_h(v)}"{" selected" if selected == v else ""}>{_h(label)}</option>' for v, label in items)


def _create_form(targets, fees):
    if not targets or not fees:
        return '<div class="hint">请先维护收费对象和收费项目，再生成账单。</div>'
    target_options = _options(targets, _target_label)
    fee_options = _options(fees, lambda item: f"{item.get('name')} · {item.get('unit_price')}")
    return f'''<form method="post" action="/backoffice/bills/generate"><label>收费对象</label><select name="target_id" required>{target_options}</select><label>收费项目</label><select name="fee_type_id" required>{fee_options}</select><label>账期</label><input name="billing_period" required placeholder="例如 2026-06"><label>服务开始日期</label><input name="service_start" required type="date"><label>服务结束日期</label><input name="service_end" required type="date"><button class="primary">生成账单</button><div class="hint">金额按收费方式、独立单价和服务期自动计算，生成后进入待审核状态。</div></form>'''


def _batch_generate_form(fees):
    if not fees:
        return '<div class="hint">请先维护收费项目，再批量出账。</div>'
    fee_options = _options(fees, lambda item: f"{item.get('name')} · {item.get('unit_price')}")
    category_options = '<option value="">全部类型</option><option value="居民">仅居民</option><option value="商户">仅商户</option><option value="办公">仅办公</option><option value="其他">仅其他</option>'
    return f'''<form method="post" action="/backoffice/bills/batch-generate"><label>收费项目</label><select name="fee_type_id" required>{fee_options}</select><label>对象范围</label><select name="category">{category_options}</select><label>楼栋 / 区域范围</label><input name="building" placeholder="选填，精确匹配楼栋/区域"><label>单元 / 分区范围</label><input name="unit" placeholder="选填，精确匹配单元/分区"><label>账期</label><input name="billing_period" required placeholder="例如 2026-06"><label>服务开始日期</label><input name="service_start" required type="date"><label>服务结束日期</label><input name="service_end" type="date"><label><input type="checkbox" name="use_payment_cycle" value="1"> 按收费对象缴费周期自动计算服务结束</label><button class="primary">批量出账</button><div class="hint">按当前租户和项目内收费对象批量生成；同一账期、收费项目、收费对象已存在账单会自动跳过。</div></form>'''


def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _normalize_filters(period='', status='', room_number='', amount_min='', amount_max='', page=1, page_size=20):
    filters = {
        'period': str(period or '').strip(),
        'status': str(status or '').strip(),
        'room_number': str(room_number or '').strip(),
        'amount_min': str(amount_min or '').strip(),
        'amount_max': str(amount_max or '').strip(),
    }
    if filters['status'] not in {'', 'pending_review', 'unpaid', 'partial', 'paid'}:
        filters['status'] = ''
    page = max(_to_int(page, 1), 1)
    page_size = min(max(_to_int(page_size, 20), 1), 50)
    return filters, page, page_size


def _filter_bills(bills, targets, filters):
    target_map = {int(i['id']): i for i in targets}
    amount_min = _to_float(filters.get('amount_min'))
    amount_max = _to_float(filters.get('amount_max'))
    rows = []
    for bill in bills:
        target = target_map.get(int(bill.get('charge_target_id') or 0), {})
        amount = float(bill.get('amount') or 0)
        if filters.get('period') and bill.get('billing_period') != filters['period']:
            continue
        if filters.get('status') and bill.get('status') != filters['status']:
            continue
        if filters.get('room_number') and filters['room_number'].lower() not in str(target.get('room_number', '')).lower():
            continue
        if amount_min is not None and amount < amount_min:
            continue
        if amount_max is not None and amount > amount_max:
            continue
        rows.append(bill)
    return rows


def _paginate(items, page, page_size):
    total = len(items)
    start = (page - 1) * page_size
    return items[start:start + page_size], total


def _query(filters, page, page_size):
    params = {key: value for key, value in filters.items() if value}
    params['page'] = str(page)
    params['page_size'] = str(page_size)
    return urllib.parse.urlencode(params)


def _pager(filters, page, page_size, total):
    prev_link = f'<a class="ghost-link" href="/backoffice/bills?{_query(filters, page - 1, page_size)}">上一页</a>' if page > 1 else '<span class="ghost-link disabled">上一页</span>'
    next_link = f'<a class="ghost-link" href="/backoffice/bills?{_query(filters, page + 1, page_size)}">下一页</a>' if page * page_size < total else '<span class="ghost-link disabled">下一页</span>'
    return f'<div class="pager"><span>共 {total} 张账单 · 第 {page} 页</span><span>{prev_link} {next_link}</span></div>'


def register_bill_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _context(user, period='', status=''):
        service._require(user, 'read')
        if repository:
            targets = repository.list_charge_targets(user['tenant_id'], user['project_id'])
            fees = repository.list_fee_types(user['tenant_id'], user['project_id'])
            bills = repository.list_bills(user['tenant_id'], user['project_id'], None, None)
        else:
            targets = service.list_charge_targets(user, user['project_id'])
            fees = service.list_fee_types(user, user['project_id'])
            bills = service.list_bills(user, user['project_id'], None, None)
        return bills, targets, fees

    @app.get('/backoffice/bills', response_class=HTMLResponse)
    def bill_page(period: str = '', status: str = '', room_number: str = '', amount_min: str = '', amount_max: str = '', page: int = 1, page_size: int = 20, message: str = '', user=Depends(current_user)):
        try:
            filters, page, page_size = _normalize_filters(period, status, room_number, amount_min, amount_max, page, page_size)
            bills, targets, fees = _context(user)
            filtered = _filter_bills(bills, targets, filters)
            visible, total = _paginate(filtered, page, page_size)
            return HTMLResponse(_render_bills(user, visible, targets, fees, filters, message, page, page_size, total))
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
                amount = calculate_bill_amount(target, fee, service_start, service_end)
                repository.create_bill(user['tenant_id'], user['project_id'], target_id, fee_type_id, billing_period, service_start, service_end, amount, actor_user_id=user['id'])
            else:
                service.generate_bill(user, user['project_id'], service.targets[target_id], service.fees[fee_type_id], billing_period, service_start, service_end)
            return RedirectResponse(f'/backoffice/bills?period={_h(billing_period)}&message=账单已生成', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/bills/batch-generate')
    def batch_generate_bill_page(fee_type_id: int = Form(...), billing_period: str = Form(...), service_start: str = Form(...), service_end: str = Form(''), category: str = Form(''), building: str = Form(''), unit: str = Form(''), use_payment_cycle: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            if repository:
                result = repository.batch_generate_bills(user['tenant_id'], user['project_id'], fee_type_id, billing_period, service_start, service_end, category, building, unit, actor_user_id=user['id'], use_payment_cycle=bool(use_payment_cycle))
            else:
                result = service.batch_generate_bills(user, user['project_id'], fee_type_id, billing_period, service_start, service_end, category, building, unit, bool(use_payment_cycle))
            msg = f"批量出账{result['created_count']}张，跳过{result['skipped_count']}张，金额合计{result.get('amount_total', 0)}元"
            item_details = []
            for item in result.get('created_items', []):
                item_details.append(
                    f"{item.get('room_number')} {item.get('service_start')}~{item.get('service_end')} {item.get('amount')}元"
                )
            if item_details:
                msg = f"{msg}；{'；'.join(item_details)}"
            query = urllib.parse.urlencode({'period': billing_period, 'message': msg})
            return RedirectResponse(f'/backoffice/bills?{query}', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/bills/{bill_id}/approve')
    def approve_bill_page(bill_id: int, user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            if repository:
                repository.approve_bill(user['tenant_id'], user['project_id'], bill_id, actor_user_id=user['id'])
            else:
                service.approve_bill(user, user['project_id'], bill_id)
            return RedirectResponse('/backoffice/bills?status=pending_review&message=账单已审核', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/bills/batch-approve')
    def batch_approve_bill_page(bill_ids: list[int] = Form([]), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            count = 0
            for bill_id in bill_ids:
                if repository:
                    repository.approve_bill(user['tenant_id'], user['project_id'], int(bill_id), actor_user_id=user['id'])
                else:
                    service.approve_bill(user, user['project_id'], int(bill_id))
                count += 1
            return RedirectResponse(f'/backoffice/bills?status=pending_review&message=批量审核{count}张账单', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/bills/batch-approve-filtered')
    def batch_approve_filtered_bill_page(period: str = Form(''), status: str = Form(''), room_number: str = Form(''), amount_min: str = Form(''), amount_max: str = Form(''), page_size: int = Form(20), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            filters, _, page_size = _normalize_filters(period, status, room_number, amount_min, amount_max, 1, page_size)
            bills, targets, _ = _context(user)
            pending = [bill for bill in _filter_bills(bills, targets, filters) if bill.get('status') == 'pending_review']
            for bill in pending:
                if repository:
                    repository.approve_bill(user['tenant_id'], user['project_id'], int(bill['id']), actor_user_id=user['id'])
                else:
                    service.approve_bill(user, user['project_id'], int(bill['id']))
            query = _query(filters, 1, page_size)
            message = urllib.parse.quote(f'批量审核{len(pending)}张账单')
            return RedirectResponse(f'/backoffice/bills?{query}&message={message}', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
