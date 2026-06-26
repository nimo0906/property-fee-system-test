#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto billing batch query, detail, and rollback helpers."""

from server.db import h, m
from server.ui_components import render_table


def recent_auto_billing_runs(db, limit=8):
    return db.execute(
        "SELECT * FROM auto_billing_runs ORDER BY created_at DESC,id DESC LIMIT ?",
        (int(limit),)
    ).fetchall()


def get_auto_billing_run(db, batch_no):
    return db.execute("SELECT * FROM auto_billing_runs WHERE batch_no=?", (batch_no,)).fetchone()


def get_auto_billing_run_bills(db, batch_no):
    return db.execute(
        """SELECT b.*,r.building,r.unit,r.room_number,r.tenant_name,r.shop_name,o.name owner_name,
        f.name fee_name,COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid,
        (SELECT COUNT(*) FROM invoices WHERE bill_id=b.id) invoice_count,
        (SELECT COUNT(*) FROM invoice_requests WHERE bill_id=b.id) invoice_request_count
        FROM bills b
        LEFT JOIN rooms r ON r.id=b.room_id
        LEFT JOIN owners o ON o.id=b.owner_id
        LEFT JOIN fee_types f ON f.id=b.fee_type_id
        WHERE b.auto_batch_no=? AND b.source='auto_contract'
        ORDER BY r.building,r.unit,r.room_number,f.sort_order,b.id""",
        (batch_no,)
    ).fetchall()


def rollback_auto_billing_batch(db, batch_no):
    rows = get_auto_billing_run_bills(db, batch_no)
    deleted = blocked = 0
    for bill in rows:
        if float(bill['paid'] or 0) > 0 or bill['status'] in ('paid', 'partial'):
            blocked += 1
            continue
        if int(bill['invoice_count'] or 0) > 0 or int(bill['invoice_request_count'] or 0) > 0:
            blocked += 1
            continue
        db.execute("DELETE FROM bills WHERE id=?", (bill['id'],))
        deleted += 1
    status = 'rolled_back' if deleted and not blocked else ('partial_rollback' if deleted else 'blocked')
    db.execute(
        "UPDATE auto_billing_runs SET rollback_count=rollback_count+?,status=?,rolled_back_at=datetime('now','localtime') WHERE batch_no=?",
        (deleted, status, batch_no)
    )
    db.commit()
    return {'deleted': deleted, 'blocked': blocked, 'status': status}


def run_row_html(run):
    rollback = ''
    if run['status'] != 'rolled_back':
        rollback = (
            f'<form method="POST" action="/auto_billing/runs/{h(run["batch_no"])}/rollback" '
            'style="display:inline" '
            'onsubmit="return confirm(\'确认撤回本批次未缴账单？已缴、部分缴费、已开票账单不会撤回。\')">'
            '<button class="btn btn-sm btn-outline-danger">撤回未缴账单</button></form>'
        )
    badge = 'secondary' if run['status'] == 'rolled_back' else 'info'
    return f'''<tr><td><small>{h(run['batch_no'])}</small></td><td>{h(run['created_at'])}</td>
    <td>{h(run['operator'] or '-')}</td><td class="text-end">{run['generated_count']}</td>
    <td>{h(run['service_start_min'] or '-')} 至 {h(run['service_end_max'] or '-')}</td>
    <td><span class="badge bg-{badge}">{h(_run_status_text(run['status']))}</span></td>
    <td><a class="btn btn-sm btn-outline-primary" href="/auto_billing/runs/{h(run['batch_no'])}">查看详情</a> {rollback}</td></tr>'''


