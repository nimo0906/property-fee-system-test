#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill detail, edit, print, delete."""

from server.db import get_db, get_fee_type_rate, calc_elevator_fee, calc_bill_late_fee, update_overdue_bills, is_period_closed, h, m, qs
from server.base import BaseHandler
from server.print_helper import print_page, print_header_row
from server.backups import create_db_backup
from datetime import datetime, date
import urllib.parse


class BillDetailMixin(BaseHandler):

    def _batch_edit_redirect(self, d, message):
        back_url = self._safe_bills_back_url(d)
        separator = '&' if '?' in back_url else '?'
        return self._redirect(back_url + separator + 'flash=' + urllib.parse.quote(message))
    def _bill_batch_edit(self, d):
        ids = self._batch_bill_ids(d)
        back_url = self._safe_bills_back_url(d)
        if not ids:
            return self._batch_edit_redirect(d, '请先在账单明细左侧勾选要批量修正的账单')
        placeholders = ','.join('?' * len(ids))
        db = get_db()
        rows = db.execute(f'''SELECT b.*,r.building,r.unit,r.room_number,f.name ft
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.id IN ({placeholders}) ORDER BY r.building,r.room_number''', ids).fetchall()
        db.close()
        bill_rows = ''.join(
            f'<tr><td>{h(r["bill_number"] or r["id"])}</td><td>{h(r["building"])}-{h(r["unit"])}-{h(r["room_number"])}</td>'
            f'<td>{h(r["ft"])}</td><td>{h(r["billing_period"])}</td><td>{h(r["due_date"] or "-")}</td><td>{h(r["notes"] or "")}</td></tr>'
            for r in rows
        )
        self._html(self._page('批量修正账单', f'''
        <div class="alert alert-warning"><strong>批量修正账单</strong>：先预览变更，确认后才会写入账单。</div>
        <form method="POST" action="/bills/batch_edit/preview" class="row g-3">
        <input type="hidden" name="bill_ids" value="{h(','.join(ids))}">
        <input type="hidden" name="back" value="{h(back_url)}">
        <div class="col-md-4"><label>统一截止日</label><input name="due_date" type="date" class="form-control"></div>
        <div class="col-md-8"><label>统一备注/修正原因</label><input name="notes" class="form-control" placeholder="如：统一调整截止日"></div>
        <div class="col-md-4"><label>金额调整方式</label><select name="amount_adjust_mode" class="form-select">
        <option value="">不调整金额</option><option value="percent">按百分比调整</option></select></div>
        <div class="col-md-4"><label>调整百分比</label><div class="input-group"><input name="amount_percent" type="number" step="0.01" class="form-control" placeholder="如 10 或 -5"><span class="input-group-text">%</span></div></div>
        <div class="col-12"><button class="btn btn-primary">预览批量修正</button> <a href="{h(back_url)}" class="btn btn-outline-secondary">取消</a></div>
        </form>
        <div class="card mt-3"><div class="card-header">将修正的账单</div>
        <table class="table table-sm mb-0"><thead><tr><th>编号</th><th>房间</th><th>费用</th><th>账期</th><th>当前截止日</th><th>当前备注</th></tr></thead><tbody>{bill_rows}</tbody></table></div>
        ''', 'bills'))

    def _bill_batch_edit_preview(self, d):
        ids = self._batch_bill_ids(d)
        back_url = self._safe_bills_back_url(d)
        due_date = qs(d, 'due_date')
        notes = qs(d, 'notes')
        amount_mode = qs(d, 'amount_adjust_mode')
        amount_percent_raw = qs(d, 'amount_percent')
        approved_by = qs(d, 'approved_by', '管理员')
        if not ids:
            return self._batch_edit_redirect(d, '请先在账单明细左侧勾选要批量修正的账单')
        if not due_date and not notes and not amount_mode:
            return self._batch_edit_redirect(d, '请填写要修正的内容')
        amount_percent = 0
        if amount_mode == 'percent':
            try:
                amount_percent = float(amount_percent_raw)
            except ValueError:
                return self._batch_edit_redirect(d, '金额调整百分比格式错误')
        placeholders = ','.join('?' * len(ids))
        db = get_db()
        rows = db.execute(f'''SELECT b.id,b.bill_number,b.amount,b.due_date,r.building,r.unit,r.room_number,f.name ft
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.id IN ({placeholders}) ORDER BY r.building,r.room_number,b.id''', ids).fetchall()
        db.close()
        detail_rows = ''
        for r in rows:
            old_amt = float(r['amount'])
            new_amt = round(old_amt * (1 + amount_percent / 100), 2) if amount_mode == 'percent' else old_amt
            new_due_date = due_date or r['due_date'] or '-'
            room = f'{r["building"] or ""}-{r["unit"] or ""}-{r["room_number"] or ""}'
            detail_rows += (
                f'<tr><td>{h(r["bill_number"] or r["id"])}</td><td>{h(room)}</td><td>{h(r["ft"] or "-")}</td>'
                f'<td class="text-end">¥{m(old_amt)}</td><td class="text-end">¥{m(new_amt)}</td>'
                f'<td>{h(r["due_date"] or "-")}</td><td>{h(new_due_date)}</td><td>{h(notes or "-")}</td></tr>'
            )
        hidden = ''.join([
            f'<input type="hidden" name="bill_ids" value="{h(",".join(ids))}">',
            f'<input type="hidden" name="due_date" value="{h(due_date)}">',
            f'<input type="hidden" name="notes" value="{h(notes)}">',
            f'<input type="hidden" name="amount_adjust_mode" value="{h(amount_mode)}">',
            f'<input type="hidden" name="amount_percent" value="{h(amount_percent_raw)}">',
            f'<input type="hidden" name="approved_by" value="{h(approved_by)}">',
            f'<input type="hidden" name="back" value="{h(back_url)}">',
        ])
        self._html(self._page('批量修正预览', f'''
        <div class="alert alert-info"><strong>批量修正预览</strong>：以下内容尚未写入数据库，请核对后再确认执行。</div>
        <div class="card"><div class="card-header">批量修正预览明细</div>
        <table class="table table-sm mb-0"><thead><tr><th>编号</th><th>房间</th><th>收费项目</th><th class="text-end">原金额</th><th class="text-end">新金额</th><th>原截止日</th><th>新截止日</th><th>修正原因</th></tr></thead><tbody>{detail_rows}</tbody></table></div>
        <form method="POST" action="/bills/batch_edit/apply">{hidden}
        <button class="btn btn-danger">确认执行批量修正</button>
        <button class="btn btn-outline-secondary" type="button" onclick="history.back()">返回修改</button>
        <a href="{h(back_url)}" class="btn btn-outline-secondary">取消</a></form>
        ''', 'bills'))

    def _bill_batch_edit_apply(self, d):
        ids = self._batch_bill_ids(d)
        back_url = self._safe_bills_back_url(d)
        due_date = qs(d, 'due_date')
        notes = qs(d, 'notes')
        amount_mode = qs(d, 'amount_adjust_mode')
        amount_percent_raw = qs(d, 'amount_percent')
        if not ids:
            return self._batch_edit_redirect(d, '请先在账单明细左侧勾选要批量修正的账单')
        if not due_date and not notes and not amount_mode:
            return self._batch_edit_redirect(d, '请填写要修正的内容')
        amount_percent = 0
        if amount_mode == 'percent':
            try:
                amount_percent = float(amount_percent_raw)
            except ValueError:
                return self._batch_edit_redirect(d, '金额调整百分比格式错误')
        db = get_db()
        placeholders = ','.join('?' * len(ids))
        bill_rows = db.execute(f'''SELECT b.id,b.bill_number,b.billing_period,b.amount,b.due_date,b.notes,r.building,r.unit,r.room_number,f.name ft
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.id IN ({placeholders}) ORDER BY r.building,r.room_number,b.id''', ids).fetchall()
        closed_periods = sorted({r['billing_period'] for r in bill_rows if is_period_closed(r['billing_period'])})
        if closed_periods:
            db.close()
            return self._redirect('/bills?flash=' + ','.join(closed_periods) + '已结账，无法批量修正')
        backup_name = create_db_backup('auto_before_batch_adjustment') if bill_rows else ''
        updated = 0
        details = []
        for bill in bill_rows:
            bid = bill['id']
            old_amt = float(bill['amount'])
            new_amt = old_amt
            new_due_date = due_date or bill['due_date']
            updates = []
            params = []
            if due_date:
                updates.append('due_date=?')
                params.append(due_date)
            if notes:
                updates.append('notes=?')
                params.append(notes)
            if amount_mode == 'percent':
                new_amt = round(old_amt * (1 + amount_percent / 100), 2)
                updates.append('amount=?')
                params.append(new_amt)
            if updates:
                params.append(bid)
                db.execute(f"UPDATE bills SET {','.join(updates)} WHERE id=?", params)
            if amount_mode == 'percent':
                if abs(new_amt - old_amt) > 0.001:
                    reason = notes or f'批量按百分比调整 {amount_percent}%'
                    approved = qs(d, 'approved_by', '管理员')
                    db.execute(
                        "INSERT INTO bill_adjustments(bill_id,old_amount,new_amount,reason,approved_by) VALUES(?,?,?,?,?)",
                        (bid, old_amt, new_amt, reason, approved)
                    )
                paid = db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=?", (bid,)).fetchone()[0]
                if paid >= new_amt:
                    db.execute("UPDATE bills SET status='paid',paid_at=datetime('now','localtime') WHERE id=?", (bid,))
                elif paid > 0:
                    db.execute("UPDATE bills SET status='partial' WHERE id=?", (bid,))
                else:
                    db.execute("UPDATE bills SET status='unpaid' WHERE id=?", (bid,))
            updated += 1
            room = f'{bill["building"] or ""}-{bill["unit"] or ""}-{bill["room_number"] or ""}'
            details.append({
                'number': bill['bill_number'] or bid,
                'room': room,
                'fee': bill['ft'] or '-',
                'old_amount': old_amt,
                'new_amount': new_amt,
                'old_due_date': bill['due_date'] or '-',
                'new_due_date': new_due_date or '-',
                'reason': notes or (f'批量按百分比调整 {amount_percent}%' if amount_mode == 'percent' else '-'),
            })
        db.commit()
        db.close()
        backup_html = ''
        if backup_name:
            backup_html = f'''<div class="alert alert-light border"><strong>自动备份：</strong><code>{h(backup_name)}</code>
            <form method="POST" action="/backups/{h(backup_name)}/restore" class="d-inline ms-2" onsubmit="return confirm('恢复会覆盖当前数据，确定恢复到批量修正前？')"><button class="btn btn-sm btn-outline-warning">恢复到修正前</button></form></div>'''
        detail_rows = ''.join(
            f'<tr><td>{h(x["number"])}</td><td>{h(x["room"])}</td><td>{h(x["fee"])}</td>'
            f'<td class="text-end">¥{m(x["old_amount"])}</td><td class="text-end">¥{m(x["new_amount"])}</td>'
            f'<td>{h(x["old_due_date"])}</td><td>{h(x["new_due_date"])}</td><td>{h(x["reason"])}</td></tr>'
            for x in details
        )
        self._html(self._page('批量修正结果', f'''
        <div class="alert alert-success"><strong>批量修正结果</strong>：已完成。</div>
        {backup_html}
        <div class="row text-center g-2 mb-3">
        <div class="col-md-12"><div class="border rounded p-3"><div class="text-muted small">更新账单</div><strong>{updated}</strong></div></div>
        </div>
        <div class="card"><div class="card-header">批量修正明细</div>
        <table class="table table-sm mb-0"><thead><tr><th>编号</th><th>房间</th><th>收费项目</th><th class="text-end">原金额</th><th class="text-end">新金额</th><th>原截止日</th><th>新截止日</th><th>修正原因</th></tr></thead><tbody>{detail_rows}</tbody></table></div>
        <a class="btn btn-primary" href="/bills/review?scope=adjusted">去核对工作台</a>
        <a class="btn btn-outline-primary" href="{h(back_url)}">返回账单列表</a>
        ''', 'bills'))

    def _safe_bills_back_url(self, d):
        back_url = qs(d or {}, 'back', '/bills')
        return back_url if back_url.startswith('/bills') else '/bills'

    def _batch_bill_ids(self, d):
        raw = d.get('bill_ids', [])
        if isinstance(raw, list):
            expanded = []
            for item in raw:
                expanded.extend(str(item).split(','))
            raw = expanded
        elif isinstance(raw, str):
            raw = raw.split(',') if ',' in raw else [raw]
        ids = []
        for x in raw:
            cleaned = str(x).strip().strip('[]').strip().strip("'\"")
            if cleaned.isdigit():
                ids.append(cleaned)
        return ids

    def _bill_detail(self, bid, q=None):
        update_overdue_bills()
        back_url = qs(q or {}, 'back', '/bills')
        if not back_url.startswith('/bills'):
            back_url = '/bills'
        db=get_db()
        b=db.execute('''SELECT b.*,r.building,r.unit,r.room_number,r.area,r.floor,r.category,o.name oname,f.name ft,f.calc_method,f.unit_price,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE b.id=?''',(bid,)).fetchone()
        if not b: return self._error(404)
        formula_text = ''
        if b['calc_method'] == 'area':
            rate = b['unit_price']
            area_val = float(b['area'] or 0)
            formula_text = f'面积 {area_val:.2f}m2 * 单价 {rate:.2f} = ¥{b["amount"]:.2f}'
        elif b['calc_method'] == 'floor':
            area_val = float(b['area'] or 0)
            floor_val = int(b['floor'] or 1)
            db2 = get_db()
            tier = db2.execute("SELECT rate FROM elevator_fee_tiers WHERE ? BETWEEN floor_from AND floor_to ORDER BY id LIMIT 1", (floor_val,)).fetchone()
            db2.close()
            tier_rate = tier[0] if tier else 1.0
            formula_text = f'楼层系数 {tier_rate:.2f} * 面积 {area_val:.2f}m2 = ¥{b["amount"]:.2f}'
        elif b['calc_method'] == 'meter':
            period_compact = b['billing_period'].replace('-', '')
            db2 = get_db()
            mr = db2.execute("SELECT consumption FROM meter_readings WHERE room_id=? AND fee_type_id=? AND period=? AND status='confirmed' LIMIT 1", (b['room_id'], b['fee_type_id'], period_compact)).fetchone()
            db2.close()
            cons = mr[0] if mr else 0
            formula_text = f'用量 {cons} * 单价 {b["unit_price"]:.2f} = ¥{b["amount"]:.2f}'
        elif b['calc_method'] == 'fixed':
            formula_text = f'固定金额 ¥{b["unit_price"]:.2f}'
        elif b['calc_method'] == 'household':
            formula_text = f'按户分摊 ¥{b["unit_price"]:.2f}'
        pays=db.execute("SELECT * FROM payments WHERE bill_id=? ORDER BY payment_date",(bid,)).fetchall()
        adjs=db.execute("SELECT * FROM bill_adjustments WHERE bill_id=? ORDER BY created_at DESC",(bid,)).fetchall()
        db.close()
        rem=b['amount']-b['paid']
        pay_section = ''
        if pays:
            pay_rows = ''.join(f'<tr><td><small>{h(p["payment_date"]or"-")}</small></td><td class="text-end"><span class="money money-paid">+¥{m(p["amount_paid"])}</span></td><td>{h(p["payment_method"])}</td><td>{h(p["operator"]or"-")}</td></tr>' for p in pays)
            pay_section = f'''<div class="card mt-3"><div class="card-header">缴费记录</div>
        <div class="card-body p-0"><table class="table table-hover mb-0"><thead><tr><th>时间</th><th class="text-end">金额</th><th>方式</th><th>经手人</th></tr></thead><tbody>{pay_rows}</tbody></table></div></div>'''
        adj_section=''
        if adjs:
            adj_rows=''.join(f'<tr><td><small>{h(a["created_at"]or"-")}</small></td><td class="text-end"><span class="money-muted">¥{m(a["old_amount"])}</span></td><td class="text-end"><span class="money">¥{m(a["new_amount"])}</span></td><td class="text-end"><span class="money money-due">¥{m(a["old_amount"]-a["new_amount"])}</span></td><td><small>{h(a["reason"])}</small></td><td>{h(a["approved_by"])}</td></tr>' for a in adjs)
            adj_section=f'''<div class="card mt-3"><div class="card-header"><i class="bi bi-pencil-square"></i> 调整记录</div>
        <div class="card-body p-0"><table class="table table-hover mb-0"><thead><tr><th>时间</th><th class="text-end">原金额</th><th class="text-end">新金额</th><th class="text-end">减免</th><th>原因</th><th>审批人</th></tr></thead><tbody>{adj_rows}</tbody></table></div></div>'''
        sn={'paid':'status-paid','unpaid':'status-unpaid','overdue':'status-overdue','partial':'status-partial'}
        ln={'paid':'已缴','unpaid':'未缴','overdue':'逾期','partial':'部分缴'}
        pay_btn = f'<a href="/bills/{bid}/pay" class="btn btn-primary mt-3"><i class="bi bi-credit-card"></i> 缴费</a>' if b['status'] != 'paid' else ''
        progress_pct = round(b['paid']/b['amount']*100,1) if b['amount']>0 else 0
        rem_class = 'text-danger' if rem>0 else 'text-success'
        self._html(self._page('账单详情',f'''
        <div class="row g-4"><div class="col-md-6"><div class="card"><div class="card-header">账单信息</div>
        <div class="card-body"><table class="table table-borderless mb-0">
        <tr><td class="text-muted" style="width:110px">编号</td><td><strong>{h(b["bill_number"]or"-")}</strong></td></tr>
        <tr><td class="text-muted">房间</td><td>{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}</td></tr>
        <tr><td class="text-muted">业主</td><td>{h(b["oname"]or"-")}</td></tr>
	        <tr><td class="text-muted">费用类型</td><td><span class="badge status-info fs-6">{h(b["ft"])}</span></td></tr>
        <tr><td class="text-muted">账期</td><td>{h(b["billing_period"])}</td></tr>
	        <tr><td class="text-muted">状态</td><td><span class="badge {sn.get(b["status"],'status-neutral')} fs-6">{ln.get(b["status"],b["status"])}</span></td></tr>
        </table></div></div></div>
        <div class="col-md-6"><div class="card"><div class="card-header">缴费信息</div>
	        <div class="card-body text-center"><p class="text-muted mb-1">应缴金额</p><h2 class="money">¥{m(b["amount"])}</h2><hr>
	        <div class="row"><div class="col-6"><small>已缴</small><h5 class="money money-paid">¥{m(b["paid"])}</h5></div>
	        <div class="col-6"><small>欠费</small><h5 class="money {'money-due' if rem>0 else 'money-paid'}">¥{m(rem)}</h5></div></div>
        <div class="progress progress-thin mt-2"><div class="progress-bar bg-success" style="width:{progress_pct}%"></div></div>
        {pay_btn}</div></div>
        {pay_section}
        {adj_section}</div></div>
        <div class="card mt-3"><div class="card-header">费用明细核对</div>
        <div class="card-body"><table class="table table-borderless mb-0">
	        <tr><td class="text-muted" style="width:110px">计算方式</td><td><span class="badge status-info">{h(b["calc_method"])}</span></td></tr>
        <tr><td class="text-muted">计算明细</td><td><strong>{formula_text}</strong></td></tr>
        </table></div></div>
        <a href='/bills/{bid}/edit' class='btn btn-outline-warning mt-3'><i class='bi bi-pencil'></i> 修改金额</a>
	        <a href="/bills/{bid}/print" class="btn btn-outline-secondary mt-3" target="_blank"><i class="bi bi-printer"></i> 打印</a>
        <a href="{h(back_url)}" class="btn btn-outline-secondary mt-3"><i class="bi bi-arrow-left"></i> 返回</a>''','bills'))

    def _bill_print(self, bid):
        db = get_db()
        b = db.execute('''SELECT b.*,r.building,r.unit,r.room_number,r.area,r.floor,r.category,o.name oname,o.phone ophone,f.name ft,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE b.id=?''', (bid,)).fetchone()
        pays = db.execute("SELECT * FROM payments WHERE bill_id=? ORDER BY payment_date", (bid,)).fetchall()
        db.close()
        if not b:
            return self._error(404)
        rem = b['amount'] - b['paid']
        sn = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
        pay_rows = ''.join(
            f'<tr><td>{h((p["payment_date"] or "")[:10])}</td><td class="amt">¥{m(p["amount_paid"])}</td>'
            f'<td>{h(p["payment_method"])}</td><td>{h(p["operator"] or "-")}</td></tr>'
            for p in pays)
        info = ''.join(print_header_row(k, v) for k, v in [
            ('房号', f'{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}'),
            ('业主', h(b["oname"] or '-')),
            ('电话', h(b["ophone"] or '-')),
            ('费用项目', h(b["ft"])),
            ('账期', h(b["billing_period"])),
            ('面积', f'{b["area"] or "-"} m2'),
            ('票据号', h(b["bill_number"] or '-')),
            ('截止日', h(b["due_date"] or '-')),
        ])
        pay_section = ''
        if pay_rows:
            pay_section = f'''
            <h3 style="margin-top:14pt;font-size:12pt">缴费记录</h3>
            <table class="detail"><thead><tr><th>日期</th><th class="amt">金额</th><th>方式</th><th>经手人</th></tr></thead>
            <tbody>{pay_rows}</tbody></table>'''
        content = f'''
        <h1>物业管理缴费单</h1>
        <table class="header-info">{info}</table>
        <div class="amount-box">
            <div class="label">应缴金额</div>
            <div class="number">¥{m(b["amount"])}</div>
            <div style="margin-top:6pt;font-size:10pt;color:#666">
                已缴：¥{m(b["paid"])} | 欠费：<strong>¥{m(rem)}</strong> | 状态：{sn.get(b["status"], b["status"])}
            </div>
        </div>
        {pay_section}
        <table class="signature"><tr><td>业主签字</td><td>收费员签字</td><td>物业盖章</td></tr></table>
        '''
        self._html(print_page(f'缴费单 #{b["id"]}', content, back_url=f'/bills/{bid}'))

    def _bill_delete(self, bid, d=None):
        back_url = self._safe_bills_back_url(d)
        db=get_db()
        b=db.execute("SELECT * FROM bills WHERE id=?",(bid,)).fetchone()
        if not b:db.close();return self._error(404)
        if is_period_closed(b['billing_period']):
            db.close();return self._redirect(back_url, f'{b["billing_period"]}已结账，无法删除账单')
        pc=db.execute("SELECT COUNT(*) FROM payments WHERE bill_id=?",(bid,)).fetchone()[0]
        if pc>0:
            db.close()
            return self._redirect(back_url, f'账单{bid}已有{pc}条缴费记录，无法删除（可先退款/冲销后再操作）')
        old = dict(b)
        db.execute("DELETE FROM bills WHERE id=?",(bid,))
        db.commit();db.close()
        self._audit('bill_delete', 'bill', bid, old, None, '删除未缴账单')
        self._redirect(back_url, '已删除')

    def _bill_edit(self, bid):
        db=get_db()
        b=db.execute('''SELECT b.*,r.building,r.unit,r.room_number,f.name ft,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE b.id=?''',(bid,)).fetchone()
        if not b:return self._error(404)
        db.close()
        self._html(self._page('修改金额',f'''
        <div class="row g-4"><div class="col-md-5"><div class="card"><div class="card-header">账单信息</div>
        <div class="card-body"><table class="table table-borderless mb-0">
        <tr><td class="text-muted">房间</td><td>{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}</td></tr>
        <tr><td class="text-muted">费用</td><td><span class="badge bg-info">{h(b["ft"])}</span></td></tr>
        <tr><td class="text-muted">账期</td><td>{h(b["billing_period"])}</td></tr>
        <tr><td class="text-muted">当前金额</td><td><strong>¥{m(b["amount"])}</strong></td></tr>
        <tr><td class="text-muted">截止日</td><td>{h(b["due_date"] or "-")}</td></tr>
        </table></div></div></div>
        <div class="col-md-7"><div class="card"><div class="card-header">修正账单</div>
        <div class="card-body">
        <form method=POST action="/bills/{bid}/edit" class="row g-3">
        <div class="col-md-6"><label>新金额 (元) <span class="text-danger">*</span></label>
        <div class="input-group"><span class="input-group-text">¥</span>
        <input name="new_amount" type="number" class="form-control form-control-lg" value="{m(b["amount"])}" step="0.01" min="0.01" required></div>
        <p class="text-muted small mt-2"><i class="bi bi-info-circle"></i> 修改后，如果已有缴费记录，欠费/退款金额将自动重新计算。</p></div>
        <div class="col-md-6"><label>截止日</label>
        <input name="due_date" type="date" class="form-control form-control-lg" value="{h(b["due_date"] or "")}"></div>
        <div class="col-12"><label>修改原因 <span class="text-danger">*</span></label><input name="notes" class="form-control" placeholder="如：单价调整、减免优惠、困难补助等" required></div>
        <div class="col-md-6"><label>审批人</label><input name="approved_by" class="form-control" value="管理员" placeholder="经办人/审批人"></div>
        <div class="col-12"><hr>
        <button class="btn btn-primary"><i class="bi bi-check-lg"></i> 确认修改</button>
        <a href="/bills/{bid}" class="btn btn-outline-secondary">取消</a></div></form></div></div></div></div>''','bills'))

    def _bill_edit_post(self, bid, d):
        db=get_db()
        new_amt=float(qs(d,'new_amount',0))
        if new_amt<=0:db.close();return self._redirect(f'/bills/{bid}/edit?flash=金额必须大于0')
        reason=qs(d,'notes','')
        due_date=qs(d,'due_date','')
        approved=qs(d,'approved_by','管理员')
        old=db.execute("SELECT * FROM bills WHERE id=?",(bid,)).fetchone()
        if not old:db.close();return self._error(404)
        if is_period_closed(old['billing_period']):
            db.close();return self._redirect(f'/bills/{bid}?flash={old["billing_period"]}已结账，无法修改账单')
        old_amt=old['amount']
        create_db_backup('auto_before_bill_adjustment')
        db.execute("UPDATE bills SET amount=?,due_date=?,notes=? WHERE id=?",(new_amt,due_date,reason,bid))
        if abs(new_amt-old_amt) > 0.001:
            db.execute("INSERT INTO bill_adjustments(bill_id,old_amount,new_amount,reason,approved_by) VALUES(?,?,?,?,?)",
                       (bid,old_amt,new_amt,reason,approved))
        paid=db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=?",(bid,)).fetchone()[0]
        if paid>=new_amt:
            db.execute("UPDATE bills SET status='paid',paid_at=datetime('now','localtime') WHERE id=?",(bid,))
        elif paid>0:
            db.execute("UPDATE bills SET status='partial' WHERE id=?",(bid,))
        else:
            db.execute("UPDATE bills SET status='unpaid' WHERE id=?",(bid,))
        db.commit();db.close()
        self._audit('bill_amount_update', 'bill', bid, {'amount': old_amt, 'due_date': old['due_date'] if 'due_date' in old.keys() else ''}, {'amount': new_amt, 'due_date': due_date, 'approved_by': approved}, reason)
        diff=new_amt-old_amt
        action='减免' if diff<0 else '调增'
        self._redirect(f'/bills/{bid}?flash=金额已{action}：¥{m(old_amt)} -> ¥{m(new_amt)}（{h(reason)}）')
