#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch bill adjustment pages and actions."""

import urllib.parse

from server.backups import create_db_backup
from server.db import get_db, h, m, qs, is_period_closed
from server.money import money_float


class BillBatchEditMixin:
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
            old_amt = money_float(r['amount'])
            new_amt = money_float(old_amt * (1 + amount_percent / 100)) if amount_mode == 'percent' else old_amt
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
            old_amt = money_float(bill['amount'])
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
                new_amt = money_float(old_amt * (1 + amount_percent / 100))
                updates.append('amount=?')
                params.append(new_amt)
            if updates:
                params.append(bid)
                db.execute(f"UPDATE bills SET {','.join(updates)} WHERE id=?", params)
            if amount_mode == 'percent':
                if new_amt != old_amt:
                    reason = notes or f'批量按百分比调整 {amount_percent}%'
                    approved = qs(d, 'approved_by', '管理员')
                    db.execute(
                        "INSERT INTO bill_adjustments(bill_id,old_amount,new_amount,reason,approved_by) VALUES(?,?,?,?,?)",
                        (bid, old_amt, new_amt, reason, approved)
                    )
                paid = money_float(db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=?", (bid,)).fetchone()[0])
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