def run_detail_html(run, bills):
    if not run:
        return ''
    summary = _batch_summary(bills)
    bill_rows = ''.join(_bill_row_html(b) for b in bills)
    group_rows = ''.join(_group_row_html(g) for g in _tenant_room_groups(bills))
    group_table = render_table(
        ['租户 / 房间', ('笔数', 'text-end'), ('应收', 'text-end'), ('已收', 'text-end'), ('未收', 'text-end')],
        group_rows,
        table_class='table table-sm align-middle mb-0',
        empty_text='暂无可分组账单',
        col_count=5,
    )
    bill_table = render_table(
        ['租户', '房间/铺位', '收费项目', '服务期', '截止日', ('金额', 'text-end'), ('已缴', 'text-end'), '状态', '限制'],
        bill_rows,
        table_class='table table-hover align-middle small mb-0',
        empty_text='本批次账单已全部撤回或不存在',
        col_count=9,
    )
    rollback = ''
    if run['status'] != 'rolled_back':
        rollback = (
            f'<form method="POST" action="/auto_billing/runs/{h(run["batch_no"])}/rollback" class="d-inline" '
            'onsubmit="return confirm(\'确认撤回本批次未缴账单？\')">'
            '<button class="btn btn-outline-danger">撤回未缴账单</button></form>'
        )
    return f'''
    <div class="card"><div class="card-header">批次信息</div><div class="card-body">
    <div class="row g-3">
      <div class="col-md-3"><small class="text-muted">批次号</small><div><code>{h(run['batch_no'])}</code></div></div>
      <div class="col-md-3"><small class="text-muted">生成时间</small><div>{h(run['created_at'])}</div></div>
      <div class="col-md-2"><small class="text-muted">操作人</small><div>{h(run['operator'] or '-')}</div></div>
      <div class="col-md-2"><small class="text-muted">生成笔数</small><div>{run['generated_count']}</div></div>
      <div class="col-md-2"><small class="text-muted">状态</small><div>{h(_run_status_text(run['status']))}</div></div>
      <div class="col-md-6"><small class="text-muted">服务期范围</small><div>{h(run['service_start_min'] or '-')} 至 {h(run['service_end_max'] or '-')}</div></div>
      <div class="col-md-6"><small class="text-muted">撤回数量</small><div>{run['rollback_count'] or 0}</div></div>
    </div></div></div>
    <div class="card mt-3"><div class="card-header">批次汇总</div><div class="card-body">
    <div class="row text-center g-3">
      <div class="col-md-3"><small class="text-muted">账单笔数</small><div class="fs-5">{summary['count']} 笔</div></div>
      <div class="col-md-3"><small class="text-muted">应收合计</small><div class="fs-5">¥{m(summary['amount'])}</div></div>
      <div class="col-md-3"><small class="text-muted">已收合计</small><div class="fs-5">¥{m(summary['paid'])}</div></div>
      <div class="col-md-3"><small class="text-muted">未收合计</small><div class="fs-5">¥{m(summary['unpaid'])}</div></div>
    </div></div></div>
    <div class="d-flex gap-2 my-3">
      <a class="btn btn-primary" href="/bills?auto_batch_no={h(run['batch_no'])}">查看本批次账单</a>
      <a class="btn btn-outline-warning" href="/reminders?period={h(_run_reminder_period(run))}&status=approaching">查看相关催缴</a>
      {rollback}
      <a class="btn btn-outline-secondary" href="/auto_billing">返回自动出账</a>
    </div>
    <div class="card mb-3"><div class="card-header">按租户/房间分组</div>
    {group_table}</div>
    <div class="card"><div class="card-header">批次账单明细</div>
    {bill_table}</div>'''


def _bill_row_html(bill):
    tenant = bill['tenant_name'] or bill['shop_name'] or bill['owner_name'] or '-'
    room = f"{bill['building'] or ''}-{bill['unit'] or ''}-{bill['room_number'] or ''}"
    status_map = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
    limits = []
    if float(bill['paid'] or 0) > 0 or bill['status'] in ('paid', 'partial'):
        limits.append('已有缴费')
    if int(bill['invoice_count'] or 0) > 0:
        limits.append('已开发票')
    if int(bill['invoice_request_count'] or 0) > 0:
        limits.append('有票据请求')
    return f'''<tr><td>{h(tenant)}</td><td>{h(room)}</td><td>{h(bill['fee_name'] or '-')}</td>
    <td>{h(bill['service_start'] or '-')} 至 {h(bill['service_end'] or '-')}</td><td>{h(bill['due_date'] or '-')}</td>
    <td class="text-end">¥{m(bill['amount'])}</td><td class="text-end">¥{m(bill['paid'])}</td>
    <td>{h(status_map.get(bill['status'], bill['status']))}</td><td>{h('、'.join(limits) or '可撤回')}</td></tr>'''


def _run_status_text(status):
    return {
        'generated': '可撤回',
        'rolled_back': '已撤回',
        'partial_rollback': '部分撤回',
        'blocked': '不可撤回',
    }.get(status or '', status or '-')


def _batch_summary(bills):
    amount = sum(float(b['amount'] or 0) for b in bills)
    paid = sum(float(b['paid'] or 0) for b in bills)
    return {'count': len(bills), 'amount': amount, 'paid': paid, 'unpaid': max(amount - paid, 0)}


def _tenant_room_groups(bills):
    groups = {}
    for bill in bills:
        tenant = bill['tenant_name'] or bill['shop_name'] or bill['owner_name'] or '-'
        room = f"{bill['building'] or ''}-{bill['unit'] or ''}-{bill['room_number'] or ''}"
        key = (tenant, room)
        groups.setdefault(key, {'tenant': tenant, 'room': room, 'count': 0, 'amount': 0.0, 'paid': 0.0})
        groups[key]['count'] += 1
        groups[key]['amount'] += float(bill['amount'] or 0)
        groups[key]['paid'] += float(bill['paid'] or 0)
    return groups.values()


def _group_row_html(group):
    unpaid = max(group['amount'] - group['paid'], 0)
    return f'''<tr><td>{h(group['tenant'])} / {h(group['room'])}</td><td class="text-end">{group['count']} 笔</td>
    <td class="text-end">¥{m(group['amount'])}</td><td class="text-end">¥{m(group['paid'])}</td>
    <td class="text-end">¥{m(unpaid)}</td></tr>'''



def _run_reminder_period(run):
    start = run['service_start_min'] or ''
    return f'{start[:7]}-01' if len(start) >= 7 else ''
