#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment workbench rendering helpers for SaaS pages."""

from server.saas_user_pages import _h


def bill_status_label(status):
    return {
        'pending_review': '待审核',
        'unpaid': '未收款',
        'partial': '部分收款',
        'paid': '已收款',
    }.get(str(status or ''), str(status or ''))


def collection_board(bills, payments):
    receivable = sum(float(bill.get('amount') or 0) for bill in bills if bill.get('status') in {'unpaid', 'partial'})
    unpaid = sum(float(bill.get('unpaid_amount', bill.get('amount')) or 0) for bill in bills if bill.get('status') in {'unpaid', 'partial'})
    available = sum(1 for bill in bills if bill.get('status') in {'unpaid', 'partial'})
    receipt_action = _latest_receipt_action(payments)
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">收款办理看板</div><div class="card-b"><div class="actions"><span class="badge">可登记收款账单 {available}</span><span class="badge">待收金额 {round(receivable, 2)}</span><span class="badge">欠费余额 {round(unpaid, 2)}</span>{receipt_action}</div><div class="hint">收款后自动更新已收、欠费和账单状态；登记后可查看收据、打印收据或导出收款流水。</div></div></section>'''


def _latest_receipt_action(payments):
    if not payments:
        return ''
    latest = payments[0]
    href = f"/backoffice/payments/{_h(latest.get('id'))}/receipt"
    return f'<a class="ghost-link" href="{href}">查看收据</a><a class="ghost-link" href="{href}/print">打印收据</a>'
