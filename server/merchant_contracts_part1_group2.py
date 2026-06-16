from server.merchant_contracts_shared import *
from server.backups import create_db_backup
from server.special_rent import create_turnover_rent_bill, special_rule_for, SPECIAL_TYPES

class MerchantContractMixinPart1Group2(BaseHandler):
    def _merchant_contract_generate(self, contract_id, d):
        period = qs(d, "billing_period") or ""
        if not period:
            from server.db import get_period
            period = get_period()
        user = self._get_current_user() or {}
        result = generate_contract_bills(contract_id, period, operator=user.get("username") or "system")
        return self._redirect(
            f"/merchant_contracts?period={h(period)}",
            flash=f"已生成 {result['generated_count']} 笔合同账单，合计 {m(result['total_amount'])} 元",
        )

    def _merchant_contract_billing_preview(self, contract_id, q):
        db = get_db()
        contract = db.execute(
            "SELECT start_date FROM merchant_contracts WHERE id=?",
            (contract_id,),
        ).fetchone()
        db.close()
        if not contract:
            return self._redirect("/merchant_contracts?flash=合同不存在")
        service_start = qs(q, "service_start") or contract["start_date"]
        try:
            preview = build_contract_billing_preview(contract_id, service_start)
        except ValueError:
            return self._redirect("/merchant_contracts?flash=合同未启用，不能预览出账")
        contract = preview["contract"]
        rows = "".join(
            f"""<tr>
              <td><strong>{h(item['fee_name'])}</strong></td>
              <td>{h(item['service_start'])} 至 {h(item['service_end'])}<div class="small text-muted">{item['months']} 个月</div></td>
              <td>{h(item['billing_period'])}</td>
              <td class="text-end">¥{m(item['amount'])}</td>
              <td><span class="badge {'status-neutral' if item['exists'] else 'status-success'}">{'已存在' if item['exists'] else '可生成'}</span></td>
            </tr>"""
            for item in preview["items"]
        )
        can_generate = any((not item["exists"]) and float(item["amount"] or 0) > 0 for item in preview["items"])
        self._html(self._page("合同出账预览", f"""
        <div class="d-flex justify-content-between align-items-center mb-3">
          <div>
            <h2 class="h4 mb-1">合同出账预览</h2>
            <div class="text-muted">先核对服务期与金额，确认后才写入账单。</div>
          </div>
          <a href="/merchant_contracts" class="btn btn-outline-secondary btn-sm">返回合同列表</a>
        </div>
        <div class="card mb-3">
          <div class="card-header"><i class="bi bi-file-earmark-text"></i> {h(contract['contract_no'])} / {h(contract['merchant_name'])}</div>
          <div class="card-body">
            <form method="GET" action="/merchant_contracts/{contract_id}/billing" class="row g-2 align-items-end">
              <div class="col-md-4"><label>本次出账服务期起始日</label><input class="form-control" type="date" name="service_start" value="{h(service_start)}"></div>
              <div class="col-md-3"><button class="btn btn-outline-primary">重新预览</button></div>
            </form>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><i class="bi bi-search"></i> 将要生成的账单</div>
          <div class="table-responsive"><table class="table table-hover align-middle mb-0">
            <thead><tr><th>收费项目</th><th>出账服务期</th><th>账单期间</th><th class="text-end">金额</th><th>状态</th></tr></thead>
            <tbody>{rows}</tbody>
          </table></div>
          <div class="card-body text-end">
            <form method="POST" action="/merchant_contracts/{contract_id}/billing/confirm" class="d-inline">
              <input type="hidden" name="service_start" value="{h(service_start)}">
              <button class="btn btn-success" {'disabled' if not can_generate else ''}>确认导入并生成结果</button>
            </form>
          </div>
        </div>
        """, "merchant_contracts"))

    def _merchant_contract_billing_confirm(self, contract_id, d):
        service_start = qs(d, "service_start") or ""
        try:
            preview = build_contract_billing_preview(contract_id, service_start)
        except ValueError:
            return self._redirect("/merchant_contracts?flash=合同未启用，不能确认出账")
        user = self._get_current_user() or {}
        result = confirm_contract_billing(contract_id, preview["items"], operator=user.get("username") or "system")
        return self._redirect(
            "/merchant_contracts",
            flash=f"合同出账完成：新增 {result['generated_count']} 笔，合计 {m(result['total_amount'])} 元",
        )

    def _merchant_contract_turnover_rent_form(self, contract_id):
        db = get_db()
        contract = db.execute("SELECT * FROM merchant_contracts WHERE id=?", (contract_id,)).fetchone()
        rule = special_rule_for(db, contract_id)
        db.close()
        if not contract or not rule:
            return self._redirect(f"/merchant_contracts/{contract_id}?flash=该合同未设置特殊计租")
        self._html(self._page("销售额分成出账", f"""
        <div class="alert alert-warning">特殊计租需要先录入本期销售额，系统计算后由财务确认生成账单。</div>
        <form method="POST" action="/merchant_contracts/{contract_id}/turnover_rent" class="card">
          <div class="card-header">{h(contract['contract_no'])} / {h(contract['merchant_name'])}</div>
          <div class="card-body row g-3">
            <div class="col-md-3"><label>计租方式</label><input class="form-control" value="{h(SPECIAL_TYPES.get(rule['rent_mode'], rule['rent_mode']))}" disabled></div>
            <div class="col-md-3"><label>保底/月固定租金</label><input class="form-control" value="{m(rule['fixed_amount'])}" disabled></div>
            <div class="col-md-3"><label>分成比例</label><input class="form-control" value="{m(float(rule['turnover_rate'] or 0) * 100)}%" disabled></div>
            <div class="col-md-3"><label>账期</label><input type="month" name="billing_period" class="form-control" required></div>
            <div class="col-md-4"><label>本期销售额</label><input type="number" step="0.01" min="0" name="turnover_amount" class="form-control" required></div>
            <div class="col-md-8"><label>备注</label><input name="notes" class="form-control" placeholder="如：6月销售额分成，财务已核对"></div>
            <div class="col-12"><button class="btn btn-warning">确认生成销售额租金账单</button> <a class="btn btn-outline-secondary" href="/merchant_contracts/{contract_id}">返回</a></div>
          </div>
        </form>""", "merchant_contracts"))

    def _merchant_contract_turnover_rent_post(self, contract_id, d):
        try:
            create_db_backup("auto_before_turnover_rent_billing")
            user = self._get_current_user() or {}
            result = create_turnover_rent_bill(contract_id, qs(d, "billing_period"), qs(d, "turnover_amount"),
                                               user.get("username") or "system", qs(d, "notes"))
            self._audit("turnover_rent_billing", "merchant_contract", contract_id, None, result, "特殊计租销售额出账")
            return self._redirect(f"/merchant_contracts/{contract_id}", flash=f"销售额租金账单已生成：¥{m(result['amount'])}")
        except Exception as exc:
            return self._redirect(f"/merchant_contracts/{contract_id}/turnover_rent?flash={exc}")
