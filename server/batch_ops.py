#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch update tools for internal operations."""

from server.base import BaseHandler
from server.backups import create_db_backup
from server.db import get_db, h, m, price, qs


class BatchOpsMixin(BaseHandler):

    def _batch_ops(self, q=None):
        db = get_db()
        blds = db.execute('SELECT DISTINCT building FROM rooms ORDER BY building').fetchall()
        cats = db.execute("SELECT DISTINCT category FROM rooms WHERE category IS NOT NULL AND category<>'' ORDER BY category").fetchall()
        fts = db.execute('SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order').fetchall()
        db.close()
        bld_opts = '<option value="">全部楼栋</option>' + ''.join(f'<option value="{h(r["building"])}">{h(r["building"])}</option>' for r in blds)
        cat_opts = '<option value="">全部类别</option>' + ''.join(f'<option value="{h(r["category"])}">{h(r["category"])}</option>' for r in cats)
        ft_opts = ''.join(f'<option value="{f["id"]}">{h(f["name"])} 当前¥{price(f["unit_price"])}</option>' for f in fts)
        self._html(self._page('批量更新', f'''
        <div class="page-intro">
          <div>
            <h2 class="mb-1">批量更新</h2>
          </div>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-md-4 col-6"><div class="summary-tile primary"><div class="label">房间楼栋</div><strong>{len(blds)}</strong></div></div>
          <div class="col-md-4 col-6"><div class="summary-tile success"><div class="label">收费项目</div><strong>{len(fts)}</strong></div></div>
          <div class="col-md-4 col-6"><div class="summary-tile warning"><div class="label">更新对象</div><strong>2 类</strong></div></div>
        </div>
        <div class="row g-3">
        <div class="col-lg-6"><div class="card"><div class="card-header">批量修改房间物业费单价</div><div class="card-body">
        <form method="POST" action="/batch_ops/room_rate" class="row g-3">
            <div class="col-md-6"><label>楼栋</label><select name="building" class="form-select">{bld_opts}</select></div>
            <div class="col-md-6"><label>类别</label><select name="category" class="form-select">{cat_opts}</select></div>
            <div class="col-md-6"><label>新单价 *</label><input name="custom_rate" type="number" step="0.01" min="0" class="form-control" required></div>
            <div class="col-md-6"><label>原因 *</label><input name="reason" class="form-control" required placeholder="如：2026年物业费调价"></div>
            <div class="col-12"><button name="mode" value="preview" class="btn btn-primary">预览</button><button name="mode" value="confirm" class="btn btn-success ms-2">直接执行</button></div>
        </form></div></div></div>
        <div class="col-lg-6"><div class="card"><div class="card-header">批量修改收费项目单价</div><div class="card-body">
        <form method="POST" action="/batch_ops/fee_rate" class="row g-3">
            <div class="col-md-12"><label>收费项目 *</label><select name="fee_type_id" class="form-select">{ft_opts}</select></div>
            <div class="col-md-6"><label>新默认单价 *</label><input name="unit_price" type="number" step="0.01" min="0" class="form-control" required></div>
            <div class="col-md-6"><label>原因 *</label><input name="reason" class="form-control" required></div>
            <div class="col-12"><button name="mode" value="preview" class="btn btn-primary">预览</button><button name="mode" value="confirm" class="btn btn-success ms-2">直接执行</button></div>
        </form></div></div></div></div>
        ''', 'batch_ops'))

    def _batch_room_rate(self, d):
        building = qs(d, 'building')
        category = qs(d, 'category')
        rate = float(qs(d, 'custom_rate', '0') or 0)
        reason = qs(d, 'reason')
        cond = []
        vals = []
        if building:
            cond.append('building=?'); vals.append(building)
        if category:
            cond.append('category=?'); vals.append(category)
        sql = 'SELECT id,building,unit,room_number,category,area,custom_rate FROM rooms'
        if cond:
            sql += ' WHERE ' + ' AND '.join(cond)
        sql += ' ORDER BY building,unit,room_number'
        db = get_db(); rows = db.execute(sql, vals).fetchall()
        if qs(d, 'mode') == 'preview':
            db.close(); return self._render_batch_preview('/batch_ops/room_rate', {'building':building,'category':category,'custom_rate':rate,'reason':reason}, rows, '房间物业费单价', lambda r: f'{h(r["building"])}-{h(r["room_number"])} {h(r["category"])}：¥{price(r["custom_rate"])} → ¥{price(rate)}')
        backup = create_db_backup('auto_before_batch_adjustment')
        old = [dict(r) for r in rows]
        db.execute('UPDATE rooms SET custom_rate=?' + ((' WHERE ' + ' AND '.join(cond)) if cond else ''), [rate] + vals)
        db.commit(); db.close()
        self._audit('batch_room_rate_update', 'rooms', None, old, {'custom_rate': rate, 'count': len(rows), 'backup': backup}, reason)
        self._redirect('/batch_ops?flash=已批量更新房间单价 ' + str(len(rows)) + ' 间，自动备份: ' + backup)

    def _batch_fee_rate(self, d):
        fid = int(qs(d, 'fee_type_id', '0') or 0)
        new_price = float(qs(d, 'unit_price', '0') or 0)
        reason = qs(d, 'reason')
        db = get_db(); ft = db.execute('SELECT * FROM fee_types WHERE id=?', (fid,)).fetchone()
        if not ft:
            db.close(); return self._redirect('/batch_ops?flash=收费项目不存在')
        if qs(d, 'mode') == 'preview':
            db.close(); return self._render_batch_preview('/batch_ops/fee_rate', {'fee_type_id':fid,'unit_price':new_price,'reason':reason}, [ft], '收费项目单价', lambda r: f'{h(r["name"])}：¥{price(r["unit_price"])} → ¥{price(new_price)}')
        backup = create_db_backup('auto_before_batch_adjustment')
        old = dict(ft)
        db.execute('UPDATE fee_types SET unit_price=? WHERE id=?', (new_price, fid))
        db.commit(); db.close()
        self._audit('batch_fee_rate_update', 'fee_type', fid, old, {'unit_price': new_price, 'backup': backup}, reason)
        self._redirect('/batch_ops?flash=收费项目单价已更新，自动备份: ' + backup)

    def _render_batch_preview(self, action, hidden_values, rows, title, render_line):
        hidden = ''.join(f'<input type="hidden" name="{h(k)}" value="{h(v)}">' for k, v in hidden_values.items())
        body = ''.join(f'<li>{render_line(r)}</li>' for r in rows[:100]) or '<li>没有匹配数据</li>'
        self._html(self._page('批量更新预览', f'''
        <div class="alert alert-warning">{h(title)}预览：将影响 <strong>{len(rows)}</strong> 条记录。确认执行前会自动备份。</div>
        <div class="card"><div class="card-header">前100条变化</div><div class="card-body"><ol>{body}</ol></div></div>
        <form method="POST" action="{h(action)}" class="mt-3"><input type="hidden" name="mode" value="confirm">{hidden}<button class="btn btn-success btn-lg" {'disabled' if not rows else ''}>确认执行</button> <a class="btn btn-outline-secondary btn-lg" href="/batch_ops">返回</a></form>
        ''', 'batch_ops'))
