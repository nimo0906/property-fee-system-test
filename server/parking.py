#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parking spot management."""

from server.db import get_db, h, m, qs
from server.base import BaseHandler
from server.ui_components import render_table


class ParkingMixin(BaseHandler):

    def _parking(self, q):
        db=get_db();kw=qs(q,'keyword');st=qs(q,'status')
        sql='''SELECT p.*,r.building,r.unit,r.room_number,o.name oname,o.phone ophone FROM parking_spots p
            LEFT JOIN rooms r ON p.room_id=r.id LEFT JOIN owners o ON r.owner_id=o.id WHERE 1=1'''
        vals=[]
        if st:sql+=" AND p.status=?";vals.append(st)
        if kw:sql+=" AND (p.spot_number LIKE ? OR r.building LIKE ? OR r.room_number LIKE ?)";vals.extend([f'%{kw}%',f'%{kw}%',f'%{kw}%'])
        sql+=" ORDER BY p.floor_zone,p.spot_number"
        rows=db.execute(sql,vals).fetchall()
        db.close()
        occupied=sum(1 for r in rows if r['status']=='occupied')
        vacant=sum(1 for r in rows if r['status']=='vacant')
        total_fee=sum(r['monthly_fee'] or 0 for r in rows if r['status']=='occupied')
        rh = ""
        for r in rows:
            spot_link = '<a href="/parking/' + str(r["id"]) + '/edit" class="btn btn-sm btn-outline-primary"><i class="bi bi-pencil"></i></a>'
            del_form = '<form method=POST action="/parking/' + str(r["id"]) + '/delete" style=display:inline><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>'
            spot_num = h(r["spot_number"])
            zone = h(r["floor_zone"] or "-")
            room_name = h(r["building"]or"") + "-" + h(r["unit"]or"") + "-" + h(r["room_number"]or"") if r["room_id"] else '<span class="text-muted">未绑定</span>'
            oname = h(r["oname"]or"-")
            fee_str = '<strong>'+m(r["monthly_fee"])+'</strong>' if r["monthly_fee"] else "-"
            status_str = '<span class="badge bg-success">已占用</span>' if r["status"]=="occupied" else '<span class="badge bg-secondary">空置</span>'
            notes = h(r["notes"]or"")
            rh += "<tr>"
            rh += "<td><strong>" + spot_num + "</strong></td>"
            rh += "<td>" + zone + "</td>"
            rh += "<td>" + room_name + "</td>"
            rh += "<td>" + oname + "</td>"
            rh += '<td class="text-end">' + fee_str + "</td>"
            rh += "<td>" + status_str + "</td>"
            rh += "<td><small>" + notes + "</small></td>"
            rh += "<td>" + spot_link + del_form + "</td></tr>"
        table_html = render_table(
            ['车位号', '区域/楼层', '绑定房间', '业主', ('月费', 'text-end'), '状态', '备注', '操作'],
            rh,
            empty_text='暂无车位',
        )
        self._html(self._page("停车管理",f'''
    <span class="badge bg-light text-dark p-2"><i class="bi bi-car-front"></i> 共{len(rows)}个车位</span>
    <span class="badge bg-success p-2">已占用{occupied}</span>
    <span class="badge bg-secondary p-2">空置{vacant}</span>
    <span class="badge bg-info p-2">月费合计 ¥{m(total_fee)}</span></div>
    {table_html}''','parking'))

    def _parking_form(self, pid):
        db=get_db();spot=None
        if pid:spot=db.execute("SELECT * FROM parking_spots WHERE id=?",(pid,)).fetchone()
        rooms=db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.building,r.room_number").fetchall()
        db.close()
        a=f'/parking/{pid}/edit' if pid else '/parking/create'
        t='编辑车位' if pid else '添加车位'
        sn=h(spot['spot_number'] if spot else '')
        fl=h(spot['floor_zone'] or'') if spot else ''
        mf=spot['monthly_fee'] if spot else 0
        st=spot['status'] if spot else 'occupied'
        nt=h(spot['notes'] or'') if spot else ''
        rm_sel=''
        if spot and spot['room_id']: rm_sel=str(spot['room_id'])
        opts='<option value="">--不绑定--</option>'+''.join(f'<option value="{r["id"]}"{" selected" if rm_sel==str(r["id"]) else""}>{h(r["building"])}-{h(r["room_number"])} ({h(r["oname"]or"")})</option>' for r in rooms)
        self._html(self._page(t,f'''<form method=POST action="{a}" class="row g-3">
    <div class="col-md-4"><label>车位号 <span class="text-danger">*</span></label><input name="spot_number" class="form-control" value="{sn}" required></div>
    <div class="col-md-4"><label>区域/楼层</label><input name="floor_zone" class="form-control" value="{fl}" placeholder="如：B1层/东区"></div>
    <div class="col-md-4"><label>月费(元)</label><input name="monthly_fee" type="number" class="form-control" value="{mf}" step="0.1" min="0"></div>
    <div class="col-md-6"><label>绑定房间</label><select name="room_id" class="form-select">{opts}</select></div>
    <div class="col-md-3"><label>状态</label><select name="status" class="form-select"><option value="occupied"{" selected" if st=="occupied" else""}>已占用</option><option value="vacant"{" selected" if st=="vacant" else""}>空置</option></select></div>
    <div class="col-md-3"><label>备注</label><input name="notes" class="form-control" value="{nt}"></div>
    <div class="col-12"><hr><button class="btn btn-primary"><i class="bi bi-check-lg"></i> 保存</button> <a href="/parking" class="btn btn-outline-secondary">取消</a></div></form>''','parking'))

    def _parking_create(self, d):
        db=get_db()
        rid=qs(d,'room_id')
        db.execute("INSERT INTO parking_spots(room_id,spot_number,floor_zone,monthly_fee,status,notes) VALUES(?,?,?,?,?,?)",
                   (int(rid) if rid else None,qs(d,'spot_number'),qs(d,'floor_zone'),
                    float(qs(d,'monthly_fee',0)),qs(d,'status','occupied'),qs(d,'notes')))
        db.commit();db.close()
        self._redirect('/parking?flash=添加成功')

    def _parking_edit(self, pid, d):
        db=get_db()
        rid=qs(d,'room_id')
        db.execute("UPDATE parking_spots SET room_id=?,spot_number=?,floor_zone=?,monthly_fee=?,status=?,notes=? WHERE id=?",
                   (int(rid) if rid else None,qs(d,'spot_number'),qs(d,'floor_zone'),
                    float(qs(d,'monthly_fee',0)),qs(d,'status','occupied'),qs(d,'notes'),pid))
        db.commit();db.close()
        self._redirect('/parking?flash=更新成功')

    def _parking_delete(self, pid):
        db=get_db();db.execute("DELETE FROM parking_spots WHERE id=?",(pid,));db.commit();db.close()
        self._redirect('/parking?flash=已删除')
