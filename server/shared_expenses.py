#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared expense allocation for internal v1.0 use."""

import json
from decimal import Decimal, ROUND_HALF_UP

from server.base import BaseHandler
from server.backups import create_db_backup
from server.db import get_db, get_period, h, m, qs, is_period_closed, room_active_in_period, date_to_period, period_to_date
from server.billing_engine import fee_applies_to_room


def allocate_shared_amount(total_amount, rooms, method='area'):
    total = Decimal(str(total_amount or 0)).quantize(Decimal('0.01'))
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
            amount = (total * weight / weight_sum).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            running += amount
        allocations.append({'room': room, 'amount': float(amount), 'weight': float(weight)})
    return allocations


def shared_expense_rooms(db, fee_type, period, building='', unit='', category=''):
    cond = []
    vals = []
    if building:
        cond.append('building=?'); vals.append(building)
    if unit:
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
        if fee_applies_to_room(fee_type['name'] or '', r) and room_active_in_period(r, period)
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
        unit_opts = '<option value="">全部单元/座</option>' + ''.join(f'<option value="{h(r["unit"])}">{h(r["unit"])}</option>' for r in units)
        cat_opts = '<option value="">全部类别</option>' + ''.join(f'<option value="{h(r["category"])}">{h(r["category"])}</option>' for r in cats)
        recent_rows = ''.join(
            f'''<tr><td>{h(r["created_at"])}</td><td>{h(r["period"])}</td><td>{h(r["fee_name"] or r["fee_type_id"])}</td>
            <td>{"按面积" if r["allocation_method"]=="area" else "按户数"}</td><td class="text-end">{r["room_count"]}</td><td class="text-end money">¥{m(r["total_amount"])}</td></tr>'''
            for r in recent
        ) or '<tr><td colspan="6" class="text-center text-muted py-3">暂无公摊记录</td></tr>'
        self._html(self._page('公摊分摊', f'''
        <div class="alert alert-info"><i class="bi bi-diagram-3"></i> 手动录入公摊总金额，系统按面积或户数分摊到选定房间，并生成独立账单。建议先预览再确认。</div>
        <form method="POST" action="/shared_expenses/allocate" class="row g-3">
            <div class="col-md-3"><label>账期 *</label><input type="date" name="period" class="form-control" value="{period_to_date(get_period())}" required><small class="text-muted">按所选日期所在月份作为账期</small></div>
            <div class="col-md-3"><label>收费项目 *</label><select name="fee_type_id" class="form-select" required>{fee_opts}</select></div>
            <div class="col-md-3"><label>公摊总金额 *</label><div class="input-group"><span class="input-group-text">¥</span><input name="total_amount" type="number" step="0.01" min="0.01" class="form-control" required></div></div>
            <div class="col-md-3"><label>截止日</label><input name="due_day" type="number" min="1" max="28" value="28" class="form-control"></div>
            <div class="col-md-3"><label>分摊方式</label><select name="allocation_method" class="form-select"><option value="area">按面积分摊</option><option value="household">按户数平均</option></select></div>
            <div class="col-md-3"><label>楼栋</label><select name="building" class="form-select">{bld_opts}</select></div>
            <div class="col-md-3"><label>单元/座</label><select name="unit" class="form-select">{unit_opts}</select></div>
            <div class="col-md-3"><label>类别</label><select name="category" class="form-select">{cat_opts}</select></div>
            <div class="col-md-3"><label>说明</label><input name="notes" class="form-control" placeholder="如：5月公共电费"></div>
            <div class="col-12"><button name="mode" value="preview" class="btn btn-primary btn-lg">预览分摊</button>
            <button name="mode" value="confirm" class="btn btn-success btn-lg">直接生成账单</button></div>
        </form>
        <div class="card mt-4"><div class="card-header">最近公摊记录</div><div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>时间</th><th>账期</th><th>项目</th><th>方式</th><th class="text-end">户数</th><th class="text-end">总额</th></tr></thead><tbody>{recent_rows}</tbody></table></div></div>
        ''', 'shared_expenses'))

    def _shared_expense_allocate(self, d):
        period = date_to_period(qs(d, 'period'))
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
        rooms = shared_expense_rooms(db, ft, period, building, unit, category)
        existing = {row[0] for row in db.execute('SELECT room_id FROM bills WHERE billing_period=? AND fee_type_id=?', (period, fid)).fetchall()}
        rooms = [r for r in rooms if r['id'] not in existing]
        allocations = allocate_shared_amount(total, rooms, method)
        if not allocations:
            db.close(); return self._redirect('/shared_expenses?flash=没有可分摊房间或金额无效')
        if qs(d, 'mode') == 'preview':
            db.close(); return self._render_shared_preview(period, fid, total, method, building, unit, category, due_day, notes, allocations, len(existing))
        backup_name = create_db_backup('auto_before_bill_generation')
        parts = period.split('-')
        due_date = f'{parts[0]}-{parts[1]}-{due_day:02d}'
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
            cur = db.execute('''INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,source_ref,notes)
                VALUES(?,?,?,?,?,?,'unpaid',?,'shared_expense',?,?)''', (r['id'], r['owner_id'], fid, period, amount, due_date, bn, str(run_id), notes))
            bill_ids.append(cur.lastrowid)
        db.execute('UPDATE shared_expense_runs SET generated_bill_ids=? WHERE id=?', (json.dumps(bill_ids), run_id))
        db.commit(); db.close()
        self._audit('shared_expense_generate', 'shared_expense_run', run_id, None, {'period': period, 'fee_type_id': fid, 'total': total, 'bill_ids': bill_ids}, notes)
        return self._render_shared_result(period, total, method, allocations, backup_name, bill_ids)

    def _render_shared_preview(self, period, fid, total, method, building, unit, category, due_day, notes, allocations, skipped):
        rows = ''.join(f'<tr><td>{h(a["room"]["building"])}-{h(a["room"]["unit"] or "")}-{h(a["room"]["room_number"])}</td><td>{h(a["room"]["category"])}</td><td class="text-end">{m(a["weight"])}</td><td class="text-end money">¥{m(a["amount"])}</td></tr>' for a in allocations[:80])
        hidden = ''.join(f'<input type="hidden" name="{k}" value="{h(v)}">' for k, v in {'period':period,'fee_type_id':fid,'total_amount':total,'allocation_method':method,'building':building,'unit':unit,'category':category,'due_day':due_day,'notes':notes}.items())
        self._html(self._page('公摊分摊预览', f'''
        <div class="alert alert-warning">当前仅预览，不写入账单。确认后会生成 {len(allocations)} 笔公摊账单，跳过已有账单房间 {skipped} 间。</div>
        <div class="row text-center g-2 mb-3"><div class="col-md-4"><div class="summary-tile">房间数<br><strong>{len(allocations)}</strong></div></div><div class="col-md-4"><div class="summary-tile">总金额<br><strong class="money">¥{m(total)}</strong></div></div><div class="col-md-4"><div class="summary-tile">分摊合计<br><strong class="money">¥{m(sum(a["amount"] for a in allocations))}</strong></div></div></div>
        <div class="card"><div class="card-header">分摊明细</div><div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>房间</th><th>类别</th><th class="text-end">权重</th><th class="text-end">金额</th></tr></thead><tbody>{rows}</tbody></table></div></div>
        <form method="POST" action="/shared_expenses/allocate" class="mt-3"><input type="hidden" name="mode" value="confirm">{hidden}<button class="btn btn-success btn-lg">确认生成公摊账单</button> <a class="btn btn-outline-secondary btn-lg" href="/shared_expenses">返回修改</a></form>
        ''', 'shared_expenses'))

    def _render_shared_result(self, period, total, method, allocations, backup_name, bill_ids):
        self._html(self._page('公摊分摊结果', f'''
        <div class="alert alert-success">公摊账单生成完成：{len(bill_ids)} 笔，合计 ¥{m(sum(a['amount'] for a in allocations))}。</div>
        <div class="alert alert-light border"><strong>自动备份：</strong><code>{h(backup_name)}</code></div>
        <div class="export-actions"><a class="btn btn-primary" href="/bills?period={h(period)}">查看账单</a><a class="btn btn-outline-success" href="/bills/export_generated?ids={h(','.join(str(x) for x in bill_ids))}">导出本次公摊CSV</a><a class="btn btn-outline-secondary" href="/shared_expenses">继续分摊</a></div>
        ''', 'shared_expenses'))
