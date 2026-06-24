#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multipart workflows that combine contract lifecycle actions with attachments."""

from server.base import BaseHandler
from server.contract_billing import create_merchant_contract
from server.db import get_db, h
from server.merchant_contract_attachments import parse_multipart, save_contract_attachment
from server.merchant_contract_lifecycle import _contract_row


class MerchantContractAttachmentWorkflowMixin(BaseHandler):
    def _merchant_contract_deactivate_form(self, contract_id):
        contract = _contract_row(contract_id)
        if not contract:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        self._html(self._page("停用商户合同", f"""
        <form method="POST" action="/merchant_contracts/{contract_id}/deactivate" enctype="multipart/form-data" class="card border-danger">
          <div class="card-header text-danger"><i class="bi bi-exclamation-triangle"></i> 停用商户合同</div>
          <div class="card-body row g-3">
            <div class="col-12">合同 <strong>{h(contract['contract_no'])}</strong> 停用后不会删除历史账单，也不能继续预览出账。</div>
            <div class="col-md-6"><label>停用原因</label><input name="reason" class="form-control" placeholder="例如：退租、合同终止" required></div>
            <div class="col-md-6"><label>上传退租协议（可选）</label><input type="file" name="file" class="form-control" accept=".pdf,.jpg,.jpeg,.png"></div>
            <div class="col-12"><button class="btn btn-danger">确认停用</button> <a href="/merchant_contracts/{contract_id}" class="btn btn-outline-secondary">取消</a></div>
          </div>
        </form>""", "merchant_contracts"))

    def _merchant_contract_renew_post_multipart(self, contract_id, form=None):
        old = _contract_row(contract_id)
        if not old:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        form = parse_multipart(self, form)
        new_id = create_merchant_contract({
            "project_id": old["project_id"], "room_id": old["room_id"], "owner_id": old["owner_id"],
            "contract_no": form.getfirst("contract_no", ""), "merchant_name": old["merchant_name"],
            "shop_name": old["shop_name"], "rent_amount": old["rent_amount"], "rent_cycle": old["rent_cycle"],
            "property_rate": old["property_rate"], "property_cycle": old["property_cycle"],
            "deposit_amount": old["deposit_amount"], "start_date": form.getfirst("start_date", ""),
            "end_date": form.getfirst("end_date", ""), "status": "active", "notes": f"续签自 {old['contract_no']}",
        })
        user = self._get_current_user() or {}
        file_item = form["file"] if "file" in form else None
        attachment_id = None
        if file_item is not None and getattr(file_item, "filename", ""):
            attachment_id, error = save_contract_attachment(new_id, file_item, "续签合同", user.get("username") or "")
            if error:
                return self._redirect(f"/merchant_contracts/{contract_id}/renew?flash={error}")
        self._audit("merchant_contract_renew", "merchant_contract", contract_id, dict(old), {"new_contract_id": new_id, "attachment_id": attachment_id}, "合同续签")
        return self._redirect("/merchant_contracts", flash="合同续签已创建")

    def _merchant_contract_deactivate_multipart(self, contract_id, form=None):
        old = _contract_row(contract_id)
        if not old:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        form = parse_multipart(self, form)
        db = get_db()
        notes = ((old["notes"] or "") + "；停用原因：" + (form.getfirst("reason", "") or "未填写")).strip("；")
        db.execute("UPDATE merchant_contracts SET status='inactive',notes=? WHERE id=?", (notes, contract_id))
        db.commit(); db.close()
        user = self._get_current_user() or {}
        file_item = form["file"] if "file" in form else None
        attachment_id = None
        if file_item is not None and getattr(file_item, "filename", ""):
            attachment_id, error = save_contract_attachment(contract_id, file_item, "退租协议", user.get("username") or "")
            if error:
                return self._redirect(f"/merchant_contracts/{contract_id}?flash={error}")
        new = dict(_contract_row(contract_id))
        new["attachment_id"] = attachment_id
        self._audit("merchant_contract_deactivate", "merchant_contract", contract_id, dict(old), new, "停用商户合同")
        return self._redirect("/merchant_contracts", flash="商户合同已停用，历史账单保留")
