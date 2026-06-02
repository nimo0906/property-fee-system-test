#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant contract based billing preview and confirmation."""

from datetime import date, datetime, timedelta

from server.backups import create_db_backup
from server.base import BaseHandler
from server.billing_engine import calculate_bill_amount, fee_applies_to_room
from server.db import add_months, get_db, h, m, qs


CYCLE_MONTHS = {'monthly': 1, 'quarterly': 3, 'semiannual': 6}
EXCLUDED_AUTO_FEE_NAMES = {'装修管理费', '装修押金', '临时收费'}


def _as_date(value):
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def _months(cycle):
    return CYCLE_MONTHS.get(str(cycle or '').strip(), 1)


def _billing_period(start, end):
    first = f'{start.year}-{start.month:02d}'
    last = f'{end.year}-{end.month:02d}'
    return first if first == last else f'{first}~{last}'


def next_service_period(contract_start, contract_end, cycle, today=None):
    """Return the next complete contract period whose start is after today."""
    start = _as_date(contract_start)
    end = _as_date(contract_end)
    cursor = start
    current = _as_date(today or date.today())
    while cursor <= current:
        cursor = add_months(cursor, _months(cycle))
    service_end = add_months(cursor, _months(cycle)) - timedelta(days=1)
    if service_end > end:
        return None
    return cursor, service_end, cursor - timedelta(days=1)


def _default_fee_ids(db):
    rows = db.execute(
        "SELECT id FROM fee_types WHERE is_active=1 AND name LIKE '物业费(%' ORDER BY sort_order,id"
    ).fetchall()
    return {int(row['id']) for row in rows}


def _candidate_fees(db, fee_ids=None):
    selected = {int(x) for x in fee_ids} if fee_ids else _default_fee_ids(db)
    rows = db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order,id").fetchall()
    return [
        row for row in rows
        if int(row['id']) in selected
        and row['calc_method'] != 'meter'
        and (row['name'] or '') not in EXCLUDED_AUTO_FEE_NAMES
    ]


def _selectable_fees(db):
    return [
        row for row in db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order,id").fetchall()
        if row['calc_method'] != 'meter' and (row['name'] or '') not in EXCLUDED_AUTO_FEE_NAMES
    ]


def _ids_from_form(data):
    raw = data.get('fee_ids', []) if data else []
    if isinstance(raw, str):
        raw = [raw]
    return [int(x) for x in raw if str(x).isdigit()]


def build_auto_billing_preview(db, today=None, advance_days=30, fee_ids=None):
    current = _as_date(today or date.today())
    cutoff = current + timedelta(days=max(0, int(advance_days or 30)))
    fees = _candidate_fees(db, fee_ids)
    rooms = db.execute(
        """SELECT r.*,o.name owner_name FROM rooms r
        LEFT JOIN owners o ON o.id=r.owner_id
        WHERE COALESCE(r.contract_start,'')<>'' AND COALESCE(r.contract_end,'')<>''
        ORDER BY r.building,r.unit,r.room_number"""
    ).fetchall()
    items = []
    for room in rooms:
        try:
            service = next_service_period(
                room['contract_start'], room['contract_end'], room['payment_cycle'], current
            )
        except ValueError:
            continue
        if not service or service[0] > cutoff:
            continue
        service_start, service_end, due_date = service
        months = _months(room['payment_cycle'])
        period = _billing_period(service_start, service_end)
        for fee in fees:
            if not fee_applies_to_room(fee['name'] or '', room):
                continue
            calc = calculate_bill_amount(db, room, fee, period, months)
            if calc['amount'] <= 0:
                continue
            exists = db.execute(
                """SELECT id FROM bills WHERE room_id=? AND fee_type_id=?
                AND ((service_start=? AND service_end=?)
                  OR ((service_start IS NULL OR service_start='') AND billing_period=?))""",
                (room['id'], fee['id'], service_start.isoformat(), service_end.isoformat(), period)
            ).fetchone()
            items.append({
                'item_key': f"{room['id']}:{fee['id']}:{service_start.isoformat()}:{service_end.isoformat()}",
                'room_id': room['id'], 'fee_type_id': fee['id'],
                'room_name': f"{room['building']}-{room['unit']}-{room['room_number']}",
                'tenant_name': room['tenant_name'] or room['shop_name'] or room['owner_name'] or '-',
                'fee_name': fee['name'], 'cycle': room['payment_cycle'] or 'monthly',
                'service_start': service_start.isoformat(), 'service_end': service_end.isoformat(),
                'due_date': due_date.isoformat(), 'billing_period': period,
                'amount': calc['amount'], 'can_generate': not bool(exists),
            })
    return items


