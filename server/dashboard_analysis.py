#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enterprise dashboard analysis HTML snippets."""

from server.db import h, m
from server.ui_components import render_table


def render_enterprise_analysis(enterprise):
    segments = enterprise.get("segments", {})
    arrears = enterprise.get("arrears_trend", [])
    merchants = enterprise.get("merchant_contribution", [])
    fees = enterprise.get("fee_structure", [])
    comparison_rows = "".join(
        f"""<tr><td>{h(name)}</td><td class="text-end">¥{m(data.get("due", 0))}</td>
        <td class="text-end">¥{m(data.get("paid", 0))}</td><td class="text-end">¥{m(data.get("unpaid", 0))}</td>
        <td class="text-end">{data.get("collection_rate", 0)}%</td></tr>"""
        for name, data in segments.items()
        if name in ("B座", "商场")
    )
    arrears_rows = "".join(
        f"""<tr><td>{h(item["period"])}</td><td class="text-end">¥{m(item["due"])}</td>
        <td class="text-end">¥{m(item["paid"])}</td><td class="text-end text-danger">¥{m(item["unpaid"])}</td></tr>"""
        for item in arrears
    )
    merchant_rows = "".join(
        f"""<tr><td>{h(item["merchant"])}</td><td class="text-end">¥{m(item["due"])}</td>
        <td class="text-end">¥{m(item["paid"])}</td><td class="text-end">{item["bill_count"]}笔</td></tr>"""
        for item in merchants
    )
    fee_rows = "".join(
        f"""<tr><td>{h(item["fee_name"])}</td><td class="text-end">¥{m(item["due"])}</td>
        <td class="text-end">{item["bill_count"]}笔</td></tr>"""
        for item in fees
    )
    comparison_table = render_table(
        ['范围', ('应收', 'text-end'), ('已收', 'text-end'), ('未收', 'text-end'), ('收缴率', 'text-end')],
        comparison_rows,
        table_class='table table-sm align-middle mb-0',
        empty_text='暂无 B座 / 商场对比数据',
    )
    arrears_table = render_table(
        ['月份', ('应收', 'text-end'), ('已收', 'text-end'), ('欠费', 'text-end')],
        arrears_rows,
        table_class='table table-sm align-middle mb-0',
        empty_text='暂无欠费趋势数据',
    )
    merchant_table = render_table(
        ['商户/店铺', ('应收', 'text-end'), ('已收', 'text-end'), ('账单', 'text-end')],
        merchant_rows,
        table_class='table table-sm align-middle mb-0',
        empty_text='暂无商户贡献数据',
    )
    fee_table = render_table(
        ['收费项目', ('应收', 'text-end'), ('笔数', 'text-end')],
        fee_rows,
        table_class='table table-sm align-middle mb-0',
        empty_text='暂无费用结构数据',
    )
    return f"""
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-bar-chart-line"></i> 经营分析看板</div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-lg-6">
                <h6>B座 / 商场对比</h6>
                {comparison_table}
              </div>
              <div class="col-lg-6">
                <h6>欠费趋势</h6>
                {arrears_table}
              </div>
              <div class="col-lg-6">
                <h6>商户贡献</h6>
                {merchant_table}
              </div>
              <div class="col-lg-6">
                <h6>费用结构</h6>
                {fee_table}
              </div>
            </div>
          </div>
        </div>"""
