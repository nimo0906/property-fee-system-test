#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML payment recording, search, receipt pages for SaaS backoffice."""

from urllib.parse import urlencode

from server.saas_business_closure import render_business_closure
from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _to_float(value):
    try:
        return float(value) if str(value or '').strip() else None
    except ValueError:
        return None


def _filter_payments(payments, method='', amount_min='', amount_max=''):
    low = _to_float(amount_min)
    high = _to_float(amount_max)
    method = str(method or '').strip().lower()
    rows = []
    for item in payments:
        amount = float(item.get('amount_paid') or 0)
        if method and method not in str(item.get('method') or '').lower():
            continue
        if low is not None and amount < low:
            continue
        if high is not None and amount > high:
            continue
        rows.append(item)
    return rows


def _paginate(items, page, page_size):
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 20), 100), 1)
    total = len(items)
    start = (page - 1) * page_size
    return {'total': total, 'page': page, 'page_size': page_size, 'items': items[start:start + page_size]}


def _payment_rows(payments):
    rows = []
    for payment in payments:
        receipt = _h(payment.get('receipt_number'))
        href = f"/backoffice/payments/{_h(payment.get('id'))}/receipt"
        rows.append(f'''<tr><td><a class="ghost-link" href="{href}">{receipt}</a></td><td>{_h(payment.get('bill_number'))}</td><td>{_h(payment.get('billing_period'))}</td><td>{_h(payment.get('amount_paid'))}</td><td>{_h(payment.get('method'))}</td></tr>''')
    return ''.join(rows) or '<tr><td colspan="5">暂无收款</td></tr>'


def _query(params, **changes):
    data = {k: v for k, v in params.items() if v not in ('', None)}
    data.update({k: v for k, v in changes.items() if v not in ('', None)})
    return urlencode(data)


def _filter_card(params):
    export_period = params.get('period') or ''
    export_href = '/api/exports/payments?' + urlencode({'period': export_period}) if export_period else '/api/exports/payments'
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">高级筛选</div><div class="card-b"><form method="get" action="/backoffice/payments" class="filters"><div><label>关键字</label><input name="keyword" value="{_h(params.get('keyword'))}" placeholder="收据号 / 账单号"></div><div><label>账期</label><input name="period" value="{_h(params.get('period'))}" placeholder="例如 2026-08"></div><div><label>收款方式</label><input name="method" value="{_h(params.get('method'))}" placeholder="现金 / 转账 / 微信"></div><div><label>最小金额</label><input name="amount_min" value="{_h(params.get('amount_min'))}" type="number" step="0.01"></div><div><label>最大金额</label><input name="amount_max" value="{_h(params.get('amount_max'))}" type="number" step="0.01"></div><div><label>每页</label><select name="page_size"><option value="10"{' selected' if str(params.get('page_size')) == '10' else ''}>10</option><option value="20"{' selected' if str(params.get('page_size')) == '20' else ''}>20</option><option value="50"{' selected' if str(params.get('page_size')) == '50' else ''}>50</option></select></div><div><button class="primary">查询收款</button></div><div><a class="ghost-link" href="{_h(export_href)}">导出收款流水</a></div></form></div></section>'''


def _pager(result, params):
    page = result['page']
    size = result['page_size']
    total = result['total']
    prev_cls = ' ghost-link disabled' if page <= 1 else 'ghost-link'
    next_cls = ' ghost-link disabled' if page * size >= total else 'ghost-link'
    prev_href = '/backoffice/payments?' + _query(params, page=max(page - 1, 1), page_size=size)
    next_href = '/backoffice/payments?' + _query(params, page=page + 1, page_size=size)
    return f'''<div class="pager"><span>共 {_h(total)} 条 · 第 {_h(page)} 页 · 每页 {_h(size)} 条</span><span class="actions"><a class="{prev_cls}" href="{_h(prev_href)}">上一页</a><a class="{next_cls}" href="{_h(next_href)}">下一页</a></span></div>'''


def _render_payments(user, result, bills, params, message=''):
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'cashier'}
    form = _create_form(bills) if can_write else '<div class="hint">当前角色只能查看收款，不能登记收款。</div>'
    rows = _payment_rows(result['items'])
    body = f'''
<section class="hero"><div><h1>收款登记</h1><div class="sub">登记已审核账单的收款记录，按当前租户和项目隔离。现金、转账、微信/支付宝线下记录都可在这里留痕。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{render_business_closure('payments')}
{_filter_card(params)}
<section class="grid"><div class="card"><div class="card-h">收款列表</div><div class="card-b">{_pager(result, params)}<table><thead><tr><th>收据号</th><th>账单号</th><th>账期</th><th>金额</th><th>方式</th></tr></thead><tbody>{rows}</tbody></table>{_pager(result, params)}</div></div>
<aside class="card"><div class="card-h">登记收款</div><div class="card-b">{form}</div></aside></section>'''
    return _page('收款登记', body)


