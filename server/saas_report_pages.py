#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML reconciliation report pages for SaaS backoffice."""

from urllib.parse import urlencode

from server.saas_repository import TenantScopeError
from server.saas_business_closure import render_business_closure
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page, _role_name


def _metric(label, value, kind=''):
    display = '0.0' if value == 0 else value
    return f'<div class="card"><div class="card-h">{_h(label)}</div><div class="card-b"><div class="metric {kind}">{_h(display)}</div></div></div>'


def _percent(numerator, denominator):
    if not denominator:
        return '0.00%'
    return f'{(float(numerator or 0) / float(denominator) * 100):.2f}%'


def _export_links(period):
    query = urlencode({'period': period}) if period else ''
    suffix = f'?{query}' if query else ''
    return f'''<div class="actions"><a class="ghost-link" href="/api/exports/bills{suffix}">导出账单</a><a class="ghost-link" href="/api/exports/payments{suffix}">导出收款流水</a><a class="ghost-link" href="/api/exports/reports/breakdown.csv{suffix}">导出分组汇总</a><a class="ghost-link" href="/api/exports/reports/arrears-bills.csv{suffix}">导出欠费明细</a></div>'''


def _filter_card(user, period):
    role_label = _role_name(user.get('role_code'))
    readonly = '<span class="badge">只读</span>' if user.get('role_code') == 'executive' else ''
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">高级筛选</div><div class="card-b"><form method="get" action="/backoffice/reports" class="filters"><div><label>账期</label><input name="period" required value="{_h(period)}" placeholder="例如 2026-09"></div><div><button class="primary">查看报表</button></div><div>{_export_links(period)}</div><div class="hint">当前角色：{_h(role_label)} {readonly}</div></form></div></section>'''


def _summary_card(summary, breakdown=None):
    due = float(summary.get('bill_amount_total') or 0)
    paid = float(summary.get('payment_amount_total') or 0)
    unpaid = float(summary.get('unpaid_amount_total') or 0)
    collection_rate = _percent(paid, due)
    arrears_rate = _percent(unpaid, due)
    hint = '暂无欠费' if unpaid <= 0 else f'欠费提醒：当前账期仍有 {_h(unpaid)} 未收，请安排催缴或复核。'
    top_area = _top_arrears_item((breakdown or {}).get('by_building', []))
    top_unit = _top_arrears_item((breakdown or {}).get('by_unit', []))
    top_fee = _top_arrears_item((breakdown or {}).get('by_fee_type', []))
    top_category = _top_arrears_item((breakdown or {}).get('by_category', []))
    area_text = _top_arrears_text(top_area)
    unit_text = _top_arrears_text(top_unit)
    fee_text = _top_arrears_text(top_fee)
    category_text = _top_arrears_text(top_category)
    return f'''<section class="card" style="margin-top:18px"><div class="card-h">经营摘要</div><div class="card-b"><table><tbody><tr><th>收缴率</th><td>{_h(collection_rate)}</td></tr><tr><th>欠费率</th><td>{_h(arrears_rate)}</td></tr><tr><th>欠费最高区域</th><td>{area_text}</td></tr><tr><th>欠费最高单元/分区</th><td>{unit_text}</td></tr><tr><th>欠费最高收费项目</th><td>{fee_text}</td></tr><tr><th>欠费最高对象分类</th><td>{category_text}</td></tr><tr><th>欠费提醒</th><td>{hint}</td></tr></tbody></table></div></section>'''


def _top_arrears_item(rows):
    candidates = [row for row in rows if float(row.get('unpaid_amount_total') or 0) > 0]
    return max(candidates, key=lambda row: float(row.get('unpaid_amount_total') or 0), default=None)


def _top_arrears_text(row):
    if not row:
        return '暂无欠费'
    return f"{_h(row.get('name'))}：欠费{_h(row.get('unpaid_amount_total'))}，欠费率{_h(row.get('arrears_rate', '0.00%'))}"


def _breakdown_table(title, rows):
    body = ''.join([
        f"<tr><td>{_h(row.get('name'))}</td><td>{_h(row.get('bill_count'))}</td><td>{_h(row.get('bill_amount_total'))}</td><td>{_h(row.get('payment_amount_total'))}</td><td>{_h(row.get('unpaid_amount_total'))}</td><td>{_h(row.get('collection_rate', '0.00%'))}</td><td>{_h(row.get('arrears_rate', '0.00%'))}</td></tr>"
        for row in rows
    ]) or '<tr><td colspan="7" class="hint">暂无数据</td></tr>'
    return f'''<section class="card"><div class="card-h">{_h(title)}</div><div class="card-b"><table><thead><tr><th>名称</th><th>账单数</th><th>应收</th><th>实收</th><th>欠费</th><th>收缴率</th><th>欠费率</th></tr></thead><tbody>{body}</tbody></table></div></section>'''


