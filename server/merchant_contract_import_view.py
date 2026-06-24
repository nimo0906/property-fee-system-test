#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render editable preview for commercial contract imports."""

from server.db import h, m, n


def _input(i, key, value, typ="text", step=""):
    step_attr = f' step="{h(step)}"' if step else ""
    return f'<input class="form-control form-control-sm" type="{typ}"{step_attr} name="{key}_{i}" value="{h(value)}">'


def _cycle_options(value):
    labels = [("monthly", "月付"), ("quarterly", "季付"), ("semiannual", "半年付"), ("yearly", "年付")]
    return "".join(f'<option value="{key}" {"selected" if key == value else ""}>{label}</option>' for key, label in labels)


def _rent_mode_options(value):
    labels = [("fixed", "固定租金"), ("fixed_plus_turnover", "固定+销售额分成"),
              ("higher_of_fixed_or_turnover", "保底/分成取高"), ("turnover_only", "纯销售额分成")]
    return "".join(f'<option value="{key}" {"selected" if key == value else ""}>{label}</option>' for key, label in labels)


def _problem_rows(rows, blocking_only=False):
    items = []
    for r in rows:
        errors = r.get("errors") or []
        if blocking_only:
            errors = [e for e in errors if e != "百分比/销售额租金需人工核对"]
        if not errors:
            continue
        raw = " | ".join(str(r.get(k) or "") for k in ("space_no", "contract_no", "merchant_name", "start_date", "end_date"))
        items.append({"row_no": r.get("row_no"), "reason": "；".join(errors), "raw": raw})
    return items


def _problem_card(handler, rows, title="合同问题行", blocking_only=False):
    problems = _problem_rows(rows, blocking_only)
    if not problems:
        return '<div class="card mb-3 import-review-card"><div class="card-header text-success">合同问题行</div><div class="card-body text-muted">暂无问题行。</div></div>'
    csv_link = ""
    if hasattr(handler, "_save_problem_rows_csv"):
        token = handler._save_problem_rows_csv(problems)
        csv_link = f'<a class="btn btn-sm btn-outline-primary" href="/import/problem_rows/{h(token)}.csv">下载问题行 CSV</a>'
    trs = "".join(f'<tr><td>{h(p["row_no"])}</td><td>{h(p["reason"])}</td><td><small>{h(p["raw"])}</small></td></tr>' for p in problems[:80])
    return f'''<div class="card mb-3 import-review-card border-warning"><div class="card-header d-flex justify-content-between align-items-center text-warning"><span>{h(title)}</span>{csv_link}</div>
    <div class="card-body small text-muted">请按 Excel 行号在下方核对表修正后再确认；系统不会写入仍有问题的合同。</div>
    <div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>行号</th><th>原因</th><th>原始数据</th></tr></thead><tbody>{trs}</tbody></table></div></div>'''


def _row_html(i, r):
    status = '<span class="badge status-success">可导入</span>'
    if r['errors']:
        status = '<span class="badge bg-warning text-dark">需核对</span><div class="small text-danger">' + h('；'.join(r['errors'])) + '</div>'
    return f"""<tr>
<td><input class="form-check-input" type="checkbox" name="include_{i}" value="1" checked>
<input type="hidden" name="row_no_{i}" value="{h(r['row_no'])}"><div class="small text-muted">Excel {h(r['row_no'])}</div></td>
<td>{_input(i, 'space_no', r['space_no'])}<div class="small text-muted">{h(r['space_no'])}</div></td>
<td>{_input(i, 'contract_no', r['contract_no'])}<div class="small text-muted">合同 {h(r['contract_no'])}</div></td>
<td>{_input(i, 'merchant_name', r['merchant_name'])}</td><td>{_input(i, 'shop_name', r['shop_name'])}</td>
<td>{_input(i, 'floor', r['floor'], 'number')}</td>
<td>{_input(i, 'start_date', r['start_date'], 'date')}<div class="small text-muted">{h(r['start_date'])} 至 {h(r['end_date'])}</div></td>
<td>{_input(i, 'end_date', r['end_date'], 'date')}<div class="small text-muted">期限 {h(r['lease_term'])}</div>{_input(i, 'lease_term', r['lease_term'])}</td>
<td>{_input(i, 'contract_area', r['contract_area'], 'number', '0.01')}<div class="small text-muted">合同面积 {n(r['contract_area'])}㎡</div></td>
<td>{_input(i, 'building_area', r['building_area'], 'number', '0.01')}<div class="small text-muted">建筑面积 {n(r['building_area'])}㎡</div></td>
<td>{_input(i, 'rent_rate', r['rent_rate'], 'number', '0.01')}<input type="hidden" name="rent_raw_{i}" value="{h(r.get('rent_raw',''))}"><div class="small text-muted">{h(r.get('rent_raw',''))}</div></td>
<td><select class="form-select form-select-sm" name="rent_mode_{i}">{_rent_mode_options(r.get('rent_mode','fixed'))}</select>
<div class="input-group input-group-sm mt-1"><input class="form-control" type="number" step="0.0001" name="turnover_rate_{i}" value="{h(r.get('turnover_rate',0))}"><span class="input-group-text">分成</span></div></td>
<td>{_input(i, 'property_rate', r['property_rate'], 'number', '0.01')}</td>
<td>{_input(i, 'deposit_amount', r['deposit_amount'], 'number', '0.01')}</td>
<td><select class="form-select form-select-sm" name="rent_cycle_{i}">{_cycle_options(r['rent_cycle'])}</select></td>
<td>{_input(i, 'water_rate', r['water_rate'], 'number', '0.01')}</td><td>{_input(i, 'electricity_rate', r['electricity_rate'], 'number', '0.01')}</td>
<td>{_input(i, 'notes', r['notes'])}</td><td>{status}</td>
</tr>"""


