#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract transfer workflow."""

from datetime import date, timedelta

from server.backups import create_db_backup
from server.base import BaseHandler
from server.contract_billing import create_merchant_contract
from server.db import get_db, h, m, n, qs
from server.merchant_contract_lifecycle_shared import _contract_row


def _prev_day(value):
    try:
        return (date.fromisoformat(value[:10]) - timedelta(days=1)).isoformat()
    except Exception:
        return value


def _space_no(contract):
    if contract['commercial_space_id']:
        db = get_db()
        row = db.execute('SELECT space_no FROM commercial_spaces WHERE id=?', (contract['commercial_space_id'],)).fetchone()
        db.close()
        return row['space_no'] if row else ''
    return ''


class MerchantContractTransferMixin(BaseHandler):
    def _merchant_contract_transfer_form(self, contract_id):
        c = _contract_row(contract_id)
        if not c:
            return self._redirect('/merchant_contracts?flash=合同不存在')
        default_no = f"{c['contract_no']}-T1"
        self._html(self._page('合同转租登记', f'''
        <div class="alert alert-warning"><strong>合同转租说明：</strong>系统会停用原合同并新建第三方承租合同；原合同已生成账单不改归属。</div>
        <form method="POST" action="/merchant_contracts/{contract_id}/transfer" class="card">
          <div class="card-header"><i class="bi bi-arrow-left-right"></i> 合同转租登记 · {h(c['contract_no'])}</div>
          <div class="card-body row g-3">
            <div class="col-md-4"><label>原商户</label><input class="form-control" value="{h(c['merchant_name'])}" disabled></div>
            <div class="col-md-4"><label>新合同编号 *</label><input name="new_contract_no" class="form-control" value="{h(default_no)}" required></div>
            <div class="col-md-4"><label>转租生效日期 *</label><input name="effective_date" type="date" class="form-control" value="{h(date.today().isoformat())}" required></div>
            <div class="col-md-4"><label>新商户/使用方 *</label><input name="new_merchant_name" class="form-control" required></div>
            <div class="col-md-4"><label>新店铺名称</label><input name="new_shop_name" class="form-control"></div>
            <div class="col-md-4"><label>新合同结束日期 *</label><input name="end_date" type="date" class="form-control" value="{h(c['end_date'])}" required></div>
            <div class="col-12"><label>备注</label><input name="notes" class="form-control" placeholder="转租原因或交接说明"></div>
            <div class="col-12 small text-muted">租金 {m(c['rent_amount'])} 元/月，物业费 {n(c['property_rate'])} 元/m²·月，面积 {n(c['contract_area'] or c['area'])}㎡ 将沿用到新合同。</div>
            <div class="col-12 d-flex gap-2"><button class="btn btn-primary">确认转租并新建合同</button><a href="/merchant_contracts/{contract_id}" class="btn btn-outline-secondary">取消</a></div>
          </div>
        </form>''', 'merchant_contracts'))

    def _merchant_contract_transfer_post(self, contract_id, d):
        old = _contract_row(contract_id)
        if not old:
            return self._redirect('/merchant_contracts?flash=合同不存在')
        effective = qs(d, 'effective_date').strip()
        new_name = qs(d, 'new_merchant_name').strip()
        new_no = qs(d, 'new_contract_no').strip()
        if not effective or not new_name or not new_no:
            return self._redirect(f'/merchant_contracts/{contract_id}/transfer?flash=请填写转租必填项')
        backup = create_db_backup('auto_before_contract_transfer')
        db = get_db()
        old_notes = ((old['notes'] or '') + f"；转租给 {new_name}，生效日 {effective}").strip('；')
        db.execute("UPDATE merchant_contracts SET status='inactive',end_date=?,notes=? WHERE id=?", (_prev_day(effective), old_notes, contract_id))
        if old['commercial_space_id']:
            db.execute("UPDATE commercial_spaces SET merchant_name=?,shop_name=?,status='active' WHERE id=?", (new_name, qs(d, 'new_shop_name') or new_name, old['commercial_space_id']))
        db.commit(); db.close()
        new_id = create_merchant_contract({
            'project_id': old['project_id'], 'room_id': old['room_id'], 'commercial_space_id': old['commercial_space_id'], 'owner_id': old['owner_id'],
            'contract_no': new_no, 'merchant_name': new_name, 'shop_name': qs(d, 'new_shop_name') or new_name,
            'rent_amount': old['rent_amount'], 'rent_cycle': old['rent_cycle'], 'property_rate': old['property_rate'], 'property_cycle': old['property_cycle'],
            'deposit_amount': old['deposit_amount'], 'contract_area': old['contract_area'] or old['area'], 'building_area': old['building_area'] or old['area'],
            'start_date': effective, 'end_date': qs(d, 'end_date'), 'status': 'active', 'notes': (qs(d, 'notes') or f"转租自 {old['contract_no']}"),
        })
        self._audit('merchant_contract_transfer', 'merchant_contract', contract_id, dict(old), {
            'new_contract_id': new_id, 'new_contract_no': new_no, 'merchant_name': new_name,
            'effective_date': effective, 'backup': backup, 'space_no': _space_no(old),
        }, '商户合同转租')
        return self._redirect(f'/merchant_contracts/{new_id}', flash='合同转租已完成，原合同账单归属保持不变')
