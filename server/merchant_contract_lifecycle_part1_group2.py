from server.merchant_contract_lifecycle_shared import *

class MerchantContractLifecycleMixinPart1Group2(BaseHandler):
    def _merchant_contract_delete(self, contract_id):
        contract = _contract_row(contract_id)
        if not contract:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        db = get_db()
        bill_count = db.execute(
            "SELECT COUNT(*) FROM bills WHERE source='merchant_contract' AND source_ref=?",
            (str(contract_id),),
        ).fetchone()[0]
        if bill_count:
            db.close()
            return self._redirect("/merchant_contracts?flash=已有合同账单，不能删除；可在详情页停用合同")
        db.execute("DELETE FROM contract_attachments WHERE contract_id=?", (contract_id,))
        db.execute("DELETE FROM contract_bill_runs WHERE contract_id=?", (contract_id,))
        db.execute("DELETE FROM merchant_contracts WHERE id=?", (contract_id,))
        db.commit(); db.close()
        self._audit("merchant_contract_delete", "merchant_contract", contract_id, dict(contract), {}, "删除商户合同")
        return self._redirect("/merchant_contracts", flash="合同档案已删除")

    def _merchant_contract_renew_form(self, contract_id):
        contract = _contract_row(contract_id)
        if not contract:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        self._html(self._page("合同续签", f"""
        <form method="POST" action="/merchant_contracts/{contract_id}/renew" enctype="multipart/form-data" class="card">
          <div class="card-header"><i class="bi bi-arrow-repeat"></i> 合同续签</div>
          <div class="card-body row g-3">
            <div class="col-12 text-muted">从原合同 <strong>{h(contract['contract_no'])}</strong> 复制商户、铺位、租金、物业费和押金，只填写新合同编号和新合同期。</div>
            <div class="col-md-4"><label>新合同编号</label><input name="contract_no" class="form-control" value="{h(contract['contract_no'])}-R1" required></div>
            <div class="col-md-4"><label>新开始日期</label><input name="start_date" type="date" class="form-control" required></div>
            <div class="col-md-4"><label>新结束日期</label><input name="end_date" type="date" class="form-control" required></div>
            <div class="col-md-8"><label>上传新合同扫描件（可选）</label><input type="file" name="file" class="form-control" accept=".pdf,.jpg,.jpeg,.png"></div>
            <div class="col-12"><button class="btn btn-primary">确认续签</button> <a href="/merchant_contracts" class="btn btn-outline-secondary">取消</a></div>
          </div>
        </form>""", "merchant_contracts"))

    def _merchant_contract_renew_post(self, contract_id, d):
        old = _contract_row(contract_id)
        if not old:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        new_id = create_merchant_contract({
            "project_id": old["project_id"], "room_id": old["room_id"], "commercial_space_id": old["commercial_space_id"], "owner_id": old["owner_id"],
            "contract_no": qs(d, "contract_no"), "merchant_name": old["merchant_name"],
            "shop_name": old["shop_name"], "rent_amount": old["rent_amount"], "rent_cycle": old["rent_cycle"],
            "property_rate": old["property_rate"], "property_cycle": old["property_cycle"],
            "deposit_amount": old["deposit_amount"], "contract_area": old["contract_area"], "building_area": old["building_area"], "start_date": qs(d, "start_date"),
            "end_date": qs(d, "end_date"), "status": "active", "notes": f"续签自 {old['contract_no']}",
        })
        self._audit("merchant_contract_renew", "merchant_contract", contract_id, dict(old), {"new_contract_id": new_id}, "合同续签")
        return self._redirect("/merchant_contracts", flash="合同续签已创建")

    def _merchant_contract_deactivate(self, contract_id, d):
        old = _contract_row(contract_id)
        if not old:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        backup = create_db_backup("auto_before_contract_deactivate")
        db = get_db()
        notes = ((old["notes"] or "") + "；停用原因：" + (qs(d, "reason") or "未填写")).strip("；")
        db.execute("UPDATE merchant_contracts SET status='inactive',notes=? WHERE id=?", (notes, contract_id))
        db.commit(); db.close()
        new = dict(_contract_row(contract_id))
        new["backup"] = backup
        self._audit("merchant_contract_deactivate", "merchant_contract", contract_id, dict(old), new, "停用商户合同")
        return self._redirect("/merchant_contracts", flash="商户合同已停用，历史账单保留")

    def _merchant_contract_bills(self, contract_id):
        contract = _contract_row(contract_id)
        if not contract:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        rows = _contract_bills(contract_id)
        body = "".join(
            f"""<tr><td>{h(r['bill_number'])}</td><td>{h(r['fee_name'])}</td><td>{h(r['service_start'] or '-')} 至 {h(r['service_end'] or '-')}</td>
            <td class="text-end">¥{m(r['amount'])}</td><td>{h(contract_status_label(r['status']))}</td><td><a class="btn btn-sm btn-outline-primary" href="/bills/{r['id']}">查看</a></td></tr>"""
            for r in rows
        ) or '<tr><td colspan="6" class="text-center text-muted py-4">暂无合同账单</td></tr>'
        self._html(self._page("合同已生成账单", f"""
        <div class="card"><div class="card-header d-flex justify-content-between">
          <span>合同已生成账单 · {h(contract['contract_no'])}</span><a href="/merchant_contracts/{contract_id}" class="btn btn-sm btn-outline-secondary">返回合同详情</a>
        </div><div class="table-responsive"><table class="table table-hover mb-0">
          <thead><tr><th>账单号</th><th>费用</th><th>服务期</th><th class="text-end">金额</th><th>状态</th><th></th></tr></thead>
          <tbody>{body}</tbody>
        </table></div></div>""", "merchant_contracts"))