def confirm_auto_billing(db, item_keys, today=None, advance_days=30, fee_ids=None, operator='管理员'):
    return create_auto_billing_run(db, item_keys, today=today, advance_days=advance_days, fee_ids=fee_ids, operator=operator)


def create_auto_billing_run(db, item_keys, today=None, advance_days=30, fee_ids=None, operator='管理员'):
    selected = set(item_keys or [])
    preview = build_auto_billing_preview(db, today=today, advance_days=advance_days, fee_ids=fee_ids)
    generated = skipped_existing = 0
    batch_no = f"AUTO-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    generated_items = []
    for item in preview:
        if item['item_key'] not in selected:
            continue
        if not item['can_generate']:
            skipped_existing += 1
            continue
        room = db.execute("SELECT * FROM rooms WHERE id=?", (item['room_id'],)).fetchone()
        seq = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period=?", (item['billing_period'],)).fetchone()[0] + 1
        bill_number = f"AUTO_{room['building']}-{room['room_number']}_{item['billing_period'].replace('~','-')}_{seq:04d}"
        db.execute(
            """INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,
            bill_number,source,source_ref,service_start,service_end,auto_batch_no)
            VALUES(?,?,?,?,?,?,'unpaid',?,'auto_contract',?,?,?,?)""",
            (item['room_id'], room['owner_id'], item['fee_type_id'], item['billing_period'],
             item['amount'], item['due_date'], bill_number, item['item_key'],
             item['service_start'], item['service_end'], batch_no)
        )
        generated_items.append(item)
        generated += 1
    if generated:
        db.execute(
            """INSERT INTO auto_billing_runs(batch_no,operator,advance_days,fee_ids,generated_count,
            service_start_min,service_end_max,status) VALUES(?,?,?,?,?,?,?,'generated')""",
            (batch_no, operator, int(advance_days or 30), ','.join(str(x) for x in (fee_ids or [])),
             generated, min(x['service_start'] for x in generated_items), max(x['service_end'] for x in generated_items))
        )
    db.commit()
    return {'generated': generated, 'skipped_existing': skipped_existing, 'batch_no': batch_no if generated else ''}


def rollback_auto_billing_batch(db, batch_no):
    rows = db.execute(
        """SELECT b.*,COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid,
        (SELECT COUNT(*) FROM invoices WHERE bill_id=b.id) invoice_count,
        (SELECT COUNT(*) FROM invoice_requests WHERE bill_id=b.id) invoice_request_count
        FROM bills b WHERE b.auto_batch_no=? AND b.source='auto_contract' ORDER BY b.id""",
        (batch_no,)
    ).fetchall()
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


def recent_auto_billing_runs(db, limit=8):
    return db.execute(
        "SELECT * FROM auto_billing_runs ORDER BY created_at DESC,id DESC LIMIT ?",
        (int(limit),)
    ).fetchall()