def render_contract_import_preview(handler, filename, token, rows):
    body = "".join(_row_html(i, r) for i, r in enumerate(rows[:200]))
    body = body or '<tr><td colspan="19" class="text-center text-muted py-4">未识别到可导入合同</td></tr>'
    disabled = "disabled" if not rows else ""
    problem_html = _problem_card(handler, rows[:200], "合同问题行")
    html = f"""
<div class="alert alert-warning"><i class="bi bi-search"></i> 在租合同导入预览：只读取 Excel 的“在租合同”sheet，其余 sheet 不导入。请先核对商铺号、合同编号、面积和合同期。</div>
{problem_html}
<div class="card import-review-card">
  <div class="card-header d-flex justify-content-between align-items-center"><span>可编辑核对表 · {h(filename)} · {len(rows)} 条</span><a class="btn btn-sm btn-outline-secondary" href="/import?data_type=commercial_contracts">重新上传</a></div>
  <form method="POST" action="/import/upload">
    <input type="hidden" name="mode" value="confirm_commercial_contracts"><input type="hidden" name="data_type" value="commercial_contracts"><input type="hidden" name="upload_token" value="{h(token)}"><input type="hidden" name="filename" value="{h(filename)}">
    <input type="hidden" name="row_count" value="{len(rows[:200])}">
    <div class="table-responsive import-sticky-scroll"><table class="table table-sm table-hover align-middle mb-0 import-edit-table">
      <thead><tr><th>导入</th><th>商户编号</th><th>合同编号</th><th>承租人</th><th>经营品牌</th><th>楼层</th><th>开始日期</th><th>结束/期限</th><th>合同面积</th><th>建筑面积</th><th>保底租金单价</th><th>计租方式/分成</th><th>物业费单价</th><th>押金</th><th>交租方式</th><th>水费</th><th>电费</th><th>备注</th><th>状态</th></tr></thead>
      <tbody>{body}</tbody></table></div>
    <div class="card-body text-end"><button class="btn btn-success" {disabled}>确认导入合同档案</button></div>
  </form>
</div>"""
    handler._html(handler._page("在租合同导入预览", html, "merchant_contracts"))


def render_contract_import_second_review(handler, filename, rows, created, updated):
    body = "".join(_row_html(i, r) for i, r in enumerate(rows))
    problem_html = _problem_card(handler, rows, "合同问题行二次校对", True)
    html = f"""
<div class="alert alert-warning"><strong>已导入：新增 {created} 条，更新 {updated} 条。</strong> 以下合同仍有问题，暂未写入；请直接修正后再次确认。</div>
{problem_html}
<div class="card import-review-card">
  <div class="card-header d-flex justify-content-between align-items-center"><span>合同问题行二次校对 · {h(filename)} · {len(rows)} 条</span><a class="btn btn-sm btn-outline-secondary" href="/import?data_type=commercial_contracts">重新上传</a></div>
  <form method="POST" action="/import/upload">
    <input type="hidden" name="mode" value="confirm_commercial_contracts"><input type="hidden" name="data_type" value="commercial_contracts"><input type="hidden" name="filename" value="{h(filename)}">
    <input type="hidden" name="row_count" value="{len(rows)}">
    <div class="table-responsive import-sticky-scroll"><table class="table table-sm table-hover align-middle mb-0 import-edit-table">
      <thead><tr><th>导入</th><th>商户编号</th><th>合同编号</th><th>承租人</th><th>经营品牌</th><th>楼层</th><th>开始日期</th><th>结束/期限</th><th>合同面积</th><th>建筑面积</th><th>保底租金单价</th><th>计租方式/分成</th><th>物业费单价</th><th>押金</th><th>交租方式</th><th>水费</th><th>电费</th><th>备注</th><th>状态</th></tr></thead>
      <tbody>{body}</tbody></table></div>
    <div class="card-body text-end"><button class="btn btn-success">修正后再次确认导入</button></div>
  </form>
</div>"""
    handler._html(handler._page("合同问题行二次校对", html, "merchant_contracts"))
