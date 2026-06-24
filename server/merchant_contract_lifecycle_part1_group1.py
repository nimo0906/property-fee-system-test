from server.merchant_contract_lifecycle_shared import *
from server.special_rent import upsert_special_rent_rule

class MerchantContractLifecycleMixinPart1Group1(BaseHandler):
    def _merchant_contract_detail(self, contract_id):
        contract = _contract_row(contract_id)
        if not contract:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        bills = _contract_bills(contract_id)
        bill_total = sum(float(r["amount"] or 0) for r in bills)
        bill_rows = "".join(
            f"""<tr><td>{h(r['bill_number'])}</td><td>{h(r['fee_name'])}</td><td>{h(r['service_start'] or '-')} 至 {h(r['service_end'] or '-')}</td>
            <td class="text-end">¥{m(r['amount'])}</td><td>{h(contract_status_label(r['status']))}</td></tr>"""
            for r in bills
        ) or '<tr><td colspan="5" class="text-center text-muted py-3">暂无合同账单</td></tr>'
        db = get_db()
        audits = db.execute(
            """SELECT * FROM audit_logs
               WHERE entity_type='merchant_contract' AND entity_id=?
               ORDER BY id DESC LIMIT 20""",
            (contract_id,),
        ).fetchall()
        db.close()
        audit_rows = "".join(
            f"""<tr><td><small>{h(a['created_at'])}</small></td><td>{h(ACTION_LABELS.get(a['action'], a['action']))}</td>
            <td>{h(a['username'] or '-')}</td><td>{_audit_diff(a['old_value'], a['new_value'])}</td></tr>"""
            for a in audits
        ) or '<tr><td colspan="4" class="text-center text-muted py-3">暂无合同变更记录</td></tr>'
        self._html(self._page("合同详情", f"""
        <div class="d-flex justify-content-between align-items-center mb-3">
          <div><h2 class="h4 mb-1">合同详情</h2><div class="text-muted">{h(contract['contract_no'])} · {h(contract['merchant_name'])}</div></div>
          <div class="d-flex flex-wrap gap-2 justify-content-end">
            <a href="/merchant_contracts/{contract_id}/edit" class="btn btn-sm btn-outline-primary">编辑</a>
            <a href="/merchant_contracts/{contract_id}/renew" class="btn btn-sm btn-outline-info">续签合同</a>
            <a href="/merchant_contracts/{contract_id}/transfer" class="btn btn-sm btn-outline-warning">转租登记</a>
            <a href="/merchant_contracts/{contract_id}/bills" class="btn btn-sm btn-outline-secondary">查看已生成账单</a>
            <a href="/merchant_contracts/{contract_id}/deactivate" class="btn btn-sm btn-outline-danger">停用合同</a>
            <a href="/merchant_contracts" class="btn btn-sm btn-outline-secondary">返回列表</a>
          </div>
        </div>
        <div class="metric-grid">
          <div class="metric-card primary"><div class="metric-label">租金单价</div><div class="metric-value">{n(_rent_unit_price(contract['rent_amount'], contract['area'] if 'area' in contract.keys() else 0))}</div></div>
          <div class="metric-card success"><div class="metric-label">物业费单价</div><div class="metric-value">{n(contract['property_rate'])}</div></div>
          <div class="metric-card warning"><div class="metric-label">已生成账单</div><div class="metric-value">{len(bills)}</div></div>
          <div class="metric-card danger"><div class="metric-label">账单合计</div><div class="metric-value money">¥{m(bill_total)}</div></div>
        </div>
        <div class="card mb-3"><div class="card-header">合同基础信息</div><div class="card-body row g-2">
          <div class="col-md-3"><span class="text-muted small">合同期</span><div>{h(contract['start_date'])} 至 {h(contract['end_date'])}</div></div>
          <div class="col-md-3"><span class="text-muted small">合同面积</span><div>{n(contract['contract_area'] or contract['area'])}㎡</div></div>
          <div class="col-md-3"><span class="text-muted small">建筑面积</span><div>{n(contract['building_area'] or contract['area'])}㎡</div></div>
          <div class="col-md-3"><span class="text-muted small">租金周期</span><div>{h(CYCLE_LABELS.get(contract['rent_cycle'], contract['rent_cycle']))}</div></div>
          <div class="col-md-3"><span class="text-muted small">物业费周期</span><div>{h(CYCLE_LABELS.get(contract['property_cycle'], contract['property_cycle']))}</div></div>
          <div class="col-md-3"><span class="text-muted small">状态</span><div>{h(contract_status_label(contract['status']))}</div></div>
        </div></div>
        {render_special_rent_rule(contract_id)}
        {render_contract_attachments(contract_id)}
        {render_contract_amendments(contract_id)}
        <div class="card mb-3"><div class="card-header">已生成账单</div><div class="table-responsive"><table class="table table-sm mb-0">
          <thead><tr><th>账单号</th><th>费用</th><th>服务期</th><th class="text-end">金额</th><th>状态</th></tr></thead><tbody>{bill_rows}</tbody>
        </table></div></div>
        <div class="card"><div class="card-header">合同变更记录</div><div class="table-responsive"><table class="table table-sm align-middle mb-0">
          <thead><tr><th>时间</th><th>动作</th><th>操作人</th><th>字段差异</th></tr></thead><tbody>{audit_rows}</tbody>
        </table></div></div>
        """, "merchant_contracts"))

    def _merchant_contract_edit_form(self, contract_id):
        contract = _contract_row(contract_id)
        if not contract:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        count = _bill_count(contract_id)
        warning = ""
        if count:
            warning = f'<div class="alert alert-warning">已有账单 {count} 笔。修改金额或周期不会自动改历史账单，请财务核对后再保存。</div>'
        return_url = _safe_return_url(self.headers.get("Referer", ""), "/merchant_contracts")
        self._html(self._page(
            "编辑商户合同",
            _contract_form_html(contract, f"/merchant_contracts/{contract_id}/edit", "编辑商户合同", warning, return_url),
            "merchant_contracts",
        ))

    def _merchant_contract_edit_post(self, contract_id, d):
        old = _contract_row(contract_id)
        if not old:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        backup = create_db_backup("auto_before_contract_edit")
        space_id = _space_id_from_contract_form(d)
        room_id = qs(d, "room_id") if not space_id else None
        space_notes = qs(d, "space_notes") or qs(d, "notes")
        db = get_db()
        db.execute(
            """UPDATE merchant_contracts SET commercial_space_id=?,room_id=?,owner_id=?,contract_no=?,merchant_name=?,shop_name=?,
               rent_amount=?,rent_cycle=?,property_rate=?,property_cycle=?,deposit_amount=?,contract_area=?,building_area=?,
               start_date=?,end_date=?,status=?,notes=? WHERE id=?""",
            (
                int(space_id) if space_id else None, int(room_id) if room_id else None,
                qs(d, "owner_id") or None, qs(d, "contract_no"),
                qs(d, "merchant_name"), qs(d, "shop_name") or qs(d, "merchant_name"), _rent_monthly_total_from_form(d),
                qs(d, "rent_cycle") or "monthly", float(qs(d, "property_rate") or 0),
                qs(d, "property_cycle") or "monthly", _deposit_total_from_form(d),
                float(qs(d, "area") or 0), float(qs(d, "building_area") or qs(d, "area") or 0),
                qs(d, "start_date"), qs(d, "end_date"), qs(d, "status") or "active",
                qs(d, "notes"), contract_id,
            ),
        )
        if space_id:
            db.execute(
                """UPDATE commercial_spaces
                   SET space_no=?,shop_name=?,merchant_name=?,business_type=?,floor=?,area=?,water_rate_type=?,status='active',notes=?
                   WHERE id=?""",
                (
                    qs(d, "space_no").strip(), qs(d, "shop_name") or qs(d, "merchant_name"),
                    qs(d, "merchant_name") or qs(d, "shop_name"), qs(d, "business_type"),
                    int(float(qs(d, "floor") or 1)), float(qs(d, "area") or 0),
                    qs(d, "water_rate_type") or "非居民", space_notes, int(space_id),
                ),
            )
        upsert_special_rent_rule(db, contract_id, qs(d, "rent_mode"), qs(d, "turnover_rate"),
                                 _rent_monthly_total_from_form(d), qs(d, "notes"))
        db.commit(); db.close()
        new = dict(_contract_row(contract_id))
        new["backup"] = backup
        self._audit("merchant_contract_update", "merchant_contract", contract_id, dict(old), new, "编辑商户合同")
        return self._redirect("/merchant_contracts", flash="商户合同已更新")
