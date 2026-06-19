#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Business closure guidance for SaaS backoffice pages."""

from server.saas_user_pages import _h

STEPS = {
    'charge_targets': ('第 1 步', '录入/导入收费对象', '下一步：配置收费项目', '/backoffice/fee-types'),
    'fee_types': ('第 2 步', '配置收费项目和单价', '下一步：生成账单', '/backoffice/bills'),
    'bills': ('第 3 步', '生成账单', '下一步：登记收款', '/backoffice/payments'),
    'payments': ('第 5 步', '登记收款', '下一步：查看对账报表', '/backoffice/reports'),
    'reports': ('第 6 步', '核对报表并导出', '可导出账单或收款记录', '/api/exports/bills'),
}


def render_business_closure(page_key):
    step, title, next_label, href = STEPS[page_key]
    extra = ''
    if page_key == 'bills':
        extra = '<span class="badge">第 4 步：审核账单</span>'
    if page_key == 'reports':
        extra = '<a class="ghost-link" href="/api/exports/payments?period=2026-06">导出收款记录</a>'
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">业务闭环</div><div class="card-b"><span class="badge">{_h(step)}：{_h(title)}</span> {extra}<p class="sub" style="margin-top:10px">当前租户和项目隔离：本页只处理当前公司、当前项目的数据。</p><a class="ghost-link" href="{_h(href)}">{_h(next_label)}</a></div></section>'''
