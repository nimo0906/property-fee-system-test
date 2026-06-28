#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared expense allocation for internal v1.0 use."""

import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta

from server.base import BaseHandler
from server.bill_snapshots import room_snapshot, apply_snapshot
from server.backups import create_db_backup
from server.data_health import cleanup_invalid_payments
from server.db import get_db, get_period, h, m, qs, is_period_closed, room_active_in_period, date_to_period, period_to_date, add_months
from server.billing_engine import fee_applies_to_room
from server.money import MONEY_QUANT, money_decimal
from server.ui_components import render_table


def allocate_shared_amount(total_amount, rooms, method='area'):
    total = money_decimal(total_amount)
    if total <= 0 or not rooms:
        return []
    weights = []
    for r in rooms:
        weight = Decimal('1') if method == 'household' else Decimal(str(r['area'] or 0))
        weights.append(max(weight, Decimal('0')))
    weight_sum = sum(weights)
    if weight_sum <= 0:
        weights = [Decimal('1') for _ in rooms]
        weight_sum = Decimal(len(rooms))
    allocations = []
    running = Decimal('0')
    for idx, (room, weight) in enumerate(zip(rooms, weights)):
        if idx == len(rooms) - 1:
            amount = total - running
        else:
            amount = (total * weight / weight_sum).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            running += amount
        allocations.append({'room': room, 'amount': float(amount), 'weight': float(weight)})
    return allocations


def _period_label(start_str, end_str):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        ed = datetime.strptime(end_str, '%Y-%m-%d').date()
        if sd.year == ed.year and sd.month == ed.month:
            return f'{sd.year}-{sd.month:02d}'
        return f'{sd.year}-{sd.month:02d}~{ed.year}-{ed.month:02d}'
    except Exception:
        return get_period()


def _resolve_shared_period(data):
    start = qs(data, 'period_start', '').strip()
    end = qs(data, 'period_end', '').strip()
    raw_period = qs(data, 'period', '').strip()
    if raw_period and not start and not end:
        start = period_to_date(date_to_period(raw_period))
        try:
            y, mo = [int(x) for x in start[:7].split('-')]
            end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
        except Exception:
            end = start
    if not start:
        start = period_to_date(get_period())
    if not end:
        try:
            y, mo = [int(x) for x in start[:7].split('-')]
            end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
        except Exception:
            end = start
    if end < start:
        start, end = end, start
    return start, end, _period_label(start, end)


def _room_active_in_date_range(room, start_str, end_str):
    try:
        period_start = datetime.strptime(start_str, '%Y-%m-%d').date()
        period_end = datetime.strptime(end_str, '%Y-%m-%d').date()
    except Exception:
        return True
    start = room['contract_start'] if 'contract_start' in room.keys() else None
    end = room['contract_end'] if 'contract_end' in room.keys() else None
    try:
        if start and datetime.strptime(start[:10], '%Y-%m-%d').date() > period_end:
            return False
        if end and datetime.strptime(end[:10], '%Y-%m-%d').date() < period_start:
            return False
    except Exception:
        return True
    return True


def shared_expense_rooms(db, fee_type, period, building='', unit='', category='', period_start='', period_end=''):
    cond = []
    vals = []
    if building:
        cond.append('building=?'); vals.append(building)
    commercial_scope = unit == '__commercial__'
    if commercial_scope:
        cond.append("unit='商场'")
        cond.append("category IN ('商户','商业')")
    elif unit:
        cond.append('unit=?'); vals.append(unit)
    if category:
        cond.append('category=?'); vals.append(category)
    sql = 'SELECT * FROM rooms'
    if cond:
        sql += ' WHERE ' + ' AND '.join(cond)
    sql += ' ORDER BY building,unit,room_number'
    rooms = db.execute(sql, vals).fetchall()
    return [
        r for r in rooms
        if fee_applies_to_room(fee_type['name'] or '', r)
        and (_room_active_in_date_range(r, period_start, period_end) if period_start and period_end else room_active_in_period(r, period))
    ]


