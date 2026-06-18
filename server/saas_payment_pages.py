#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML payment recording and list pages for SaaS backoffice."""

from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _payment_rows(payments):
    rows = []
    for payment in payments:
        rows.append(f'''<tr><td>{_h(payment.get('receipt_number'))}</td><td>{_h(payment.get('bill_number'))}</td><td>{_h(payment.get('billing_period'))}</td><td>{_h(payment.get('amount_paid'))}</td><td>{_h(payment.get('method'))}</td></tr>''')
    return ''.join(rows) or '<tr><td colspan="5">暂无收款</td></tr>'


def _render_payments(user, payments, bills, message=''):
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'cashier'}
    form = _create_form(bills) if can_write else '<div class="hint">当前角色只能查看收款，不能登记收款。</div>'
    rows = _payment_rows(payments)
    body = f'''
<section class="hero"><div><h1>收款登记</h1><div class="sub">登记已审核账单的收款记录，按当前租户和项目隔离。现金、转账、微信/支付宝线下记录都可在这里留痕。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
<section class="card" style="margin-bottom:18px"><div class="card-b"><form method="get" action="/backoffice/payments" class="filters"><div><label>关键字</label><input name="keyword" value="" placeholder="收据号 / 账单号 / 方式"></div><div><label>账期</label><input name="period" value="" placeholder="例如 2026-08"></div><div><button class="primary">查询收款</button></div></form></div></section>
<section class="grid"><div class="card"><div class="card-h">收款列表</div><div class="card-b"><table><thead><tr><th>收据号</th><th>账单号</th><th>账期</th><th>金额</th><th>方式</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<aside class="card"><div class="card-h">登记收款</div><div class="card-b">{form}</div></aside></section>'''
    return _page('收款登记', body)


def _create_form(bills):
    unpaid_bills = [bill for bill in bills if bill.get('status') in {'unpaid', 'partial'}]
    if not unpaid_bills:
        return '<div class="hint">请先把账单审核为未收款/部分收款，再登记收款。</div>'
    options = ''.join(f'<option value="{_h(b.get("id"))}">{_h(b.get("bill_number"))} · {_h(b.get("billing_period"))} · {_h(b.get("status"))} · {_h(b.get("amount"))}</option>' for b in unpaid_bills)
    return f'''<form method="post" action="/backoffice/payments/create"><label>账单</label><select name="bill_id" required>{options}</select><label>收款金额</label><input name="amount" required type="number" step="0.01" min="0.01" placeholder="例如 100"><label>收款方式</label><input name="method" placeholder="cash / transfer / wechat / alipay"><label>幂等键</label><input name="idempotency_key" placeholder="可选，防重复提交"><button class="primary">登记收款</button><div class="hint">幂等键用于防止重复入账；收款后账单状态会自动变为 partial 或 paid。</div></form>'''


def register_payment_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _context(user, keyword='', period=''):
        service._require(user, 'read')
        if repository:
            bills = repository.list_bills(user['tenant_id'], user['project_id'])
            payments = repository.search_payments(user['tenant_id'], user['project_id'], keyword or '', period or None, 1, 1000)['items']
        else:
            bills = service.list_bills(user, user['project_id'])
            payments = service.search_payments(user, user['project_id'], keyword or '', period or None, 1, 1000)['items']
        return bills, payments

    @app.get('/backoffice/payments', response_class=HTMLResponse)
    def payment_page(keyword: str = '', period: str = '', message: str = '', user=Depends(current_user)):
        try:
            bills, payments = _context(user, keyword, period)
            return HTMLResponse(_render_payments(user, payments, bills, message))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/payments/create')
    def create_payment_page(bill_id: int = Form(...), amount: float = Form(...), method: str = Form(''), idempotency_key: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'payment')
            if repository:
                item = repository.create_payment(user['tenant_id'], user['project_id'], bill_id, amount, method, idempotency_key or None, actor_user_id=user['id'])
            else:
                item = service.record_payment(user, bill_id, amount, method, idempotency_key or None)
            return RedirectResponse('/backoffice/payments?message=收款已登记', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
