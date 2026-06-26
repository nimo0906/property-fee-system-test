#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deposit management."""

from server.db import get_db, h, m, qs
from server.base import BaseHandler
from server.ui_components import render_table
from datetime import date


class DepositMixin(BaseHandler):

    def _deposits(self, q):
        db=get_db();kw=qs(q,'keyword');st=qs(q,'status','active')
        sql='''SELECT d.*,r.building,r.unit,r.room_number,o.name oname,o.phone ophone FROM deposits d
            LEFT JOIN rooms r ON d.room_id=r.id LEFT JOIN owners o ON d.owner_id=o.id WHERE d.status=?'''
        vals=[st]
        if kw:sql+=" AND (o.name LIKE ? OR r.building LIKE ? OR r.room_number LIKE ?)";vals.extend([f'%{kw}%',f'%{kw}%',f'%{kw}%'])
        sql+=" ORDER BY d.deposit_date DESC"
        rows=db.execute(sql,vals).fetchall()
        total_active=db.execute("SELECT COALESCE(SUM(amount-COALESCE(refund_amount,0)),0) FROM deposits WHERE status='active'").fetchone()[0]
        total_refunded=db.execute("SELECT COALESCE(SUM(refund_amount),0) FROM deposits WHERE status='refunded'").fetchone()[0]
        db.close()

        status_names = {'active':'押金中','refunded':'已退还'}
        status_badges = {'active':'success','refunded':'secondary'}
        rh = ""
        for r in rows:
            rem = (r['amount'] or 0) - (r['refund_amount'] or 0)
            sn = status_names.get(r['status'], r['status'])
            sb = status_badges.get(r['status'], 'secondary')
            rh += "<tr>"
            rh += "<td>" + h(r.get('building','') or '') + "-" + h(r.get('unit','') or '') + "-" + h(r.get('room_number','') or '') + "</td>"
            rh += "<td>" + h(r['oname'] or '-') + "</td>"
            rh += '<td class="text-end"><strong>' + m(r['amount']) + "</strong></td>"
            rh += "<td>" + h(r['deposit_date'] or '-') + "</td>"
            rh += '<td class="text-end">' + (m(r['refund_amount']) if r['refund_amount'] else '-') + "</td>"
            rh += "<td>" + (h(r['refund_date'] or '-') if r['refund_date'] else '-') + "</td>"
            rh += "<td><span class='badge bg-" + sb + "'>" + sn + "</span></td>"
            rh += "<td><small>" + h(r['notes'] or '') + "</small></td>"
            rh += "<td>"
            rh += "<a href='/deposits/" + str(r['id']) + "/edit' class='btn btn-sm btn-outline-primary'><i class='bi bi-pencil'></i></a> "
            if r['status'] == 'active':
                rh += "<a href='/deposits/" + str(r['id']) + "/refund' class='btn btn-sm btn-outline-warning'><i class='bi bi-arrow-return-left'></i></a> "
            rh += "<form method=POST action='/deposits/" + str(r['id']) + "/delete' style=display:inline><button class='btn btn-sm btn-outline-danger'><i class='bi bi-trash'></i></button></form>"
            rh += "</td></tr>"

        st_opts = ''
        for v, l in [('active','押金中'),('refunded','已退还')]:
            sel = ' selected' if st == v else ''
            st_opts += f'<option value="{v}"{sel}>{l}</option>'
        table_html = render_table(
            ['房间', '业主', ('押金金额', 'text-end'), '收取日期', ('退还金额', 'text-end'), '退还日期', '状态', '备注', '操作'],
            rh,
            empty_text='暂无押金记录',
        )

        self._html(self._page("押金管理", f'''
    <div class="d-flex flex-wrap justify-content-between mb-3 gap-2">
    <form class="row g-2" method=GET>
    <div class="col-auto"><select name="status" class="form-select form-select-sm" onchange="this.form.submit()">{st_opts}</select></div>
    <div class="col-auto"><input name="keyword" class="form-control form-control-sm" placeholder="业主/房间..." value="{h(kw)}"></div>
    <div class="col-auto"><button class="btn btn-sm btn-outline-primary"><i class="bi bi-search"></i></button><a href="/deposits" class="btn btn-sm btn-outline-secondary"><i class="bi bi-x-circle"></i></a></div></form>
    <a href="/deposits/create" class="btn btn-primary btn-sm"><i class="bi bi-plus-lg"></i> 收取押金</a></div>
    <div class="d-flex gap-2 mb-2 flex-wrap">
    <span class="badge bg-light text-dark p-2"><i class="bi bi-cash-stack"></i> 押金中: <strong>¥{m(total_active)}</strong></span>
    <span class="badge bg-secondary p-2">已退还: ¥{m(total_refunded)}</span></div>
    {table_html}''', "deposits"))

    def _deposit_form(self, did):
        db=get_db();dep=None
        if did: dep=db.execute("SELECT * FROM deposits WHERE id=?",(did,)).fetchone()
        rooms=db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.building,r.room_number").fetchall()
        owners=db.execute("SELECT * FROM owners ORDER BY name").fetchall()
        db.close()
        edit = bool(did)
        a = f'/deposits/{did}/edit' if edit else '/deposits/create'
        t = '编辑押金' if edit else '收取押金'
        amt = dep['amount'] if dep else 0
        dd = dep['deposit_date'] if dep else ''
        nt = h(dep['notes'] or '') if dep else ''
        rm_id = str(dep['room_id']) if dep and dep['room_id'] else ''
        ow_id = str(dep['owner_id']) if dep and dep['owner_id'] else ''
        rm_opts = '<option value="">--选择--</option>' + ''.join(f'<option value="{r["id"]}"{" selected" if rm_id==str(r["id"]) else""}>{h(r["building"])}-{h(r["room_number"])} ({h(r["oname"]or"")})</option>' for r in rooms)
        ow_opts = '<option value="">--选择--</option>' + ''.join(f'<option value="{o["id"]}"{" selected" if ow_id==str(o["id"]) else""}>{h(o["name"])}</option>' for o in owners)
        self._html(self._page(t, f'''<form method=POST action="{a}" class="row g-3">
    <div class="col-md-4"><label>关联房间</label><select name="room_id" class="form-select">{rm_opts}</select></div>
    <div class="col-md-4"><label>业主</label><select name="owner_id" class="form-select">{ow_opts}</select></div>
    <div class="col-md-4"><label>押金金额 <span class="text-danger">*</span></label><div class="input-group"><span class="input-group-text">¥</span><input name="amount" type="number" class="form-control" value="{amt}" step="0.1" min="0" required></div></div>
    <div class="col-md-4"><label>收取日期</label><input name="deposit_date" type="date" class="form-control" value="{dd}"></div>
    <div class="col-md-4"><label>备注</label><input name="notes" class="form-control" value="{nt}"></div>
    <div class="col-12"><hr><button class="btn btn-primary"><i class="bi bi-check-lg"></i> 保存</button> <a href="/deposits" class="btn btn-outline-secondary">取消</a></div></form>''', "deposits"))

    def _deposit_create(self, d):
        db=get_db()
        db.execute("INSERT INTO deposits(room_id,owner_id,amount,deposit_date,notes) VALUES(?,?,?,?,?)",
                   (int(qs(d,'room_id')) if qs(d,'room_id') else None, int(qs(d,'owner_id')) if qs(d,'owner_id') else None,
                    float(qs(d,'amount',0)), qs(d,'deposit_date') or None, qs(d,'notes')))
        db.commit();db.close()
        self._redirect('/deposits?flash=押金收取成功')

    def _deposit_edit(self, did, d):
        db=get_db()
        db.execute("UPDATE deposits SET room_id=?,owner_id=?,amount=?,deposit_date=?,notes=? WHERE id=?",
                   (int(qs(d,'room_id')) if qs(d,'room_id') else None, int(qs(d,'owner_id')) if qs(d,'owner_id') else None,
                    float(qs(d,'amount',0)), qs(d,'deposit_date') or None, qs(d,'notes'), did))
        db.commit();db.close()
        self._redirect('/deposits?flash=更新成功')

    def _deposit_refund(self, did):
        db=get_db()
        d=db.execute("SELECT * FROM deposits WHERE id=?",(did,)).fetchone()
        db.close()
        if not d: return self._error(404)
        self._html(self._page("退还押金", f'''
    <div class="row g-4"><div class="col-md-5"><div class="card"><div class="card-header">押金信息</div>
    <div class="card-body"><table class="table table-borderless mb-0">
    <tr><td class="text-muted">押金金额</td><td><strong>¥{m(d["amount"])}</strong></td></tr>
    <tr><td class="text-muted">已退还</td><td>{"¥"+m(d["refund_amount"]) if d["refund_amount"] else "-"}</td></tr>
    <tr><td class="text-muted">收取日期</td><td>{h(d["deposit_date"] or "-")}</td></tr>
    </table></div></div></div>
    <div class="col-md-7"><div class="card"><div class="card-header">办理退还</div>
    <div class="card-body"><form method=POST action="/deposits/{did}/refund" class="row g-3">
    <div class="col-12"><label>退还金额 <span class="text-danger">*</span></label>
    <div class="input-group"><span class="input-group-text">¥</span><input name="refund_amount" type="number" class="form-control form-control-lg" value="{m(d["amount"] - (d["refund_amount"] or 0))}" step="0.1" min="0" required></div></div>
    <div class="col-md-6"><label>退还日期</label><input name="refund_date" type="date" class="form-control" value="{date.today().isoformat()}"></div>
    <div class="col-md-6"><label>备注</label><input name="notes" class="form-control" placeholder="退还原因"></div>
    <div class="col-12"><hr><button class="btn btn-warning btn-lg"><i class="bi bi-arrow-return-left"></i> 确认退还</button>
    <a href="/deposits" class="btn btn-outline-secondary">取消</a></div></form></div></div></div></div>''', "deposits"))

    def _deposit_refund_post(self, did, d):
        db=get_db()
        refund=float(qs(d,'refund_amount',0))
        if refund<=0: db.close(); return self._redirect(f'/deposits/{did}/refund?flash=金额必须大于0')
        rd=qs(d,'refund_date',date.today().isoformat())
        nt=qs(d,'notes','')
        db.execute("UPDATE deposits SET refund_amount=?,refund_date=?,status='refunded',notes=? WHERE id=?",(refund,rd,nt,did))
        db.commit();db.close()
        self._redirect(f'/deposits?flash=已退还 ¥{m(refund)}')

    def _deposit_delete(self, did):
        db=get_db();db.execute("DELETE FROM deposits WHERE id=?",(did,));db.commit();db.close()
        self._redirect('/deposits?flash=已删除')
