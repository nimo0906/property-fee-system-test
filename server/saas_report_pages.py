#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML reconciliation report pages for SaaS backoffice."""

from server.saas_repository import TenantScopeError
from server.saas_business_closure import render_business_closure
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page, _role_name


def _metric(label, value, kind=''):
    display = '0.0' if value == 0 else value
    return f'<div class="card"><div class="card-h">{_h(label)}</div><div class="card-b"><div class="metric {kind}">{_h(display)}</div></div></div>'


def _render_report(user, period, summary):
    role_label = _role_name(user.get('role_code'))
    readonly = '<span class="badge">只读</span>' if user.get('role_code') == 'executive' else ''
    metrics = ''.join([
        _metric('账单数量', summary.get('bill_count', 0)),
        _metric('应收金额', summary.get('bill_amount_total', 0.0)),
        _metric('实收金额', summary.get('payment_amount_total', 0.0)),
        _metric('欠费金额', summary.get('unpaid_amount_total', 0.0)),
    ])
    body = f'''
<section class="hero"><div><h1>对账报表</h1><div class="sub">按账期汇总当前租户和项目的应收、实收、欠费。报表只读取本公司数据，避免不同公司数据混在一起。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{render_business_closure('reports')}
<section class="card" style="margin-bottom:18px"><div class="card-b"><form method="get" action="/backoffice/reports" class="filters"><div><label>账期</label><input name="period" required value="{_h(period)}" placeholder="例如 2026-09"></div><div><button class="primary">查看报表</button></div><div class="hint">当前角色：{_h(role_label)} {readonly}</div></form></div></section>
<section class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">{metrics}</section>'''
    return _page('对账报表', body)


def register_report_pages(app, service, repository, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/reports', response_class=HTMLResponse)
    def report_page(period: str = '', user=Depends(current_user)):
        try:
            service._require(user, 'read')
            selected_period = period or '2026-09'
            if repository:
                summary = repository.report_summary(user['tenant_id'], user['project_id'], selected_period)
            else:
                summary = service.report(user, user['project_id'], selected_period)
            return HTMLResponse(_render_report(user, selected_period, summary))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
