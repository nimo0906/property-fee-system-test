#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review board rendering helpers for SaaS bill pages."""

from server.saas_user_pages import _h


CAN_REVIEW_ROLES = {'platform_admin', 'system_admin', 'finance'}


def bill_status_label(status):
    return {
        'pending_review': '待审核',
        'unpaid': '未收款',
        'partial': '部分收款',
        'paid': '已收款',
    }.get(str(status or ''), str(status or ''))


def bill_review_board(user, bills):
    pending = sum(1 for bill in bills if bill.get('status') == 'pending_review')
    unpaid = sum(1 for bill in bills if bill.get('status') in {'unpaid', 'partial'})
    reviewed = sum(1 for bill in bills if bill.get('status') in {'unpaid', 'partial', 'paid'})
    hint = '当前角色只能查看账单；请联系财务或管理员完成账单审核。'
    if user.get('role_code') in CAN_REVIEW_ROLES:
        hint = '审核通过后进入收款登记；审核前请核对收费对象、账期、服务期、收费项目和金额。'
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">出账审核看板</div><div class="card-b"><div class="actions"><span class="badge">待审核账单 {pending}</span><span class="badge">已审核账单 {reviewed}</span><span class="badge">待收款账单 {unpaid}</span><a class="ghost-link" href="/backoffice/bills?status=pending_review">查看待审核</a><a class="ghost-link" href="/backoffice/payments">去收款登记</a></div><div class="hint">{hint}</div></div></section>'''


def bill_review_header():
    return ''.join(
        f'<th>{_h(label)}</th>'
        for label in ['批量审核', '账单号', '账期', '服务期', '收费对象', '收费项目', '金额', '已收', '欠费', '状态', '审核/下一步']
    )


def bill_rows(bills, targets, fees, target_label_func):
    target_map = {int(i['id']): i for i in targets}
    fee_map = {int(i['id']): i for i in fees}
    rows = []
    for bill in bills:
        target = target_map.get(int(bill.get('charge_target_id') or 0), {})
        fee = fee_map.get(int(bill.get('fee_type_id') or 0), {})
        rows.append(_bill_row(bill, target, fee, target_label_func))
    return ''.join(rows) or '<tr><td colspan="11">暂无账单</td></tr>'


def _bill_row(bill, target, fee, target_label_func):
    checkbox = ''
    action = '<a class="ghost-link" href="/backoffice/payments">去收款登记</a>'
    if bill.get('status') == 'pending_review':
        checkbox = f'<input type="checkbox" name="bill_ids" value="{_h(bill.get("id"))}">'
        action = f'<form method="post" action="/backoffice/bills/{_h(bill.get("id"))}/approve" class="inline"><button class="primary">审核通过</button><a class="ghost-link" href="/backoffice/payments">去收款登记</a></form>'
    service_period = f"{bill.get('service_start', '')}~{bill.get('service_end', '')}"
    cells = [
        checkbox,
        _h(bill.get('bill_number')),
        _h(bill.get('billing_period')),
        _h(service_period),
        _h(target_label_func(target)),
        _h(fee.get('name')),
        _h(bill.get('amount')),
        _h(bill.get('paid_amount', 0)),
        _h(bill.get('unpaid_amount', bill.get('amount'))),
        _h(bill_status_label(bill.get('status'))),
        action,
    ]
    return '<tr>' + ''.join(f'<td>{cell}</td>' for cell in cells) + '</tr>'
