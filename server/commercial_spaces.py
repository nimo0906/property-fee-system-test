#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial space master data for mall shops."""

from server.base import BaseHandler
from server.db import get_db, h, m, n, qs
from server.pagination import pagination_state, query_items, render_pagination


def create_commercial_space(data):
    db = get_db()
    cur = db.execute(
        """INSERT INTO commercial_spaces(project_id,space_no,floor,area,shop_name,merchant_name,business_type,water_rate_type,status,notes)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            int(data.get("project_id") or 1),
            data.get("space_no") or data.get("shop_no") or "",
            int(data.get("floor") or 1),
            float(data.get("area") or 0),
            data.get("shop_name") or data.get("merchant_name") or "",
            data.get("merchant_name") or data.get("shop_name") or "",
            data.get("business_type") or "",
            data.get("water_rate_type") or "非居民",
            data.get("status") or "active",
            data.get("notes") or "",
        ),
    )
    db.commit(); space_id = cur.lastrowid; db.close()
    return space_id


def get_commercial_space(space_id):
    db = get_db()
    row = db.execute("SELECT * FROM commercial_spaces WHERE id=?", (space_id,)).fetchone()
    db.close()
    return row


class CommercialSpaceMixin(BaseHandler):
    def _commercial_spaces(self, q):
        db = get_db()
        kw = qs(q, 'keyword').strip()
        sql = "SELECT * FROM commercial_spaces WHERE 1=1"
        vals = []
        if kw:
            like = f'%{kw}%'
            sql += " AND (space_no LIKE ? OR shop_name LIKE ? OR merchant_name LIKE ? OR business_type LIKE ?)"
            vals.extend([like] * 4)
        total_rows = db.execute("SELECT COUNT(*) FROM (" + sql + ")", vals).fetchone()[0]
        pg, per_page, total_pages = pagination_state(q, total_rows)
        rows = db.execute(sql + " ORDER BY status,space_no,id DESC LIMIT ? OFFSET ?", vals + [per_page, (pg - 1) * per_page]).fetchall()
        db.close()
        body = ''.join(
            f"""<tr><td><strong>{h(r['space_no'])}</strong></td><td>{h(r['shop_name'] or '-')}</td>
            <td>{h(r['merchant_name'] or '-')}</td><td>{h(r['business_type'] or '-')}</td><td>{r['floor'] or '-'}F</td>
            <td class="text-end">{n(r['area'])}</td><td>{h(r['water_rate_type'] or '非居民')}</td>
            <td><span class="badge {'status-success' if r['status']=='active' else 'status-neutral'}">{h(r['status'])}</span></td>
            <td class="text-end"><a class="btn btn-sm btn-outline-primary" href="/commercial_spaces/{r['id']}/edit">编辑</a></td></tr>"""
            for r in rows
        ) or '<tr><td colspan="9" class="text-center text-muted py-4">暂无空间档案</td></tr>'
        self._html(self._page('空间合同档案', f'''
        <div class="alert alert-info">空间档案作为行政档案/合同备查使用，不局限于商场；日常收费仍以房间管理和收费入口为准。</div>
        <div class="card"><div class="card-header d-flex justify-content-between"><span><i class="bi bi-shop"></i> 空间/铺位档案</span><a class="btn btn-primary btn-sm" href="/commercial_spaces/create">新增空间档案</a></div>
        <div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead><tr><th>铺位号</th><th>店铺</th><th>商户</th><th>业态</th><th>楼层</th><th class="text-end">面积</th><th>水费标准</th><th>状态</th><th class="text-end">操作</th></tr></thead><tbody>{body}</tbody></table></div></div>
        {render_pagination('/commercial_spaces', query_items(q, ['keyword']), pg, total_pages, per_page, total_rows, '商铺档案分页')}
        ''', 'merchant_contracts'))

    def _commercial_space_form(self, space_id=None):
        row = get_commercial_space(space_id) if space_id else None
        def val(k, default=''):
            return h(row[k] if row and row[k] is not None else default)
        action = f'/commercial_spaces/{space_id}/edit' if space_id else '/commercial_spaces/create'
        wt = val('water_rate_type', '非居民')
        status = val('status', 'active')
        self._html(self._page('编辑空间档案' if row else '新增空间档案', f'''
        <form method="POST" action="{action}" class="card"><div class="card-header">空间档案资料</div><div class="card-body row g-3">
        <div class="col-md-3"><label>铺位号 *</label><input name="space_no" class="form-control" value="{val('space_no')}" required></div>
        <div class="col-md-3"><label>店铺名称</label><input name="shop_name" class="form-control" value="{val('shop_name')}"></div>
        <div class="col-md-3"><label>商户名称</label><input name="merchant_name" class="form-control" value="{val('merchant_name')}"></div>
        <div class="col-md-3"><label>业态</label><input name="business_type" class="form-control" value="{val('business_type')}"></div>
        <div class="col-md-3"><label>楼层</label><input name="floor" type="number" class="form-control" value="{val('floor', 1)}"></div>
        <div class="col-md-3"><label>面积(m²) *</label><input name="area" type="number" step="0.01" class="form-control" value="{val('area', 0)}" required></div>
        <div class="col-md-3"><label>水费标准</label><select name="water_rate_type" class="form-select"><option value="非居民" {'selected' if wt=='非居民' else ''}>非居民</option><option value="特行" {'selected' if wt=='特行' else ''}>特行</option></select></div>
        <div class="col-md-3"><label>状态</label><select name="status" class="form-select"><option value="active" {'selected' if status=='active' else ''}>启用</option><option value="inactive" {'selected' if status=='inactive' else ''}>停用</option></select></div>
        <div class="col-12"><label>备注</label><input name="notes" class="form-control" value="{val('notes')}"></div>
        <div class="col-12"><hr><button class="btn btn-primary">保存</button> <a href="/merchant_contracts" class="btn btn-outline-secondary">取消</a></div>
        </div></form>''', 'merchant_contracts'))

    def _commercial_space_create(self, d):
        create_commercial_space({k: qs(d, k) for k in ['space_no','shop_name','merchant_name','business_type','floor','area','water_rate_type','status','notes']})
        return self._redirect('/merchant_contracts?flash=空间档案已保存')

    def _commercial_space_edit(self, space_id, d):
        db = get_db()
        db.execute("""UPDATE commercial_spaces SET space_no=?,shop_name=?,merchant_name=?,business_type=?,floor=?,area=?,water_rate_type=?,status=?,notes=? WHERE id=?""",
                   (qs(d,'space_no'), qs(d,'shop_name'), qs(d,'merchant_name'), qs(d,'business_type'), int(qs(d,'floor') or 1), float(qs(d,'area') or 0), qs(d,'water_rate_type','非居民'), qs(d,'status','active'), qs(d,'notes'), space_id))
        db.commit(); db.close()
        return self._redirect('/merchant_contracts?flash=空间档案已更新')
