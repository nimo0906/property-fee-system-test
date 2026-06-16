#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Room tenant transfer workflow."""

from datetime import date

from server.backups import create_db_backup
from server.base import BaseHandler
from server.db import get_db, h, qs


def _room_row(room_id):
    db = get_db()
    row = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
    db.close()
    return row


def _today():
    return date.today().isoformat()


class TenantTransferMixin(BaseHandler):
    def _room_tenant_transfer_form(self, room_id):
        room = _room_row(room_id)
        if not room:
            return self._redirect('/rooms?flash=房间不存在')
        old_name = room['tenant_name'] or room['shop_name'] or '-'
        default_start = _today()
        self._html(self._page('转租登记', f'''
        <div class="alert alert-warning"><strong>转租登记说明：</strong>已生成账单不会改归属；转租后新生成账单会按新租户写入客户快照。</div>
        <form method="POST" action="/rooms/{room_id}/tenant_transfer" class="card">
          <div class="card-header"><i class="bi bi-arrow-left-right"></i> 转租登记 · {h(room['building'])}-{h(room['unit'])}-{h(room['room_number'])}</div>
          <div class="card-body row g-3">
            <div class="col-md-4"><label>原租户</label><input class="form-control" value="{h(old_name)}" disabled></div>
            <div class="col-md-4"><label>新租户姓名 *</label><input name="new_tenant_name" class="form-control" required></div>
            <div class="col-md-4"><label>新租户电话</label><input name="new_tenant_phone" class="form-control"></div>
            <div class="col-md-4"><label>转租生效日期 *</label><input name="effective_date" type="date" class="form-control" value="{default_start}" required></div>
            <div class="col-md-4"><label>新合同开始</label><input name="contract_start" type="date" class="form-control" value="{default_start}"></div>
            <div class="col-md-4"><label>新合同结束</label><input name="contract_end" type="date" class="form-control"></div>
            <div class="col-12"><label>备注</label><input name="notes" class="form-control" placeholder="例如：原租户无力承租，转租给第三人"></div>
            <div class="col-12 d-flex gap-2"><button class="btn btn-primary">确认转租</button><a href="/rooms" class="btn btn-outline-secondary">取消</a></div>
          </div>
        </form>''', 'rooms'))

    def _room_tenant_transfer_post(self, room_id, d):
        old = _room_row(room_id)
        if not old:
            return self._redirect('/rooms?flash=房间不存在')
        new_name = qs(d, 'new_tenant_name').strip()
        effective = qs(d, 'effective_date').strip()
        if not new_name or not effective:
            return self._redirect(f'/rooms/{room_id}/tenant_transfer?flash=请填写新租户和生效日期')
        backup = create_db_backup('auto_before_tenant_transfer')
        old_note = old['notes'] or ''
        transfer_note = f"转租：{old['tenant_name'] or '-'} -> {new_name}，生效日 {effective}"
        extra = qs(d, 'notes').strip()
        notes = '；'.join(x for x in [old_note, transfer_note, extra] if x)
        db = get_db()
        db.execute(
            """UPDATE rooms SET tenant_name=?,tenant_phone=?,contract_start=?,contract_end=?,notes=? WHERE id=?""",
            (new_name, qs(d, 'new_tenant_phone'), qs(d, 'contract_start') or effective, qs(d, 'contract_end'), notes, room_id),
        )
        db.commit(); db.close()
        self._audit('tenant_transfer', 'room', room_id, dict(old), {
            'tenant_name': new_name,
            'tenant_phone': qs(d, 'new_tenant_phone'),
            'effective_date': effective,
            'contract_start': qs(d, 'contract_start') or effective,
            'contract_end': qs(d, 'contract_end'),
            'backup': backup,
        }, '房间转租登记')
        return self._redirect('/rooms', flash='转租登记已完成，历史账单归属保持不变')
