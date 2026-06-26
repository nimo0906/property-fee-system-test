#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner management."""

from server.db import get_db, h, m, n, qs
from server.base import BaseHandler
from server.pagination import pagination_state, query_items, render_pagination
from server.ui_components import render_form


class OwnerMixin(BaseHandler):

    def _owners(self, q):
        db=get_db();kw=qs(q,'keyword')
        o_sql="SELECT DISTINCT o.* FROM owners o"
        o_vals=[]
        if kw:o_sql+=" WHERE (o.name LIKE ? OR o.phone LIKE ?)";o_vals.extend([f'%{kw}%',f'%{kw}%'])
        o_sql+=" ORDER BY o.name"
        total_rows = db.execute("SELECT COUNT(*) FROM (" + o_sql + ")", o_vals).fetchone()[0]
        pg, per_page, total_pages = pagination_state(q, total_rows)
        owners=db.execute(o_sql + " LIMIT ? OFFSET ?", o_vals + [per_page, (pg - 1) * per_page]).fetchall()
        rh=''
        for o in owners:
            r_sql="SELECT * FROM rooms WHERE owner_id=? ORDER BY building,unit,room_number"
            rooms=db.execute(r_sql,(o['id'],)).fetchall()
            rc=len(rooms)
            room_detail=''
            for r in rooms:
                cs=(r['contract_start'] or '')[:7]; ce=(r['contract_end'] or '')[:7]
                ct=(cs+'~'+ce) if cs or ce else '-'
                rm=h(r['building']or'')+'-'+h(r['unit']or'')+'-'+h(r['room_number']or'')
                room_detail+=f'<tr class="owner-room-{o["id"]}" style="display:none"><td></td><td></td><td></td><td>{rm}</td><td><span class="badge status-{"info" if r["category"]=="商户" else "neutral"}">{h(r["category"]or"-")}</span></td><td class="text-end">{n(r["area"])}</td><td><small>{ct}</small></td><td><a href="/rooms/'+str(r['id'])+'/edit" class="btn btn-sm btn-outline-primary"><i class="bi bi-pencil"></i></a></td></tr>'
            rh+=f'<tr class="table-light" onclick="toggleOwnerRooms({o["id"]})" style="cursor:pointer">'
            rh+=f'<td><i class="bi bi-chevron-right" id="oicon_{o["id"]}"></i> <strong>{h(o["name"])}</strong></td>'
            rh+=f'<td>{h(o["phone"]or"-")}</td><td><small>{h(o["id_card"]or"-")}</small></td>'
            rh+=f'<td><span class="badge status-neutral">{rc}间</span></td><td></td><td></td><td></td>'
            rh+=f'<td><a href="/owners/{o["id"]}/edit" class="btn btn-sm btn-outline-primary"><i class="bi bi-pencil"></i></a>'
            rh+=f'<form method=POST action="/owners/{o["id"]}/delete" style=display:inline onsubmit="return confirm(\'确定删除？\')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'
            rh+=room_detail
        db.close()
        tpl=self._load_template('owners.html')
        tpl=tpl.replace('{KEYWORD}',h(kw))
        tpl=tpl.replace('{ROWS}',rh or '<tr><td colspan="8" class="text-center text-muted py-4">暂无业主，请先 <a href=\"/owners/create\">添加业主</a></td></tr>')
        page_links = render_pagination(
            '/owners',
            query_items(q, ['keyword']),
            pg,
            total_pages,
            per_page,
            total_rows,
            '业主分页',
        )
        tpl = tpl.replace('{PAGE_LINKS}', page_links)
        self._html(self._page('业主管理',tpl,'owners'))

    def _owner_form(self, oid):
        db=get_db();o=None
        if oid:o=db.execute("SELECT * FROM owners WHERE id=?",(oid,)).fetchone()
        db.close()
        a=f'/owners/{oid}/edit' if oid else '/owners/create'
        t='编辑业主' if oid else '添加业主'
        n=h(o['name'] if o else '');p=h(o['phone'] or'') if o else ''
        ic=h(o['id_card'] or'') if o else '';md=o['move_in_date'] if o else ''
        nt=h(o['notes'] or'') if o else ''
        fields_html = f'''
    <div class="col-md-6"><label>姓名 *</label><input name="name" class="form-control" value="{n}" required></div>
    <div class="col-md-6"><label>电话</label><input name="phone" class="form-control" value="{p}"></div>
    <div class="col-md-6"><label>身份证</label><input name="id_card" class="form-control" value="{ic}"></div>
    <div class="col-md-6"><label>入住日期</label><input name="move_in_date" type="date" class="form-control" value="{md}"></div>
    <div class="col-12"><label>备注</label><input name="notes" class="form-control" value="{nt}"></div>'''
        form_html = render_form(fields_html, action=a, submit_text='<i class="bi bi-check-lg"></i> 保存', cancel_url='/owners')
        self._html(self._page(t, form_html, 'owners'))

    def _owner_create(self, d):
        db=get_db()
        db.execute("INSERT INTO owners(name,phone,id_card,move_in_date,notes) VALUES(?,?,?,?,?)",
                   (qs(d,'name'),qs(d,'phone'),qs(d,'id_card'),qs(d,'move_in_date') or None,qs(d,'notes')))
        db.commit();db.close()
        self._redirect('/owners?flash=添加成功')

    def _owner_edit(self, oid, d):
        db=get_db()
        db.execute("UPDATE owners SET name=?,phone=?,id_card=?,move_in_date=?,notes=? WHERE id=?",
                   (qs(d,'name'),qs(d,'phone'),qs(d,'id_card'),qs(d,'move_in_date') or None,qs(d,'notes'),oid))
        db.commit();db.close()
        self._redirect('/owners?flash=更新成功')

    def _owner_delete(self, oid):
        db=get_db()
        db.execute("UPDATE rooms SET owner_id=NULL WHERE owner_id=?",(oid,))
        db.execute("DELETE FROM owners WHERE id=?",(oid,))
        db.commit();db.close()
        self._redirect('/owners?flash=已删除')