def _render_receipt(user, payment):
    body = f'''
<section class="hero"><div><h1>收据详情</h1><div class="sub">当前收据只展示当前公司、当前项目下的收款业务信息，不展示内部数据字段。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">收据详情</div><div class="card-b"><table><tbody>
<tr><th>收据号</th><td>{_h(payment.get('receipt_number'))}</td></tr>
<tr><th>账单号</th><td>{_h(payment.get('bill_number'))}</td></tr>
<tr><th>账期</th><td>{_h(payment.get('billing_period'))}</td></tr>
<tr><th>金额</th><td>{_h(payment.get('amount_paid'))}</td></tr>
<tr><th>收款方式</th><td>{_h(payment.get('method'))}</td></tr>
</tbody></table><div class="actions" style="margin-top:16px"><a class="ghost-link" href="/backoffice/payments">返回收款列表</a></div></div></section>'''
    return _page('收据详情', body)


def _create_form(bills):
    unpaid_bills = [bill for bill in bills if bill.get('status') in {'unpaid', 'partial'}]
    if not unpaid_bills:
        return '<div class="hint">请先把账单审核为未收款/部分收款，再登记收款。</div>'
    options = ''.join(f'<option value="{_h(b.get("id"))}">{_h(b.get("bill_number"))} · {_h(b.get("billing_period"))} · {_h(b.get("status"))} · 应收 {_h(b.get("amount"))} · 已收 {_h(b.get("paid_amount", 0))} · 欠费 {_h(b.get("unpaid_amount", b.get("amount")))}</option>' for b in unpaid_bills)
    return f'''<form method="post" action="/backoffice/payments/create"><label>账单</label><select name="bill_id" required>{options}</select><label>收款金额</label><input name="amount" required type="number" step="0.01" min="0.01" placeholder="例如 100"><label>收款方式</label><input name="method" placeholder="cash / transfer / wechat / alipay"><label>幂等键</label><input name="idempotency_key" placeholder="可选，防重复提交"><button class="primary">登记收款</button><div class="hint">幂等键用于防止重复入账；收款后账单状态会自动变为 partial 或 paid。</div></form>'''


def register_payment_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _context(user, keyword='', period='', method='', amount_min='', amount_max='', page=1, page_size=20):
        service._require(user, 'read')
        if repository:
            bills = repository.list_bills(user['tenant_id'], user['project_id'])
            rows = repository.search_payments(user['tenant_id'], user['project_id'], keyword or '', period or None, 1, 10000)['items']
        else:
            bills = service.list_bills(user, user['project_id'])
            rows = service.search_payments(user, user['project_id'], keyword or '', period or None, 1, 10000)['items']
        return bills, _paginate(_filter_payments(rows, method, amount_min, amount_max), page, page_size)

    def _find_payment(user, payment_id):
        rows = repository.search_payments(user['tenant_id'], user['project_id'], '', None, 1, 10000)['items'] if repository else service.search_payments(user, user['project_id'], '', None, 1, 10000)['items']
        return next((item for item in rows if int(item.get('id')) == int(payment_id)), None)

    @app.get('/backoffice/payments', response_class=HTMLResponse)
    def payment_page(keyword: str = '', period: str = '', method: str = '', amount_min: str = '', amount_max: str = '', page: int = 1, page_size: int = 20, message: str = '', user=Depends(current_user)):
        try:
            params = {'keyword': keyword, 'period': period, 'method': method, 'amount_min': amount_min, 'amount_max': amount_max, 'page': page, 'page_size': page_size}
            bills, result = _context(user, keyword, period, method, amount_min, amount_max, page, page_size)
            return HTMLResponse(_render_payments(user, result, bills, params, message))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/payments/{payment_id}/receipt', response_class=HTMLResponse)
    def receipt_page(payment_id: int, user=Depends(current_user)):
        try:
            service._require(user, 'read')
            item = _find_payment(user, payment_id)
            if not item:
                raise HTTPException(status_code=404, detail='receipt not found')
            return HTMLResponse(_render_receipt(user, item))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/payments/create')
    def create_payment_page(bill_id: int = Form(...), amount: float = Form(...), method: str = Form(''), idempotency_key: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'payment')
            if repository:
                repository.create_payment(user['tenant_id'], user['project_id'], bill_id, amount, method, idempotency_key or None, actor_user_id=user['id'])
            else:
                service.record_payment(user, bill_id, amount, method, idempotency_key or None)
            return RedirectResponse('/backoffice/payments?message=收款已登记', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
