#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant contract based billing preview and confirmation."""

from datetime import date, datetime, timedelta

from server.backups import create_db_backup
from server.base import BaseHandler
from server.auto_billing_runs import (
    get_auto_billing_run, get_auto_billing_run_bills, recent_auto_billing_runs,
    rollback_auto_billing_batch, run_detail_html,
)
from server.auto_billing_page import render_auto_billing_page
from server.billing_engine import calculate_bill_amount, fee_applies_to_room
from server.db import add_months, get_db, h, m, qs


CYCLE_MONTHS = {'monthly': 1, 'quarterly': 3, 'semiannual': 6, 'yearly': 12}
EXCLUDED_AUTO_FEE_NAMES = {'装修管理费', '装修押金', '临时收费'}


def _as_date(value):
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def _months(cycle):
    return CYCLE_MONTHS.get(str(cycle or '').strip(), 1)


def _effective_cycle(room, period_cycle=None):
    override = str(period_cycle or '').strip()
    if override in CYCLE_MONTHS:
        return override
    return room['payment_cycle'] or 'monthly'


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


def build_auto_billing_preview(db, today=None, advance_days=30, fee_ids=None, period_cycle=None):
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
            schedule_cycle = room['payment_cycle'] or 'monthly'
            cycle = _effective_cycle(room, period_cycle)
            service = next_service_period(
                room['contract_start'], room['contract_end'], schedule_cycle, current
            )
        except ValueError:
            continue
        if not service or service[0] > cutoff:
            continue
        service_start, _schedule_end, due_date = service
        months = _months(cycle)
        service_end = add_months(service_start, months) - timedelta(days=1)
        if service_end > _as_date(room['contract_end']):
            continue
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
                'fee_name': fee['name'], 'cycle': cycle,
                'service_start': service_start.isoformat(), 'service_end': service_end.isoformat(),
                'due_date': due_date.isoformat(), 'billing_period': period,
                'amount': calc['amount'], 'can_generate': not bool(exists),
            })
    return items


def confirm_auto_billing(db, item_keys, today=None, advance_days=30, fee_ids=None, operator='管理员', period_cycle=None):
    return create_auto_billing_run(db, item_keys, today=today, advance_days=advance_days, fee_ids=fee_ids, operator=operator, period_cycle=period_cycle)


def create_auto_billing_run(db, item_keys, today=None, advance_days=30, fee_ids=None, operator='管理员', period_cycle=None):
    selected = set(item_keys or [])
    preview = build_auto_billing_preview(db, today=today, advance_days=advance_days, fee_ids=fee_ids, period_cycle=period_cycle)
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


