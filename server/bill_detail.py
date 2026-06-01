#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill detail, edit, print, delete."""

from server.db import get_db, update_overdue_bills, is_period_closed, h, m, qs
from server.base import BaseHandler
from server.backups import create_db_backup
from server.bill_batch_edit import BillBatchEditMixin
from server.bill_single_print import BillSinglePrintMixin


class BillDetailMixin(BillBatchEditMixin, BillSinglePrintMixin, BaseHandler):

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