def _breakdown_cards(breakdown):
    return f'''<section class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-top:18px">{_breakdown_table('按楼栋 / 区域汇总', breakdown.get('by_building', []))}{_breakdown_table('按单元 / 分区汇总', breakdown.get('by_unit', []))}{_breakdown_table('按收费项目汇总', breakdown.get('by_fee_type', []))}{_breakdown_table('按收费对象分类汇总', breakdown.get('by_category', []))}</section>'''


def _owner_contact(item):
    return ' / '.join(str(item.get(k) or '').strip() for k in ['owner_name', 'owner_phone'] if str(item.get(k) or '').strip())


def _arrears_bill_rows(items, period):
    rows = []
    for item in items:
        unpaid = float(item.get('unpaid_amount') or 0)
        if unpaid <= 0:
            continue
        label = ' '.join(str(item.get(k) or '') for k in ['building', 'unit', 'room_number']).strip()
        detail = ' / '.join(str(item.get(k) or '').strip() for k in ['shop_name', 'tenant_name'] if str(item.get(k) or '').strip())
        bill_href = '/backoffice/bills?' + urlencode({'period': period, 'room_number': item.get('room_number') or ''})
        rows.append(f"<tr><td>{_h(label)}</td><td>{_h(detail)}</td><td>{_h(_owner_contact(item))}</td><td>{_h(item.get('fee_name') or '')}</td><td>{_h(item.get('amount'))}</td><td>{_h(item.get('paid_amount', 0))}</td><td>{_h(item.get('unpaid_amount', 0))}</td><td><a class=\"ghost-link\" href=\"{_h(bill_href)}\">查看账单</a></td></tr>")
    return ''.join(rows) or '<tr><td colspan="8" class="hint">暂无欠费账单</td></tr>'


def _arrears_bill_table(items, period):
    sorted_items = sorted(items, key=lambda item: float(item.get('unpaid_amount') or 0), reverse=True)[:10]
    return f'''<section class="card" style="margin-top:18px"><div class="card-h">欠费账单明细</div><div class="card-b"><table><thead><tr><th>收费对象</th><th>商户/承租人</th><th>业主/电话</th><th>收费项目</th><th>应收</th><th>已收</th><th>欠费</th><th>操作</th></tr></thead><tbody>{_arrears_bill_rows(sorted_items, period)}</tbody></table><div class="hint">按欠费金额从高到低显示当前账期前 10 条，用于收费员催缴核对。</div></div></section>'''


def _render_report(user, period, summary, breakdown=None, arrears_bills=None):
    metrics = ''.join([
        _metric('账单数量', summary.get('bill_count', 0)),
        _metric('应收金额', summary.get('bill_amount_total', 0.0)),
        _metric('实收金额', summary.get('payment_amount_total', 0.0)),
        _metric('欠费金额', summary.get('unpaid_amount_total', 0.0)),
    ])
    body = f'''
<section class="hero"><div><h1>对账报表</h1><div class="sub">按账期汇总当前租户和项目的应收、实收、欠费。报表只读取本公司数据，避免不同公司数据混在一起。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{render_business_closure('reports')}
{_filter_card(user, period)}
<section class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">{metrics}</section>
{_breakdown_cards(breakdown or {'by_building': [], 'by_unit': [], 'by_fee_type': [], 'by_category': []})}
{_arrears_bill_table(arrears_bills or [], period)}
{_summary_card(summary, breakdown or {})}'''
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
                breakdown = repository.report_breakdown(user['tenant_id'], user['project_id'], selected_period)
                arrears_bills = repository.search_bills(user['tenant_id'], user['project_id'], '', selected_period, None, 1, 10000)['items']
            else:
                summary = service.report(user, user['project_id'], selected_period)
                breakdown = {'by_building': [], 'by_unit': [], 'by_fee_type': [], 'by_category': []}
                arrears_bills = service.search_bills(user, user['project_id'], '', selected_period, None, 1, 10000)['items']
            return HTMLResponse(_render_report(user, selected_period, summary, breakdown, arrears_bills))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