class AutoBillingMixin(BaseHandler):
    def _auto_billing(self, q):
        advance_days = int(qs(q, 'advance_days', 30) or 30)
        period_cycle = qs(q, 'period_cycle', 'tenant') or 'tenant'
        db = get_db()
        selected_fee_ids = _ids_from_form(q) or _default_fee_ids(db)
        preview_status = qs(q, 'preview_status', 'all') or 'all'
        fee_options = _selectable_fees(db)
        items = build_auto_billing_preview(db, advance_days=advance_days, fee_ids=selected_fee_ids, period_cycle=period_cycle)
        if preview_status == 'can_generate':
            items = [x for x in items if x['can_generate']]
        elif preview_status == 'existing':
            items = [x for x in items if not x['can_generate']]
        runs = recent_auto_billing_runs(db)
        db.close()
        body = render_auto_billing_page(advance_days, fee_options, selected_fee_ids, items, runs, preview_status, period_cycle)
        self._html(self._page('自动出账预览', body, 'auto_billing'))

    def _auto_billing_run_detail(self, batch_no):
        db = get_db()
        run = get_auto_billing_run(db, batch_no)
        if not run:
            db.close()
            return self._error(404, '自动出账批次不存在')
        bills = get_auto_billing_run_bills(db, batch_no)
        db.close()
        self._html(self._page('自动出账批次详情', run_detail_html(run, bills), 'auto_billing'))

    def _auto_billing_confirm(self, d):
        keys = d.get('item_keys', [])
        if isinstance(keys, str):
            keys = [keys]
        if not keys:
            return self._redirect('/auto_billing?flash=请勾选要生成的账单')
        advance_days = int(qs(d, 'advance_days', 30) or 30)
        period_cycle = qs(d, 'period_cycle', 'tenant') or 'tenant'
        fee_ids = _ids_from_form(d)
        if qs(d, 'confirm') != '1':
            return self._auto_billing_confirm_preview(keys, advance_days, fee_ids, period_cycle)
        create_db_backup('auto_before_contract_billing')
        db = get_db()
        user = self._get_current_user() or {}
        result = confirm_auto_billing(db, keys, advance_days=advance_days, fee_ids=fee_ids, operator=user.get('display_name') or user.get('username') or '管理员', period_cycle=period_cycle)
        db.close()
        self._audit('auto_billing_confirm', 'bill', None, None, result, '租户合同自动出账确认')
        msg = f"已生成{result['generated']}笔账单"
        if result['skipped_existing']:
            msg += f"，跳过{result['skipped_existing']}笔已存在账单"
        self._redirect(f"/auto_billing/runs/{result['batch_no']}" if result['batch_no'] else '/bills', msg)

    def _auto_billing_confirm_preview(self, keys, advance_days, fee_ids, period_cycle):
        selected = set(keys)
        db = get_db()
        items = [x for x in build_auto_billing_preview(db, advance_days=advance_days, fee_ids=fee_ids, period_cycle=period_cycle) if x['item_key'] in selected]
        db.close()
        can_items = [x for x in items if x['can_generate']]
        skipped = len(items) - len(can_items)
        total = sum(float(x['amount'] or 0) for x in can_items)
        hidden_keys = ''.join(f'<input type="hidden" name="item_keys" value="{h(k)}">' for k in keys)
        hidden_fees = ''.join(f'<input type="hidden" name="fee_ids" value="{fid}">' for fid in fee_ids)
        rows = ''.join(
            f'''<tr><td>{h(x['tenant_name'])}</td><td>{h(x['room_name'])}</td><td>{h(x['fee_name'])}</td>
            <td>{h(x['service_start'])} 至 {h(x['service_end'])}</td><td>{h(x['due_date'])}</td>
            <td class="text-end">¥{m(x['amount'])}</td><td>{'将生成' if x['can_generate'] else '已存在，跳过'}</td></tr>'''
            for x in items
        ) or '<tr><td colspan="7" class="text-center text-muted py-4">没有可确认的账单</td></tr>'
        body = f'''
        <div class="alert alert-warning">请核对以下自动出账内容。确认后才会写入账单；系统会先自动备份，已存在的账单不会重复生成。</div>
        <div class="card mb-3"><div class="card-header">确认汇总</div><div class="card-body">
          <div class="row text-center g-3">
            <div class="col-md-3"><small class="text-muted">生成账单</small><div class="fs-5">将生成 {len(can_items)} 笔账单</div></div>
            <div class="col-md-3"><small class="text-muted">跳过已存在</small><div class="fs-5">{skipped} 笔</div></div>
            <div class="col-md-3"><small class="text-muted">应收合计</small><div class="fs-5">¥{m(total)}</div></div>
            <div class="col-md-3"><small class="text-muted">提前天数</small><div class="fs-5">{advance_days} 天</div></div>
          </div>
        </div></div>
        <div class="table-responsive"><table class="table table-hover align-middle small">
        <thead><tr><th>租户</th><th>房间/铺位</th><th>收费项目</th><th>服务期</th><th>缴费截止日</th><th class="text-end">金额</th><th>状态</th></tr></thead>
        <tbody>{rows}</tbody></table></div>
        <form method="POST" action="/auto_billing/confirm" class="d-inline">
          <input type="hidden" name="confirm" value="1">
          <input type="hidden" name="advance_days" value="{advance_days}">
          <input type="hidden" name="period_cycle" value="{h(period_cycle)}">
          {hidden_keys}{hidden_fees}
          <button class="btn btn-success" {'disabled' if not can_items else ''}>确认写入账单</button>
        </form>
        <a class="btn btn-outline-secondary" href="/auto_billing?advance_days={advance_days}&period_cycle={h(period_cycle)}">返回修改</a>'''
        self._html(self._page('自动出账确认', body, 'auto_billing'))

    def _auto_billing_rollback(self, batch_no):
        create_db_backup('auto_before_contract_billing_rollback')
        db = get_db()
        result = rollback_auto_billing_batch(db, batch_no)
        db.close()
        self._audit('auto_billing_rollback', 'auto_billing_run', None, {'batch_no': batch_no}, result, '撤回自动出账未缴账单')
        self._redirect('/auto_billing', f"已撤回{result['deleted']}笔未缴账单，保留{result['blocked']}笔不可撤回账单")
