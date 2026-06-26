#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repair/work order management."""

from server.db import get_db, h, m, qs
from server.base import BaseHandler
from server.ui_components import render_form, render_kv_table, render_table
from datetime import date


class RepairMixin(BaseHandler):

    def _repairs(self, q):
        db=get_db();s=qs(q,'status');kw=qs(q,'keyword')
        sql='''SELECT r.*,rm.building,rm.unit,rm.room_number FROM repairs r
               LEFT JOIN rooms rm ON r.room_id=rm.id WHERE 1=1'''
        vals=[]
        if s:sql+=" AND r.status=?";vals.append(s)
        if kw:
            sql+=" AND (rm.building LIKE ? OR rm.room_number LIKE ? OR r.owner_name LIKE ? OR r.description LIKE ?)"
            vals.extend([f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%'])
        sql+=" ORDER BY r.id DESC"
        rows=db.execute(sql,vals).fetchall()
        totals={'pending':0,'processing':0,'done':0,'cancelled':0}
        total_cost=0
        for r in rows:
            totals[r['status']]=totals.get(r['status'],0)+1
            if r['status']=='done':total_cost+=r['cost'] or 0
        db.close()
        sn={'pending':'warning text-dark','processing':'info','done':'success','cancelled':'secondary'}
        ln={'pending':'待处理','processing':'处理中','done':'已完成','cancelled':'已取消'}
        rh=''
        for r in rows:
            rm_name=f"{r['building']or''}-{r['unit']or''}-{r['room_number']or''}" if r['building'] else r['owner_name'] or '外部'
            rh+=f'''<tr><td><small>{r["id"]}</small></td><td>{h(rm_name)}</td>
    <td><small>{h(r["description"][:30])}{"..." if len(r["description"] or "")>30 else ""}</small></td>
    <td><span class="badge bg-secondary">{h(r["category"]or"-")}</span></td>
    <td><span class="badge bg-{sn.get(r['status'],'secondary')}">{ln.get(r['status'],r['status'])}</span></td>
    <td>{h(r["assignee"]or"-")}</td>
    <td class="text-end">{f'¥{m(r["cost"])}' if r["cost"] else '-'}</td>
    <td><small>{h(r["report_date"]or"")}</small></td>
    <td><a href="/repairs/{r["id"]}" class="btn btn-sm btn-outline-info"><i class="bi bi-eye"></i></a>
    <form method=POST action="/repairs/{r["id"]}/delete" style=display:inline onsubmit="return confirm('确定删除？')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'''
        table_html = render_table(
            ['#', '房间/业主', '报修内容', '类别', '状态', '维修人', ('费用', 'text-end'), '日期', '操作'],
            rh,
            empty_text='暂无维修记录',
        )
        self._html(self._page('维修管理',f'''
    <div class="d-flex flex-wrap justify-content-between mb-3 gap-2">
    <form class="row g-2" method=GET>
    <div class="col-auto"><select name="status" class="form-select form-select-sm" onchange="this.form.submit()">
    <option value="">全部状态</option><option value="pending"{" selected" if s=='pending' else""}>待处理</option>
    <option value="processing"{" selected" if s=='processing' else""}>处理中</option>
    <option value="done"{" selected" if s=='done' else""}>已完成</option>
    <option value="cancelled"{" selected" if s=='cancelled' else""}>已取消</option></select></div>
    <div class="col-auto"><input name="keyword" class="form-control form-control-sm" placeholder="搜索..." value="{h(kw)}"></div>
    <div class="col-auto"><button class="btn btn-sm btn-outline-primary"><i class="bi bi-search"></i></button>
    <a href="/repairs" class="btn btn-sm btn-outline-secondary"><i class="bi bi-x-circle"></i></a></div></form>
    <a href="/repairs/create" class="btn btn-primary btn-sm"><i class="bi bi-plus-lg"></i> 新建报修</a></div>
    <div class="d-flex flex-wrap gap-2 mb-2">
    <span class="badge bg-light text-dark p-2">全部{len(rows)}单</span>
    <span class="badge bg-warning text-dark p-2">待处理{totals["pending"]}</span>
    <span class="badge bg-info p-2">处理中{totals["processing"]}</span>
    <span class="badge bg-success p-2">已完成{totals["done"]}</span>
    <span class="badge bg-secondary p-2">已取消{totals["cancelled"]}</span>
    <span class="badge bg-light text-dark p-2">维修费: ¥{m(total_cost)}</span>
    </div>
    {table_html}''','repairs'))

    def _repair_form(self, rid=None):
        db=get_db();r=None
        if rid:r=db.execute("SELECT * FROM repairs WHERE id=?",(rid,)).fetchone()
        rooms=db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.building,r.room_number").fetchall()
        db.close()
        rms='<option value="">外部（无房间）</option>'+''.join(f'<option value="{rm["id"]}">{h(rm["building"])}-{h(rm["room_number"])} ({h(rm["oname"]or"")})</option>' for rm in rooms)
        today=date.today().isoformat()
        if rid:
            sn={'pending':'待处理','processing':'处理中','done':'已完成','cancelled':'已取消'}
            info_rows = [
                ('报修内容', h(r["description"])),
                ('业主', h(r["owner_name"]or"-")),
                ('电话', h(r["phone"]or"-")),
                ('类别', f'<span class="badge bg-secondary">{h(r["category"]or"-")}</span>'),
                ('报修日期', h(r["report_date"]or"-")),
                ('状态', f'<span class="badge bg-{"warning text-dark" if r["status"]=="pending" else "info" if r["status"]=="processing" else "success" if r["status"]=="done" else "secondary"}">{sn.get(r["status"],r["status"])}</span>'),
                ('维修人', h(r["assignee"]or"-")),
                ('维修费', f'¥{m(r["cost"])}' if r["cost"] else '-'),
                ('完成日期', h(r["complete_date"]or"-")),
            ]
            if r["notes"]:
                info_rows.append(('备注', h(r["notes"])))
            info_table = render_kv_table(info_rows)
            fields_html = f'''
    <div class="col-12"><label>状态</label><select name="status" class="form-select">
    <option value="pending"{" selected" if r["status"]=="pending" else""}>待处理</option>
    <option value="processing"{" selected" if r["status"]=="processing" else""}>处理中</option>
    <option value="done"{" selected" if r["status"]=="done" else""}>已完成</option>
    <option value="cancelled"{" selected" if r["status"]=="cancelled" else""}>已取消</option></select></div>
    <div class="col-md-6"><label>维修人</label><input name="assignee" class="form-control" value="{h(r["assignee"]or"")}"></div>
    <div class="col-md-6"><label>维修费</label><div class="input-group"><span class="input-group-text">¥</span><input name="cost" type="number" class="form-control" value="{r["cost"] or 0}" step="0.1"></div></div>
    <div class="col-12"><label>备注</label><textarea name="notes" class="form-control" rows="2">{h(r["notes"] or "")}</textarea></div>'''
            form_html = render_form(fields_html, action=f'/repairs/{rid}/status', submit_text='<i class="bi bi-save"></i> 更新', cancel_url='/repairs')
            self._html(self._page('维修工单',f'''
    <div class="row g-4"><div class="col-md-6"><div class="card"><div class="card-header">工单 #{r["id"]}</div>
    <div class="card-body">{info_table}</div></div></div>
    <div class="col-md-6"><div class="card"><div class="card-header">更新状态</div>
    <div class="card-body">{form_html}</div></div></div></div>''','repairs'))
        else:
            fields_html = f'''
    <div class="col-md-6"><label>关联房间</label><select name="room_id" class="form-select">{rms}</select></div>
    <div class="col-md-6"><label>业主姓名</label><input name="owner_name" class="form-control" placeholder="未选房间时手动填写"></div>
    <div class="col-md-6"><label>联系电话</label><input name="phone" class="form-control"></div>
    <div class="col-md-6"><label>报修日期</label><input name="report_date" type="date" class="form-control" value="{today}"></div>
    <div class="col-12"><label>报修内容 <span class="text-danger">*</span></label><textarea name="description" class="form-control" rows="3" required></textarea></div>
    <div class="col-md-6"><label>维修类别</label><select name="category" class="form-select">
    <option value="水电">水电</option><option value="门窗">门窗</option><option value="管道">管道</option>
    <option value="墙面">墙面/地面</option><option value="电器">电器</option><option value="其他">其他</option></select></div>'''
            form_html = render_form(fields_html, action='/repairs/create', submit_text='<i class="bi bi-plus-lg"></i> 提交报修', cancel_url='/repairs')
            self._html(self._page('新建报修', form_html, 'repairs'))

    def _repair_create(self, d):
        db=get_db()
        rid=qs(d,'room_id')
        db.execute("INSERT INTO repairs(room_id,owner_name,phone,report_date,description,category) VALUES(?,?,?,?,?,?)",
                   (int(rid) if rid else None,qs(d,'owner_name'),qs(d,'phone'),qs(d,'report_date',date.today().isoformat()),
                    qs(d,'description'),qs(d,'category')))
        db.commit();db.close()
        self._redirect('/repairs?flash=报修提交成功')

    def _repair_detail(self, rid):
        self._repair_form(rid)

    def _repair_status(self, rid, d):
        db=get_db()
        st=qs(d,'status','pending')
        assignee=qs(d,'assignee')
        cost=float(qs(d,'cost',0)) if qs(d,'cost') else 0
        notes=qs(d,'notes','')
        complete=date.today().isoformat() if st=='done' else None
        db.execute("UPDATE repairs SET status=?,assignee=?,cost=?,complete_date=?,notes=? WHERE id=?",
                   (st,assignee if assignee else None,cost,complete,notes,rid))
        db.commit();db.close()
        sn={'pending':'待处理','processing':'处理中','done':'已完成','cancelled':'已取消'}
        self._redirect(f'/repairs/{rid}?flash=已更新为「{sn.get(st,st)}」')

    def _repair_delete(self, rid):
        db=get_db()
        db.execute("DELETE FROM repairs WHERE id=?",(rid,))
        db.commit();db.close()
        self._redirect('/repairs?flash=已删除')
