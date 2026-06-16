#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contract amendment recognition and confirmation pages."""

from server.base import BaseHandler
from server.backups import create_db_backup
from server.contract_amendments import create_draft_from_attachment, confirm_draft
from server.db import get_db, h, qs
from server.merchant_contract_attachments import _attachment_path


class ContractAmendmentMixin(BaseHandler):
    def _contract_amendment_recognize(self, contract_id, attachment_id):
        db = get_db()
        row = db.execute("SELECT * FROM contract_attachments WHERE id=? AND contract_id=?", (attachment_id, contract_id)).fetchone()
        if not row:
            db.close(); return self._redirect(f'/merchant_contracts/{contract_id}?flash=附件不存在')
        path = _attachment_path(contract_id, row['stored_name'])
        if not path:
            db.close(); return self._redirect(f'/merchant_contracts/{contract_id}?flash=附件文件不存在')
        draft_id = create_draft_from_attachment(db, contract_id, attachment_id, path)
        db.commit(); db.close()
        self._audit('contract_amendment_recognize', 'merchant_contract', contract_id, None, {'draft_id': draft_id}, '补充协议本地识别草案')
        return self._redirect(f'/merchant_contracts/{contract_id}/amendments/{draft_id}', flash='补充协议识别草案已生成，请核对后确认')

    def _contract_amendment_draft(self, contract_id, draft_id):
        db = get_db()
        d = db.execute('SELECT * FROM contract_amendment_drafts WHERE id=? AND contract_id=?', (draft_id, contract_id)).fetchone()
        db.close()
        if not d: return self._redirect(f'/merchant_contracts/{contract_id}?flash=草案不存在')
        self._html(self._page('补充协议识别草案', f'''<div class="alert alert-warning">系统识别仅供核对，确认后才影响后续商业合同出账；历史账单不会静默修改。</div>
        <form method="POST" action="/merchant_contracts/{contract_id}/amendments/{draft_id}/confirm" class="card"><div class="card-header">补充协议识别草案</div>
        <div class="card-body row g-3"><div class="col-md-4"><label>生效日期</label><input type="date" name="effective_date" class="form-control" value="{h(d['effective_date'] or '')}" required></div>
        <div class="col-md-4"><label>租金单价 元/m²·月</label><input name="rent_unit_price" type="number" step="0.0001" class="form-control" value="{h(d['rent_unit_price'] or '')}"></div>
        <div class="col-md-4"><label>月租金总额</label><input name="rent_amount" type="number" step="0.01" class="form-control" value="{h(d['rent_amount'] or '')}"></div>
        <div class="col-md-4"><label>物业费单价 元/m²·月</label><input name="property_rate" type="number" step="0.0001" class="form-control" value="{h(d['property_rate'] or '')}"></div>
        <div class="col-md-4"><label>租金周期</label><input name="rent_cycle" class="form-control" value="{h(d['rent_cycle'] or 'monthly')}"></div>
        <div class="col-md-4"><label>物业周期</label><input name="property_cycle" class="form-control" value="{h(d['property_cycle'] or 'monthly')}"></div>
        <div class="col-12"><label>备注</label><input name="notes" class="form-control" value="{h(d['notes'] or '')}"></div>
        <div class="col-12 small text-muted">识别置信度：{h(d['confidence'])}</div><div class="col-12"><button class="btn btn-primary">确认补充协议生效</button> <a class="btn btn-outline-secondary" href="/merchant_contracts/{contract_id}">返回</a></div></div></form>''', 'merchant_contracts'))

    def _contract_amendment_confirm(self, contract_id, draft_id, d):
        create_db_backup('auto_before_contract_amendment_confirm')
        db = get_db(); old = db.execute('SELECT * FROM contract_amendment_drafts WHERE id=?', (draft_id,)).fetchone()
        amendment_id = confirm_draft(db, draft_id, {'effective_date': qs(d, 'effective_date'), 'rent_unit_price': qs(d, 'rent_unit_price'), 'rent_amount': qs(d, 'rent_amount'), 'property_rate': qs(d, 'property_rate'), 'rent_cycle': qs(d, 'rent_cycle'), 'property_cycle': qs(d, 'property_cycle'), 'notes': qs(d, 'notes')})
        db.commit(); db.close()
        self._audit('contract_amendment_confirm', 'merchant_contract', contract_id, dict(old) if old else None, {'amendment_id': amendment_id}, '确认补充协议生效')
        return self._redirect(f'/merchant_contracts/{contract_id}', flash='补充协议已确认，后续出账将按生效日分段计算')
