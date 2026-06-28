#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alert center pages for commercial-complex v2."""

from server.alert_center import get_alert_center
from server.base import BaseHandler
from server.db import get_period, h, m
from server.ui_components import render_table


class AlertCenterMixin(BaseHandler):
    def _alert_center(self, q):
        period = (q.get("period") or [get_period()])[0]
        alerts = get_alert_center(period)
        s = alerts["summary"]
        severity_class = {
            "success": "alert-success",
            "warning": "alert-warning",
            "danger": "alert-danger",
        }.get(alerts["severity"], "alert-info")
        expiring_rows = "".join(
            f"""<tr><td><a href="/merchant_contracts/{r['id']}">{h(r['contract_no'])}</a></td><td>{h(r['merchant_name'])}</td><td>{h(r['building'])}-{h(r['room_number'])}</td><td>{h(r['end_date'])}</td>
            <td><div class='d-flex flex-column flex-sm-row gap-1'>
            <a class='btn btn-sm btn-outline-secondary' href='/merchant_contracts/{r['id']}'>查看</a>
            <a class='btn btn-sm btn-outline-primary' href='/merchant_contracts/{r['id']}/renew'>续签</a>
            <a class='btn btn-sm btn-outline-secondary' href='/merchant_contracts/{r['id']}/edit'>编辑</a></div></td></tr>"""
            for r in alerts["expiring_contracts"]
        )
        expired_rows = "".join(
            f"""<tr><td><a href="/merchant_contracts/{r['id']}">{h(r['contract_no'])}</a></td><td>{h(r['merchant_name'])}</td><td>{h(r['building'])}-{h(r['room_number'])}</td><td>{h(r['end_date'])}</td>
            <td><div class='d-flex flex-column flex-sm-row gap-1'>
            <a class='btn btn-sm btn-outline-secondary' href='/merchant_contracts/{r['id']}'>查看</a>
            <a class='btn btn-sm btn-outline-primary' href='/merchant_contracts/{r['id']}/renew'>续签</a>
            <a class='btn btn-sm btn-outline-danger' href='/merchant_contracts/{r['id']}/deactivate'>停用</a></div></td></tr>"""
            for r in alerts["expired_contracts"]
        )
        unpaid_rows = "".join(
            f"""<tr><td>{h(r['bill_number'])}</td><td>{h(r['contract_no'])}</td><td>{h(r['merchant_name'])}</td><td>{h(r['fee_name'])}</td><td class='text-end'>¥{m(r['amount'])}</td><td>{h(r['status'])}</td><td><a class='btn btn-sm btn-outline-success' href='/bills/{r['id']}/pay'>收费</a></td></tr>"""
            for r in alerts["unpaid_contract_bills"]
        )
        zero_rows = "".join(
            f"""<tr><td>{h(r['bill_number'])}</td><td>{h(r['building'])}-{h(r['room_number'])}</td><td>{h(r['fee_name'])}</td><td>{h(r['status'])}</td><td><a class='btn btn-sm btn-outline-warning' href='/bills/{r['id']}'>核对</a></td></tr>"""
            for r in alerts["zero_amount_bills"]
        )
        expiring_table = render_table(['合同', '商户', '铺位', '到期', ''], expiring_rows, table_class='table table-sm mb-0', empty_text='30天内暂无到期合同')
        expired_table = render_table(['合同', '商户', '铺位', '到期', ''], expired_rows, table_class='table table-sm mb-0', empty_text='暂无已过期合同')
        unpaid_table = render_table(['账单', '合同', '商户', '费用', ('金额', 'text-end'), '状态', ''], unpaid_rows, table_class='table table-sm mb-0', empty_text='暂无合同欠费账单')
        zero_table = render_table(['账单', '房间', '费用', '状态', ''], zero_rows, table_class='table table-sm mb-0', empty_text='暂无零金额账单')
        self._html(self._page("智能预警中心", f"""
        <div class="page-intro">
          <div>
            <h2 class="mb-1">智能预警中心</h2>
          </div>
          <div class="export-actions">
            <a class="btn btn-outline-primary btn-sm" href="/merchant_contracts"><i class="bi bi-folder"></i> 合同档案</a>
            <a class="btn btn-outline-secondary btn-sm" href="/bills"><i class="bi bi-receipt"></i> 账单管理</a>
          </div>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-md-3 col-6"><div class="summary-tile warning"><div class="label">30天内到期</div><strong>{s['contracts_expiring_30d']}</strong></div></div>
          <div class="col-md-3 col-6"><div class="summary-tile danger"><div class="label">已过期</div><strong>{s['expired_contracts']}</strong></div></div>
          <div class="col-md-3 col-6"><div class="summary-tile danger"><div class="label">合同欠费</div><strong>{s['unpaid_contract_bills']}</strong></div></div>
          <div class="col-md-3 col-6"><div class="summary-tile danger"><div class="label">零金额</div><strong>{s['zero_amount_bills']}</strong></div></div>
        </div>
        <div class="card mb-3"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><span><i class="bi bi-shop"></i> 商业合同应收</span><a class="btn btn-sm btn-outline-primary" href="/commercial_receivables">进入</a></div></div>
        <div class="row g-3">
          <div class="col-lg-6"><div class="card"><div class="card-header">即将到期合同</div>{expiring_table}</div></div>
          <div class="col-lg-6"><div class="card border-danger"><div class="card-header text-danger">已过期合同</div>{expired_table}</div></div>
          <div class="col-12"><div class="card border-danger"><div class="card-header text-danger">合同欠费账单</div>{unpaid_table}</div></div>
          <div class="col-12"><div class="card border-warning"><div class="card-header text-warning">异常账单：零金额</div>{zero_table}</div></div>
        </div>
        """, "alert_center"))
