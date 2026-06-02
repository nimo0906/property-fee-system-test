#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto billing batch query, detail, and rollback helpers."""

from server.db import h, m


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
    <td><span class="badge bg-{badge}">{h(run['status'])}</span></td>
    <td><a class="btn btn-sm btn-outline-primary" href="/auto_billing/runs/{h(run['batch_no'])}">查看详情</a> {rollback}</td></tr>'''


def run_detail_html(run, bills):
    if not run:
        return ''
    bill_rows = ''.join(_bill_row_html(b) for b in bills)
    if not bill_rows:
        bill_rows = '<tr><td colspan="9" class="text-center text-muted py-4">本批次账单已全部撤回或不存在</td></tr>'
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
      <div class="col-md-2"><small class="text-muted">状态</small><div>{h(run['status'])}</div></div>
      <div class="col-md-6"><small class="text-muted">服务期范围</small><div>{h(run['service_start_min'] or '-')} 至 {h(run['service_end_max'] or '-')}</div></div>
      <div class="col-md-6"><small class="text-muted">撤回数量</small><div>{run['rollback_count'] or 0}</div></div>
    </div></div></div>
    <div class="d-flex gap-2 my-3">
      <a class="btn btn-primary" href="/bills?auto_batch_no={h(run['batch_no'])}">查看本批次账单</a>
      {rollback}
      <a class="btn btn-outline-secondary" href="/auto_billing">返回自动出账</a>
    </div>
    <div class="card"><div class="card-header">批次账单明细</div>
    <div class="table-responsive"><table class="table table-hover align-middle small mb-0">
    <thead><tr><th>租户</th><th>房间/铺位</th><th>收费项目</th><th>服务期</th><th>截止日</th><th class="text-end">金额</th><th class="text-end">已缴</th><th>状态</th><th>限制</th></tr></thead>
    <tbody>{bill_rows}</tbody></table></div></div>'''


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