class SharedExpenseMixin(BaseHandler):

    def _shared_expenses(self, q=None):
        q = q or {}
        db = get_db()
        fts = db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order").fetchall()
        blds = db.execute("SELECT DISTINCT building FROM rooms ORDER BY building").fetchall()
        units = db.execute("SELECT DISTINCT unit FROM rooms WHERE unit IS NOT NULL AND unit<>'' ORDER BY unit").fetchall()
        cats = db.execute("SELECT DISTINCT category FROM rooms WHERE category IS NOT NULL AND category<>'' ORDER BY category").fetchall()
        recent = db.execute('''SELECT s.*,f.name fee_name FROM shared_expense_runs s LEFT JOIN fee_types f ON s.fee_type_id=f.id
            ORDER BY s.created_at DESC,s.id DESC LIMIT 10''').fetchall()
        db.close()
        fee_opts = ''.join(f'<option value="{f["id"]}"{" selected" if "公摊" in (f["name"] or "") else ""}>{h(f["name"])} - {h(f["calc_method"])}</option>' for f in fts)
        bld_opts = '<option value="">全部楼栋</option>' + ''.join(f'<option value="{h(r["building"])}">{h(r["building"])}</option>' for r in blds)
        unit_opts = '<option value="">全部单元/区域</option><option value="__commercial__">商业部分</option>' + ''.join(f'<option value="{h(r["unit"])}">{h(r["unit"])}</option>' for r in units if r["unit"] != '商场')
        cat_opts = '<option value="">全部类别</option>' + ''.join(f'<option value="{h(r["category"])}">{h(r["category"])}</option>' for r in cats)
        recent_rows = ''.join(
            f'''<tr><td>{h(r["created_at"])}</td><td>{h(r["period"])}</td><td>{h(r["fee_name"] or r["fee_type_id"])}</td>
            <td>{"按面积" if r["allocation_method"]=="area" else "按户数"}</td><td class="text-end">{r["room_count"]}</td><td class="text-end money">¥{m(r["total_amount"])}</td></tr>'''
            for r in recent
        )
        recent_table = render_table(
            ['时间', '账期', '项目', '方式', ('户数', 'text-end'), ('总额', 'text-end')],
            recent_rows,
            table_class='table table-sm mb-0',
            empty_text='暂无公摊记录',
        )
        default_start, default_end, _ = _resolve_shared_period(q)
        self._html(self._page('公摊分摊', f'''
        <div class="page-intro">
          <div>
            <h2 class="mb-1">公摊分摊</h2>
            <div class="small text-muted">按财务自然日期范围生成公摊账单</div>
          </div>
          <div class="export-actions">
            <a class="btn btn-outline-secondary btn-sm" href="/bills"><i class="bi bi-receipt"></i> 账单管理</a>
          </div>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-md-3 col-6"><div class="summary-tile primary"><div class="label">最近记录</div><strong>{len(recent)}</strong></div></div>
          <div class="col-md-3 col-6"><div class="summary-tile"><div class="label">默认起始</div><strong>{h(default_start)}</strong></div></div>
          <div class="col-md-3 col-6"><div class="summary-tile success"><div class="label">默认截止</div><strong>{h(default_end)}</strong></div></div>
          <div class="col-md-3 col-6"><div class="summary-tile warning"><div class="label">最近总额</div><strong class="money">¥{m(sum(float(r["total_amount"] or 0) for r in recent))}</strong></div></div>
        </div>
        <div class="card mb-3">
          <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><span><i class="bi bi-funnel"></i> 分摊条件</span></div>
          <div class="card-body">
            <form method="POST" action="/shared_expenses/allocate" class="row g-3">
                <div class="col-md-3"><label class="form-label small text-muted mb-1">起始日期 *</label><input type="date" name="period_start" class="form-control form-control-sm" value="{h(default_start)}" required></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">截止日期 *</label><input type="date" name="period_end" class="form-control form-control-sm" value="{h(default_end)}" required></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">收费项目 *</label><select name="fee_type_id" class="form-select form-select-sm" required>{fee_opts}</select></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">公摊总金额 *</label><div class="input-group input-group-sm"><span class="input-group-text">¥</span><input name="total_amount" type="number" step="0.1" min="0.1" class="form-control" required></div></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">分摊方式</label><select name="allocation_method" class="form-select form-select-sm"><option value="area">按面积分摊</option><option value="household">按户数平均</option></select></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">楼栋</label><select name="building" class="form-select form-select-sm">{bld_opts}</select></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">单元/区域</label><select name="unit" class="form-select form-select-sm">{unit_opts}</select></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">类别</label><select name="category" class="form-select form-select-sm">{cat_opts}</select></div>
                <div class="col-md-3"><label class="form-label small text-muted mb-1">说明</label><input name="notes" class="form-control form-control-sm" placeholder="如：5月公共电费"></div>
                <div class="col-12 d-flex gap-2"><button name="mode" value="preview" class="btn btn-primary">预览分摊</button><button name="mode" value="confirm" class="btn btn-success">确认生成账单</button></div>
            </form>
          </div>
        </div>
        <div class="card mt-4"><div class="card-header">最近公摊记录</div>{recent_table}</div>
        ''', 'shared_expenses'))

    def _shared_expense_allocate(self, d):
        legacy_period_input = bool(qs(d, 'period', '').strip() and not qs(d, 'period_start', '').strip() and not qs(d, 'period_end', '').strip())
        period_start, period_end, period = _resolve_shared_period(d)
        if is_period_closed(period):
            return self._redirect('/shared_expenses?flash=' + period + '已结账，无法生成公摊账单')
        fid = int(qs(d, 'fee_type_id', '0') or 0)
        total = float(qs(d, 'total_amount', '0') or 0)
        method = qs(d, 'allocation_method', 'area')
        building = qs(d, 'building')
        unit = qs(d, 'unit')
        category = qs(d, 'category')
        due_day = int(qs(d, 'due_day', '28') or 28)
        due_day = min(28, max(1, due_day))
        notes = qs(d, 'notes')
        db = get_db()
        ft = db.execute('SELECT * FROM fee_types WHERE id=? AND is_active=1', (fid,)).fetchone()
        if not ft:
            db.close(); return self._redirect('/shared_expenses?flash=收费项目不存在')
        rooms = shared_expense_rooms(db, ft, period, building, unit, category, period_start, period_end)
        existing = {row[0] for row in db.execute('SELECT room_id FROM bills WHERE billing_period=? AND fee_type_id=?', (period, fid)).fetchall()}
        rooms = [r for r in rooms if r['id'] not in existing]
        allocations = allocate_shared_amount(total, rooms, method)
        if not allocations:
            db.close(); return self._redirect('/shared_expenses?flash=没有可分摊房间或金额无效')
        if qs(d, 'mode') == 'preview':
            db.close(); return self._render_shared_preview(period, fid, total, method, building, unit, category, due_day, notes, allocations, len(existing), period_start, period_end)
        backup_name = create_db_backup('auto_before_bill_generation')
        cleanup_invalid_payments(db)
        due_date = f'{period[:4]}-{period[5:7]}-{due_day:02d}' if legacy_period_input and '~' not in period else period_end
        run = db.execute('''INSERT INTO shared_expense_runs(period,fee_type_id,total_amount,allocation_method,building,category,room_count,operator,notes)
            VALUES(?,?,?,?,?,?,?,?,?)''', (period, fid, total, method, building, category, len(allocations), (self._get_current_user() or {}).get('username',''), notes))
        run_id = run.lastrowid
        bill_ids = []
        seq_base = db.execute('SELECT COUNT(*) FROM bills WHERE billing_period=?', (period,)).fetchone()[0]
        for idx, a in enumerate(allocations, 1):
            r = a['room']; amount = a['amount']
            oname_row = db.execute('SELECT name FROM owners WHERE id=?', (r['owner_id'],)).fetchone()
            oname = ((oname_row[0] if oname_row else '未知') or '未知')[:10]
            bn = f'{r["building"]}-{r["room_number"]}_{oname}_{period}_GT{run_id}_{idx:04d}'
            cur = db.execute('''INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,source_ref,notes,service_start,service_end)
                VALUES(?,?,?,?,?,?,'unpaid',?,'shared_expense',?,?,?,?)''', (r['id'], r['owner_id'], fid, period, amount, due_date, bn, str(run_id), notes, period_start, period_end))
            apply_snapshot(db, cur.lastrowid, room_snapshot(db, r['id'], r['owner_id']))
            bill_ids.append(cur.lastrowid)
        db.execute('UPDATE shared_expense_runs SET generated_bill_ids=? WHERE id=?', (json.dumps(bill_ids), run_id))
        db.commit(); db.close()
        self._audit('shared_expense_generate', 'shared_expense_run', run_id, None, {'period': period, 'fee_type_id': fid, 'total': total, 'bill_ids': bill_ids}, notes)
        return self._render_shared_result(period, total, method, allocations, backup_name, bill_ids, period_start, period_end, not legacy_period_input)

    def _render_shared_preview(self, period, fid, total, method, building, unit, category, due_day, notes, allocations, skipped, period_start='', period_end=''):
        rows = ''.join(f'<tr><td>{h(a["room"]["building"])}-{h(a["room"]["unit"] or "")}-{h(a["room"]["room_number"])}</td><td>{h(a["room"]["category"])}</td><td class="text-end">{m(a["weight"])}</td><td class="text-end money">¥{m(a["amount"])}</td></tr>' for a in allocations[:80])
        detail_table = render_table(
            ['房间', '类别', ('权重', 'text-end'), ('金额', 'text-end')],
            rows,
            table_class='table table-sm mb-0',
        )
        hidden = ''.join(f'<input type="hidden" name="{k}" value="{h(v)}">' for k, v in {'period':period,'period_start':period_start,'period_end':period_end,'fee_type_id':fid,'total_amount':total,'allocation_method':method,'building':building,'unit':unit,'category':category,'due_day':due_day,'notes':notes}.items())
        self._html(self._page('公摊分摊预览', f'''
        <div class="page-intro">
          <div>
            <h2 class="mb-1">公摊分摊预览</h2>
          </div>
        </div>
        <div class="row g-2 mb-3"><div class="col-md-4 col-6"><div class="summary-tile"><div class="label">房间数</div><strong>{len(allocations)}</strong></div></div><div class="col-md-4 col-6"><div class="summary-tile primary"><div class="label">总金额</div><strong class="money">¥{m(total)}</strong></div></div><div class="col-md-4 col-6"><div class="summary-tile success"><div class="label">分摊合计</div><strong class="money">¥{m(sum(a["amount"] for a in allocations))}</strong></div></div></div>
        <div class="card mb-3"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><span><i class="bi bi-eye"></i> 预览结果</span></div><div class="card-body"><div class="table-responsive">{detail_table}</div></div></div>
        <form method="POST" action="/shared_expenses/allocate" class="mt-3"><input type="hidden" name="mode" value="confirm">{hidden}<div class="d-flex justify-content-end gap-2"><button class="btn btn-success btn-lg">确认生成公摊账单</button> <a class="btn btn-outline-secondary btn-lg" href="/shared_expenses">返回修改</a></div></form>
        ''', 'shared_expenses'))

    def _render_shared_result(self, period, total, method, allocations, backup_name, bill_ids, period_start='', period_end='', use_range_links=True):
        query = f'period_start={h(period_start)}&amp;period_end={h(period_end)}' if use_range_links and period_start and period_end else f'period={h(period)}'
        self._html(self._page('公摊分摊结果', f'''
        <div class="page-intro">
          <div>
            <h2 class="mb-1">公摊分摊完成</h2>
          </div>
        </div>
        <div class="row g-2 mb-3"><div class="col-md-4 col-6"><div class="summary-tile primary"><div class="label">生成笔数</div><strong>{len(bill_ids)}</strong></div></div><div class="col-md-4 col-6"><div class="summary-tile success"><div class="label">总金额</div><strong class="money">¥{m(sum(a['amount'] for a in allocations))}</strong></div></div><div class="col-md-4 col-6"><div class="summary-tile warning"><div class="label">自动备份</div><strong>{h(backup_name)}</strong></div></div></div>
        <div class="card mb-3"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><span><i class="bi bi-check-circle"></i> 公摊生成完成</span></div><div class="card-body"><div class="alert alert-success mb-2">公摊账单生成完成：{len(bill_ids)} 笔，合计 ¥{m(sum(a['amount'] for a in allocations))}。</div><div class="alert alert-light border mb-2"><strong>自动备份：</strong><code>{h(backup_name)}</code></div></div></div>
        <div class="export-actions"><a class="btn btn-primary" href="/bills?{query}">查看账单</a><a class="btn btn-outline-success" href="/bills/export_generated?ids={h(','.join(str(x) for x in bill_ids))}">导出本次公摊CSV</a><a class="btn btn-outline-secondary" href="/shared_expenses">继续分摊</a></div>
        ''', 'shared_expenses'))
