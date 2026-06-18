#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enterprise dashboard analysis HTML snippets."""

from server.db import h, m


def render_enterprise_analysis(enterprise):
    segments = enterprise.get("segments", {})
    arrears = enterprise.get("arrears_trend", [])
    merchants = enterprise.get("merchant_contribution", [])
    fees = enterprise.get("fee_structure", [])
    comparison_items = sorted(
        segments.items(),
        key=lambda item: (float(item[1].get("due", 0) or 0), int(item[1].get("bill_count", 0) or 0)),
        reverse=True,
    )
    comparison_rows = "".join(
        f"""<tr><td>{h(name)}</td><td class="text-end">¥{m(data.get("due", 0))}</td>
        <td class="text-end">¥{m(data.get("paid", 0))}</td><td class="text-end">¥{m(data.get("unpaid", 0))}</td>
        <td class="text-end">{data.get("collection_rate", 0)}%</td></tr>"""
        for name, data in comparison_items
    ) or '<tr><td colspan="5" class="text-center text-muted py-3">暂无区域/业态对比数据</td></tr>'
    arrears_rows = "".join(
        f"""<tr><td>{h(item["period"])}</td><td class="text-end">¥{m(item["due"])}</td>
        <td class="text-end">¥{m(item["paid"])}</td><td class="text-end text-danger">¥{m(item["unpaid"])}</td></tr>"""
        for item in arrears
    ) or '<tr><td colspan="4" class="text-center text-muted py-3">暂无欠费趋势数据</td></tr>'
    merchant_rows = "".join(
        f"""<tr><td>{h(item["merchant"])}</td><td class="text-end">¥{m(item["due"])}</td>
        <td class="text-end">¥{m(item["paid"])}</td><td class="text-end">{item["bill_count"]}笔</td></tr>"""
        for item in merchants
    ) or '<tr><td colspan="4" class="text-center text-muted py-3">暂无商户贡献数据</td></tr>'
    fee_rows = "".join(
        f"""<tr><td>{h(item["fee_name"])}</td><td class="text-end">¥{m(item["due"])}</td>
        <td class="text-end">{item["bill_count"]}笔</td></tr>"""
        for item in fees
    ) or '<tr><td colspan="3" class="text-center text-muted py-3">暂无费用结构数据</td></tr>'
    return f"""
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-bar-chart-line"></i> 经营分析看板</div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-lg-6">
                <h6>区域 / 业态对比</h6>
                <div class="table-responsive"><table class="table table-sm align-middle mb-0">
                  <thead><tr><th>范围</th><th class="text-end">应收</th><th class="text-end">已收</th><th class="text-end">未收</th><th class="text-end">收缴率</th></tr></thead>
                  <tbody>{comparison_rows}</tbody>
                </table></div>
              </div>
              <div class="col-lg-6">
                <h6>欠费趋势</h6>
                <div class="table-responsive"><table class="table table-sm align-middle mb-0">
                  <thead><tr><th>月份</th><th class="text-end">应收</th><th class="text-end">已收</th><th class="text-end">欠费</th></tr></thead>
                  <tbody>{arrears_rows}</tbody>
                </table></div>
              </div>
              <div class="col-lg-6">
                <h6>商户贡献</h6>
                <div class="table-responsive"><table class="table table-sm align-middle mb-0">
                  <thead><tr><th>商户/店铺</th><th class="text-end">应收</th><th class="text-end">已收</th><th class="text-end">账单</th></tr></thead>
                  <tbody>{merchant_rows}</tbody>
                </table></div>
              </div>
              <div class="col-lg-6">
                <h6>费用结构</h6>
                <div class="table-responsive"><table class="table table-sm align-middle mb-0">
                  <thead><tr><th>收费项目</th><th class="text-end">应收</th><th class="text-end">笔数</th></tr></thead>
                  <tbody>{fee_rows}</tbody>
                </table></div>
              </div>
            </div>
          </div>
        </div>"""