def _run_row_html(run):
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
    <td><a class="btn btn-sm btn-outline-primary" href="/bills?source=auto_contract">查看账单</a> {rollback}</td></tr>'''


class AutoBillingMixin(BaseHandler):
    def _auto_billing(self, q):
        advance_days = int(qs(q, 'advance_days', 30) or 30)
        db = get_db()
        selected_fee_ids = _ids_from_form(q) or _default_fee_ids(db)
        fee_options = _selectable_fees(db)
        items = build_auto_billing_preview(db, advance_days=advance_days, fee_ids=selected_fee_ids)
        runs = recent_auto_billing_runs(db)
        db.close()
        fee_checks = ''.join(
            f'''<label class="form-check form-check-inline mb-2">
                <input class="form-check-input" type="checkbox" name="fee_ids" value="{f['id']}"
                    {"checked" if int(f['id']) in selected_fee_ids else ""}>
                <span class="form-check-label">{h(f['name'])}</span>
            </label>'''
            for f in fee_options
        )
        hidden_fee_ids = ''.join(f'<input type="hidden" name="fee_ids" value="{fid}">' for fid in selected_fee_ids)
        rows = ''.join(
            f'''<tr><td><input type="checkbox" name="item_keys" value="{h(x['item_key'])}"
                {"checked" if x["can_generate"] else "disabled"}></td>
            <td>{h(x["tenant_name"])}</td><td>{h(x["room_name"])}</td><td>{h(x["fee_name"])}</td>
            <td>{h(x["service_start"])} 至 {h(x["service_end"])}</td><td>{h(x["due_date"])}</td>
            <td class="text-end">¥{m(x["amount"])}</td>
            <td>{"可生成" if x["can_generate"] else "已存在"}</td></tr>'''
            for x in items
        ) or '<tr><td colspan="8" class="text-center text-muted py-4">未来指定天数内暂无需要生成的租户账单</td></tr>'
        run_rows = ''.join(_run_row_html(r) for r in runs) or '<tr><td colspan="7" class="text-center text-muted py-3">暂无自动出账记录</td></tr>'
        body = f'''
        <div class="alert alert-info">根据租户合同起止日期和缴费周期计算下一期服务日期。这里只做预览，确认后才写入账单；默认只生成适用的物业费，不影响原有手动收费。</div>
        <form method="GET" action="/auto_billing" class="row g-2 mb-3">
          <div class="col-auto"><label class="col-form-label">提前出账天数</label></div>
          <div class="col-auto"><input type="number" class="form-control" name="advance_days" min="0" max="365" value="{advance_days}"></div>
          <div class="col-12">
            <div class="card"><div class="card-header py-2">收费项目选择</div>
            <div class="card-body py-2">{fee_checks}</div></div>
          </div>
          <div class="col-auto"><button class="btn btn-primary">刷新预览</button></div>
        </form>
        <form method="POST" action="/auto_billing/confirm" onsubmit="return confirm('确认生成选中的租户账单？')">
          <input type="hidden" name="advance_days" value="{advance_days}">
          {hidden_fee_ids}
          <div class="table-responsive"><table class="table table-hover align-middle small">
          <thead><tr><th>选择</th><th>租户</th><th>房间/铺位</th><th>收费项目</th><th>服务期</th><th>缴费截止日</th><th class="text-end">金额</th><th>状态</th></tr></thead>
          <tbody>{rows}</tbody></table></div>
          <button class="btn btn-success"><i class="bi bi-check2-circle"></i> 确认生成选中账单</button>
        </form>
        <div class="card mt-3"><div class="card-header">最近自动出账记录</div>
        <div class="table-responsive"><table class="table table-hover align-middle small mb-0">
        <thead><tr><th>批次号</th><th>生成时间</th><th>操作人</th><th class="text-end">笔数</th><th>服务期范围</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>{run_rows}</tbody></table></div></div>'''
        self._html(self._page('自动出账预览', body, 'auto_billing'))

    def _auto_billing_confirm(self, d):
        keys = d.get('item_keys', [])
        if isinstance(keys, str):
            keys = [keys]
        if not keys:
            return self._redirect('/auto_billing?flash=请勾选要生成的账单')
        advance_days = int(qs(d, 'advance_days', 30) or 30)
        fee_ids = _ids_from_form(d)
        create_db_backup('auto_before_contract_billing')
        db = get_db()
        user = self._get_current_user() or {}
        result = confirm_auto_billing(db, keys, advance_days=advance_days, fee_ids=fee_ids, operator=user.get('display_name') or user.get('username') or '管理员')
        db.close()
        self._audit('auto_billing_confirm', 'bill', None, None, result, '租户合同自动出账确认')
        msg = f"已生成{result['generated']}笔账单"
        if result['skipped_existing']:
            msg += f"，跳过{result['skipped_existing']}笔已存在账单"
        self._redirect('/bills', msg)

    def _auto_billing_rollback(self, batch_no):
        create_db_backup('auto_before_contract_billing_rollback')
        db = get_db()
        result = rollback_auto_billing_batch(db, batch_no)
        db.close()
        self._audit('auto_billing_rollback', 'auto_billing_run', None, {'batch_no': batch_no}, result, '撤回自动出账未缴账单')
        self._redirect('/auto_billing', f"已撤回{result['deleted']}笔未缴账单，保留{result['blocked']}笔不可撤回账单")
