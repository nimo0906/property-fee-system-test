#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract pages for commercial-complex v2."""

from server.base import BaseHandler
from server.cloud_schema import build_postgres_schema
from server.contract_billing import create_merchant_contract, generate_contract_bills
from server.db import get_db, h, m, qs


class MerchantContractMixin(BaseHandler):
    def _merchant_contracts(self, q):
        db = get_db()
        rows = db.execute(
            """SELECT c.*,r.building,r.unit,r.room_number,r.area,o.name owner_name
               FROM merchant_contracts c
               JOIN rooms r ON c.room_id=r.id
               LEFT JOIN owners o ON c.owner_id=o.id
               ORDER BY c.status,c.end_date,c.id DESC"""
        ).fetchall()
        db.close()
        body = "".join(
            f"""<tr>
            <td><strong>{h(r['contract_no'])}</strong><div class="small text-muted">{h(r['merchant_name'])}</div></td>
            <td>{h(r['building'])}-{h(r['room_number'])}<div class="small text-muted">{h(r['shop_name'] or r['owner_name'] or '-')}</div></td>
            <td class="text-end">¥{m(r['rent_amount'])}</td>
            <td class="text-end">{m(r['property_rate'])} 元/m²</td>
            <td class="text-end">¥{m(r['deposit_amount'])}</td>
            <td>{h(r['start_date'])} 至 {h(r['end_date'])}</td>
            <td><span class="badge {'status-success' if r['status']=='active' else 'status-neutral'}">{h(r['status'])}</span></td>
            <td class="text-end">
              <form method="POST" action="/merchant_contracts/{r['id']}/generate" class="d-inline">
                <input type="hidden" name="billing_period" value="{h(qs(q,'period') or '')}">
                <button class="btn btn-sm btn-outline-success">生成本期账单</button>
              </form>
            </td>
            </tr>"""
            for r in rows
        ) or '<tr><td colspan="8" class="text-center text-muted py-4">暂无商户合同</td></tr>'
        self._html(self._page("商户合同", f"""
        <div class="alert alert-info"><i class="bi bi-file-earmark-text"></i>
        2.0 商场收费以合同为核心：租金、物业费、押金按合同生成账单，B座原收费流程保持稳定。</div>
        <div class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span><i class="bi bi-shop"></i> 商场商户合同</span>
            <a class="btn btn-primary btn-sm" href="/merchant_contracts/create"><i class="bi bi-plus-lg"></i> 新增合同</a>
          </div>
          <div class="table-responsive"><table class="table table-hover align-middle mb-0">
            <thead><tr><th>合同/商户</th><th>铺位</th><th class="text-end">租金/月</th><th class="text-end">物业单价</th><th class="text-end">押金</th><th>合同期</th><th>状态</th><th class="text-end">操作</th></tr></thead>
            <tbody>{body}</tbody>
          </table></div>
        </div>
        """, "merchant_contracts"))

    def _merchant_contract_form(self):
        db = get_db()
        rooms = db.execute(
            """SELECT r.id,r.building,r.unit,r.room_number,r.area,r.shop_name,r.custom_rate,r.owner_id,o.name owner_name
               FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
               WHERE (r.building='商场' OR r.unit='商场') AND r.category IN('商户','商业')
               ORDER BY r.room_number"""
        ).fetchall()
        db.close()
        options = "".join(
            f"""<option value="{r['id']}" data-owner="{r['owner_id'] or ''}" data-shop="{h(r['shop_name'] or r['owner_name'] or '')}" data-rate="{r['custom_rate'] or 0}">
            {h(r['building'])}-{h(r['room_number'])} / {h(r['shop_name'] or r['owner_name'] or '-')} / {m(r['area'])}m²</option>"""
            for r in rooms
        )
        self._html(self._page("新增商户合同", f"""
        <form method="POST" action="/merchant_contracts/create" class="card">
          <div class="card-header"><i class="bi bi-file-earmark-plus"></i> 合同基本信息</div>
          <div class="card-body row g-3">
            <div class="col-md-4"><label>商场铺位</label><select name="room_id" id="contractRoom" class="form-select" required>{options}</select></div>
            <div class="col-md-4"><label>合同编号</label><input name="contract_no" class="form-control" placeholder="如 HT-2026-001" required></div>
            <div class="col-md-4"><label>商户/店名</label><input name="merchant_name" id="merchantName" class="form-control" required></div>
            <input type="hidden" name="owner_id" id="ownerId">
            <div class="col-md-4"><label>租金（月）</label><input name="rent_amount" type="number" step="0.01" class="form-control" required></div>
            <div class="col-md-4"><label>物业费单价（元/m²·月）</label><input name="property_rate" id="propertyRate" type="number" step="0.0001" class="form-control" required></div>
            <div class="col-md-4"><label>押金</label><input name="deposit_amount" type="number" step="0.01" class="form-control" required></div>
            <div class="col-md-4"><label>开始日期</label><input name="start_date" type="date" class="form-control" required></div>
            <div class="col-md-4"><label>结束日期</label><input name="end_date" type="date" class="form-control" required></div>
            <div class="col-md-4"><label>备注</label><input name="notes" class="form-control"></div>
            <div class="col-12"><button class="btn btn-primary">保存合同</button> <a href="/merchant_contracts" class="btn btn-outline-secondary">取消</a></div>
          </div>
        </form>
        <script>
        function fillRoom(){{
          var o=document.getElementById('contractRoom').selectedOptions[0];
          if(!o) return;
          document.getElementById('ownerId').value=o.dataset.owner||'';
          document.getElementById('merchantName').value=o.dataset.shop||'';
          document.getElementById('propertyRate').value=o.dataset.rate&&o.dataset.rate!='0'?o.dataset.rate:'';
        }}
        document.getElementById('contractRoom').addEventListener('change',fillRoom); fillRoom();
        </script>
        """, "merchant_contracts"))

    def _merchant_contract_create(self, d):
        create_merchant_contract({
            "room_id": qs(d, "room_id"),
            "owner_id": qs(d, "owner_id") or None,
            "contract_no": qs(d, "contract_no"),
            "merchant_name": qs(d, "merchant_name"),
            "shop_name": qs(d, "merchant_name"),
            "rent_amount": qs(d, "rent_amount"),
            "property_rate": qs(d, "property_rate"),
            "deposit_amount": qs(d, "deposit_amount"),
            "start_date": qs(d, "start_date"),
            "end_date": qs(d, "end_date"),
            "notes": qs(d, "notes"),
        })
        return self._redirect("/merchant_contracts?flash=商户合同已保存")

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

    def _cloud_schema(self):
        sql = h(build_postgres_schema())
        self._html(self._page("云端数据底座", f"""
        <div class="alert alert-warning"><i class="bi bi-cloud-check"></i>
        这里是 2.0 云端 PostgreSQL 第一版 schema 合同，用于后续云端部署和 SQLite 数据迁移；当前本地系统仍可继续运行。</div>
        <pre class="cloud-schema-panel"><code>{sql}</code></pre>
        """, "cloud_schema"))
