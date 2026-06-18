#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Views and helpers for import preview pages."""

from server.db import get_db, h, qs
from server.import_parser import summarize_rows
from server.basic_import import preview_basic_info_import
from server.import_cache import save_import_file
from server.import_batching import PREVIEW_BATCH_SIZE, batch_window
from server.payment_ledger import analyze_basic_info, analyze_payment_ledger


def _payment_cycle_select(name, value):
    labels = [('monthly', '月付'), ('quarterly', '季付'), ('semiannual', '半年付'), ('yearly', '年付')]
    current = str(value or '').strip()
    opts = ''.join(
        f'<option value="{h(code)}"{" selected" if code == current else ""}>{h(label)}</option>'
        for code, label in labels
    )
    return f'<select class="form-select form-select-sm" name="{h(name)}"><option value="">未设置</option>{opts}</select>'


class ImportPreviewMixin:
    def _col_map_from_form(self, form, current_map, header_count):
        has_manual_mapping = any(form.getvalue(f'col_{key}') is not None for key in self._manual_mapping_fields())
        if not has_manual_mapping:
            return current_map
        mapped = dict(current_map)
        for key in self._manual_mapping_fields():
            value = form.getvalue(f'col_{key}', '')
            if value == '':
                mapped.pop(key, None)
                continue
            try:
                idx = int(value)
            except ValueError:
                continue
            if 0 <= idx < header_count:
                mapped[key] = idx
        return mapped

    def _manual_mapping_fields(self):
        return [
            'building', 'unit', 'room_number', 'floor', 'category', 'area',
            'owner_name', 'owner_phone', 'tenant_name', 'tenant_phone', 'tenant_id_card', 'shop_name',
            'business_type', 'custom_rate', 'payment_cycle', 'water_rate_type', 'contract_start', 'contract_end', 'rent_period',
        ]

    def _field_labels(self):
        return {
            'building': '楼栋/区域', 'unit': '单元/分区', 'room_number': '房号/铺位号',
            'floor': '楼层', 'category': '类别', 'area': '面积',
            'owner_name': '业主/商户', 'owner_phone': '电话',
            'tenant_name': '租户', 'tenant_phone': '租户电话', 'tenant_id_card': '租户身份证号', 'shop_name': '店铺名称',
            'business_type': '业态', 'custom_rate': '物业费单价', 'payment_cycle': '缴费周期',
            'water_rate_type': '水费标准', 'contract_start': '合同开始日期', 'contract_end': '合同到期日期', 'rent_period': '催缴租金租期',
        }

    def _render_import_preview(self, filename, headers, data_rows, col_map, data_type, header_idx, upload_token, import_offset=0):
        type_names = {"owners": "业主信息", "rooms": "收费对象信息", "bills": "账单记录", "payment_ledger": "收款明细表", "unknown": "未知类型"}
        detected_tip = f'<div class="alert alert-info"><strong>系统识别为：{h(type_names.get(data_type, data_type))}</strong>。如识别不准确，请返回导入页手动选择类型后重新预览。</div>'
        warning = ''
        if data_type == 'payment_ledger':
            db = get_db()
            rooms = [dict(r) for r in db.execute("SELECT building, room_number, category, area FROM rooms").fetchall()]
            db.close()
            analysis = analyze_payment_ledger(headers, data_rows, rooms)
            stats_rows = ''.join(
                f'<tr><td>{h(x["name"])}</td><td>{h(x["action"])}</td><td>{x["positive"]}</td><td>{x["negative"]}</td><td>{h(x["total"])}</td><td>{h(x["note"])}</td></tr>'
                for x in analysis['fee_stats']
            )
            fee_mapping_form = self._render_fee_mapping_form(filename, upload_token, analysis['fee_stats'])
            examples = '、'.join(h(x) for x in analysis['unmatched_examples']) or '-'
            room_types = '、'.join(f'{h(k)} {v}行' for k, v in analysis['room_types']) or '-'
            payment_html = f'''
            <div class="alert alert-warning"><strong>已识别为收款明细表。</strong> 历史金额只用于识别收费项目列，不会自动入账。</div>
            <div class="card mb-3 import-review-card"><div class="card-header"><i class="bi bi-receipt-cutoff"></i> 收费项目识别分析</div>
            <div class="card-body"><p class="small text-muted">房间类型：{room_types}</p><p class="small text-muted">未匹配示例：{examples}</p>
            <div class="table-responsive"><table class="table table-sm"><thead><tr><th>收费项目列</th><th>识别结果</th><th>正数行</th><th>负数行</th><th>金额合计</th><th>说明</th></tr></thead><tbody>{stats_rows}</tbody></table></div></div></div>{fee_mapping_form}'''
            self._html(self._page('导入预览', payment_html, 'import'))
            return
        elif data_type == 'unknown':
            warning = '<div class="alert alert-warning">未能可靠判断数据类型，请检查列头或手动选择导入类型。</div>'

        db = get_db()
        result = preview_basic_info_import(db, headers, data_rows, col_map)
        db.close()
        changed_rooms = result.get('changed_rooms', [])
        total_changed = len(changed_rooms)
        batch_start, batch_end, batch_count, has_next = batch_window(total_changed, import_offset, PREVIEW_BATCH_SIZE)
        batch_rooms = changed_rooms[batch_start:batch_end]
        next_offset = batch_end
        review_rows = self._render_mapped_review_rows(batch_rooms, col_map, headers)
        batch_label = '暂无可导入数据' if not total_changed else f'当前批次：第 {batch_start + 1} - {batch_end} 条，共 {total_changed} 条'
        batch_tip = '确认后可继续导入后续数据。' if has_next else '当前文件已到最后一批；完成后“继续导入”用于导入其他文件。'
        batch_total = ((total_changed - 1) // PREVIEW_BATCH_SIZE + 1) if total_changed else 0
        batch_no = (batch_start // PREVIEW_BATCH_SIZE + 1) if total_changed else 0
        batch_percent = int((batch_end / total_changed) * 100) if total_changed else 0
        batch_remaining = max(0, total_changed - batch_end)
        problem_rows = result.get('problem_rows', [])
        problem_csv = ''
        if problem_rows:
            token = self._save_problem_rows_csv(problem_rows)
            problem_csv = f'<a class="btn btn-sm btn-outline-primary" href="/import/problem_rows/{h(token)}.csv"><i class="bi bi-download"></i> 下载问题行 CSV</a>'
        problem_html = self._render_problem_summary(problem_rows, problem_csv)
        mapping_summary = self._render_mapping_summary(headers, col_map)
        mapping_form = self._render_mapping_form(
            filename, headers, col_map, data_type, upload_token, collapsed=True, import_offset=batch_start
        )
        advanced_html = self._render_advanced_import_info(
            filename, headers, data_rows[batch_start:batch_end], col_map, data_type, header_idx, result, type_names, len(data_rows)
        )
        self._html(self._page('导入预览', f'''
        <div class="import-hero import-hero-pro import-hero-compact">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
                <div><div class="page-kicker">IMPORT REVIEW</div><h4 class="mb-2">确认即将导入的数据</h4>
                <p class="mb-0 text-muted">当前页面只预览，不写入数据库。请先核对映射结果，确认后才会导入并自动备份。</p></div>
                <a href="/import" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> 返回导入页</a>
            </div>
        </div>
        {detected_tip}
        {warning}
        {mapping_summary}
        {mapping_form}
        <div class="card mb-3 import-review-card import-mapped-review-card"><div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
            <span><i class="bi bi-pencil-square"></i> 数据核对与修正</span>
            <span class="badge status-info">映射后的结果，不是原始 Excel 杂表</span>
        </div><div class="card-body">
        <p class="small text-muted mb-2">按收费对象管理字段顺序展示；左侧“动作、楼栋/区域、单元/分区、房号/铺位号”会固定，横向查看右侧字段时不容易丢失当前户。</p>
        <div class="import-batch-panel {'has-next' if has_next else 'is-final'}">
            <div class="import-batch-head">
                <div><div class="import-batch-kicker">批次进度</div><strong>{h(batch_label)}</strong></div>
                <span>{h(batch_tip)}</span>
            </div>
            <div class="import-batch-stats">
                <div><span>当前批次</span><strong>{batch_no}/{batch_total}</strong></div>
                <div><span>本批次</span><strong>{batch_count}</strong><em>行</em></div>
                <div><span>剩余</span><strong>{batch_remaining}</strong><em>行</em></div>
                <div><span>已预览</span><strong>{batch_percent}%</strong></div>
            </div>
            <div class="import-batch-progress"><i style="width:{batch_percent}%"></i></div>
        </div>
        <form method="POST" action="/import/upload">
            <input type="hidden" name="mode" value="confirm_preview_rows">
            <input type="hidden" name="data_type" value="{h(data_type)}">
            <input type="hidden" name="filename" value="{h(filename)}">
            <input type="hidden" name="upload_token" value="{h(upload_token)}">
            <input type="hidden" name="import_offset" value="{batch_start}">
            <input type="hidden" name="next_import_offset" value="{next_offset}">
            <input type="hidden" name="preview_total_rows" value="{total_changed}">
            <input type="hidden" name="preview_row_count" value="{batch_count}">
            <div class="table-responsive import-sticky-scroll"><table class="table table-sm align-middle import-edit-table">
            <thead>{self._render_review_header(headers, col_map)}</thead><tbody>{review_rows}</tbody></table></div>
            <div class="batch-bar"><button class="btn btn-primary btn-lg"><i class="bi bi-check2-circle"></i> 确认导入并生成结果</button>
            <a href="/import" class="btn btn-outline-secondary">取消</a></div>
        </form></div></div>
        {problem_html}
        {advanced_html}
        ''', 'import'))

    def _source_label(self, headers, col_map, key):
        idx = col_map.get(key)
        return h(headers[idx]) if idx is not None and idx < len(headers) else '未映射'

    def _render_review_header(self, headers, col_map):
        cols = [
            ('action','动作'),('building','楼栋/区域'),('unit','单元/分区'),('room_number','房号/铺位号'),
            ('shop_name','店铺名称'),('tenant_name','租户姓名'),('floor','楼层'),('category','类别'),
            ('business_type','业态'),('area','面积'),('owner_name','业主/商户'),('contract_start','合同开始'),
            ('contract_end','合同结束'),('custom_rate','物业单价'),('payment_cycle','缴费周期'),
            ('owner_phone','电话'),('notes','备注')
        ]
        th = []
        for key,label in cols:
            source = '系统判断' if key in ('action','notes') else f'来自：{self._source_label(headers, col_map, key)}'
            th.append(f'<th>{h(label)}<small>{source}</small></th>')
        return '<tr>' + ''.join(th) + '</tr>'

    def _render_mapped_review_rows(self, changed_rooms, col_map, headers):
        if not changed_rooms:
            return '<tr><td colspan="17" class="text-center text-muted py-4">暂无可导入数据，请检查字段映射或问题行。</td></tr>'
        rows = []
        for i, item in enumerate(changed_rooms):
            def inp(key, value, width=''):
                return f'<input class="form-control form-control-sm {width}" name="row_{i}_{key}" value="{h(value or "")}">'
            rows.append(f'''<tr>
                <td><span class="badge status-{'success' if item.get('action') == '新增' else 'info'}">{h(item.get('action'))}</span><input type="hidden" name="row_{i}_action" value="{h(item.get('action'))}"></td>
                <td>{inp('building', item.get('building'))}</td>
                <td>{inp('unit', item.get('unit'))}</td>
                <td>{inp('room_number', item.get('room_number'))}</td>
                <td>{inp('shop_name', item.get('shop_name'))}</td>
                <td>{inp('tenant_name', item.get('tenant_name'))}</td>
                <td>{inp('floor', item.get('floor'), 'w-80')}</td>
                <td>{inp('category', item.get('category'))}</td>
                <td>{inp('business_type', item.get('business_type'))}</td>
                <td>{inp('area', item.get('area'), 'w-100')}</td>
                <td>{inp('owner_name', item.get('owner_name'))}</td>
                <td>{inp('contract_start', item.get('contract_start'))}</td>
                <td>{inp('contract_end', item.get('contract_end'))}</td>
                <td>{inp('custom_rate', item.get('custom_rate'))}</td>
                <td>{_payment_cycle_select(f'row_{i}_payment_cycle', item.get('payment_cycle'))}</td>
                <td>{inp('owner_phone', item.get('owner_phone'))}</td>
                <td>{inp('notes', item.get('notes'))}</td>
            </tr>''')
        return ''.join(rows)

    def _render_mapping_summary(self, headers, col_map):
        return f'''<div class="mapping-toggle-row mb-3">
            <button class="btn btn-outline-primary btn-lg" type="button" data-bs-toggle="collapse" data-bs-target="#advancedMapping"><i class="bi bi-sliders"></i> 调整字段映射</button>
        </div>'''

    def _render_mapping_form(self, filename, headers, col_map, data_type, upload_token, collapsed=False, import_offset=0):
        labels = self._field_labels()
        rows = ''
        options = ['<option value="">不导入</option>'] + [f'<option value="{idx}">{h(label)}</option>' for idx, label in enumerate(headers)]
        for key in self._manual_mapping_fields():
            selected = col_map.get(key)
            field_options = ''.join(opt.replace(f'value="{selected}"', f'value="{selected}" selected', 1) if selected is not None else opt for opt in options)
            rows += f'''<div class="col-md-4"><label class="form-label">{h(labels.get(key,key))}</label><select name="col_{key}" class="form-select form-select-sm">{field_options}</select></div>'''
        wrap_start = '<div class="collapse" id="advancedMapping">' if collapsed else ''
        wrap_end = '</div>' if collapsed else ''
        return f'''{wrap_start}<div class="card mb-3 import-mapping-card"><div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
        <span><i class="bi bi-sliders"></i> 调整字段映射</span><span class="badge status-warning">重新预览，不写入</span></div><div class="card-body">
        <form method="POST" action="/import/upload" class="row g-3"><input type="hidden" name="mode" value="preview"><input type="hidden" name="data_type" value="{h(data_type)}"><input type="hidden" name="filename" value="{h(filename)}"><input type="hidden" name="upload_token" value="{h(upload_token)}"><input type="hidden" name="import_offset" value="{import_offset}">{rows}
        <div class="col-12"><div class="batch-bar mb-0"><button class="btn btn-primary"><i class="bi bi-arrow-repeat"></i> 重新生成核对表</button><a href="/import" class="btn btn-outline-secondary">取消</a></div></div></form>
        </div></div>{wrap_end}'''

    def _render_problem_summary(self, problem_rows, csv_link):
        if not problem_rows:
            return '<div class="card mb-3 import-review-card"><div class="card-header text-success"><i class="bi bi-check2-circle"></i> 问题提醒</div><div class="card-body text-muted">暂无问题行。</div></div>'
        rows = ''.join(f'<tr><td>{r.get("row_no")}</td><td>{h(r.get("reason"))}</td><td><small>{h(r.get("raw"))}</small></td></tr>' for r in problem_rows[:50])
        return f'''<div class="card mb-3 import-review-card border-warning"><div class="card-header d-flex justify-content-between align-items-center text-warning"><span><i class="bi bi-exclamation-triangle"></i> 问题提醒</span>{csv_link}</div>
        <div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>行号</th><th>原因</th><th>原始数据</th></tr></thead><tbody>{rows}</tbody></table></div></div>'''

    def _render_advanced_import_info(self, filename, headers, data_rows, col_map, data_type, header_idx, result, type_names, total_data_rows=None):
        mapped = ''.join(f'<tr><td>{h(k)}</td><td>{h(headers[v] if v < len(headers) else "")}</td></tr>' for k, v in sorted(col_map.items()))
        width = min(len(headers), 12)
        head = ''.join(f'<th>{h(x)}</th>' for x in headers[:width])
        body = ''.join('<tr>' + ''.join(f'<td>{h(x)}</td>' for x in row) + '</tr>' for row in summarize_rows(data_rows, headers))
        total = len(data_rows) if total_data_rows is None else total_data_rows
        return f'''<details class="card mb-3 import-review-card advanced-import-info"><summary class="card-header"><i class="bi bi-info-circle"></i> 高级识别信息</summary>
        <div class="card-body"><div class="row text-center g-2 mb-3"><div class="col-md-3"><div class="summary-tile"><div class="label">文件类型</div><strong>{h(type_names.get(data_type,data_type))}</strong></div></div><div class="col-md-3"><div class="summary-tile"><div class="label">列头行</div><strong>第 {header_idx+1} 行</strong></div></div><div class="col-md-3"><div class="summary-tile"><div class="label">数据行</div><strong>{total}</strong></div></div><div class="col-md-3"><div class="summary-tile"><div class="label">匹配字段</div><strong>{len(col_map)}</strong></div></div></div>
        <div class="row g-3"><div class="col-md-5"><div class="table-responsive"><table class="table table-sm"><thead><tr><th>系统字段</th><th>表格列</th></tr></thead><tbody>{mapped}</tbody></table></div></div><div class="col-md-7"><div class="table-responsive"><table class="table table-sm"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div></div></div></details>'''

    def _render_basic_info_analysis(self, headers, data_rows):
        analysis = analyze_basic_info(headers, data_rows)
        labels = {'room_number':'房号','owner_name':'业主/用户','owner_phone':'联系电话','tenant_name':'租户','tenant_phone':'租户电话','tenant_id_card':'租户身份证号','shop_name':'店铺名称','business_type':'业态','area':'面积','contract_start':'合同开始日期','contract_end':'合同到期日期','rent_period':'催缴租金租期'}
        rows = ''.join(f'<tr><td>{label}</td><td>{analysis["field_counts"].get(key,0)}</td><td class="small text-muted">{"、".join(h(x) for x in analysis["examples"].get(key, [])) or "-"}</td></tr>' for key,label in labels.items())
        return f'<div class="card mb-3 import-review-card"><div class="card-header"><i class="bi bi-clipboard-data"></i> 基础资料识别分析</div><div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>资料项</th><th>可识别行数</th><th>示例</th></tr></thead><tbody>{rows}</tbody></table></div></div>'

    def _render_import_impact(self, data_type, headers, data_rows, col_map):
        if data_type not in ('rooms', 'payment_ledger'):
            return ''
        db = get_db(); result = preview_basic_info_import(db, headers, data_rows, col_map); db.close()
        return f'<div class="card mb-3 import-impact-card"><div class="card-header"><i class="bi bi-speedometer2"></i> 确认导入前影响预估</div><div class="card-body"><div class="row text-center g-2"><div class="col-md-3"><div class="summary-tile success"><div class="label">将新增房间</div><strong>{result["imported_rooms"]}</strong></div></div><div class="col-md-3"><div class="summary-tile"><div class="label">将更新房间</div><strong>{result["updated_rooms"]}</strong></div></div><div class="col-md-3"><div class="summary-tile"><div class="label">将新增业主</div><strong>{result["imported_owners"]}</strong></div></div><div class="col-md-3"><div class="summary-tile warning"><div class="label">将跳过行</div><strong>{result["skipped"]}</strong></div></div></div></div></div>'

    def _render_import_audit(self, data_type, headers, data_rows, col_map):
        if data_type not in ('rooms', 'payment_ledger'):
            return ''
        db = get_db(); result = preview_basic_info_import(db, headers, data_rows, col_map); db.close()
        return self._render_problem_summary(result.get('problem_rows', []), '')

    def _render_audit_room_rows(self, changed_rooms):
        return ''

    def _render_audit_problem_rows(self, rows, empty_text):
        return ''
