#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Views and helpers for import preview pages."""

from server.db import get_db, h
from server.import_parser import summarize_rows
from server.basic_import import preview_basic_info_import
from server.import_cache import save_import_file
from server.payment_ledger import analyze_basic_info, analyze_payment_ledger


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
            'owner_name', 'owner_phone', 'tenant_name', 'shop_name',
            'business_type', 'contract_start', 'contract_end', 'rent_period',
        ]

    def _render_import_preview(self, filename, headers, data_rows, col_map, data_type, header_idx, upload_token):
        type_names = {
            "owners": "业主信息",
            "rooms": "房间信息",
            "bills": "账单记录",
            "payment_ledger": "收款明细表",
            "unknown": "未知类型",
        }
        mapped = ''.join(
            f'<tr><td>{h(k)}</td><td>{h(headers[v] if v < len(headers) else "")}</td></tr>'
            for k, v in sorted(col_map.items())
        )
        width = min(len(headers), 12)
        head = ''.join(f'<th>{h(x)}</th>' for x in headers[:width])
        body = ''.join(
            '<tr>' + ''.join(f'<td>{h(x)}</td>' for x in row) + '</tr>'
            for row in summarize_rows(data_rows, headers)
        )
        warning = ''
        analysis_html = self._render_import_impact(data_type, headers, data_rows, col_map)
        analysis_html += self._render_basic_info_analysis(headers, data_rows)
        audit_html = self._render_import_audit(data_type, headers, data_rows, col_map)
        mapping_form = self._render_mapping_form(filename, headers, col_map, data_type, upload_token)
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
            analysis_html += f'''
            <div class="card mb-3 import-review-card"><div class="card-header"><i class="bi bi-receipt-cutoff"></i> 收费项目识别分析</div>
            <div class="card-body">
            <div class="row text-center g-2 mb-3">
            <div class="col-md-3"><div class="summary-tile success"><div class="label">房间匹配</div><strong>{analysis['matched_rooms']}</strong></div></div>
            <div class="col-md-3"><div class="summary-tile warning"><div class="label">未匹配</div><strong>{analysis['unmatched_rooms']}</strong></div></div>
            <div class="col-md-3"><div class="summary-tile"><div class="label">有业主名</div><strong>{analysis['rows_with_owner']}</strong></div></div>
            <div class="col-md-3"><div class="summary-tile"><div class="label">有单位名</div><strong>{analysis['rows_with_company']}</strong></div></div>
            </div>
            <p class="small text-muted">房间类型：{room_types}</p>
            <p class="small text-muted">未匹配示例：{examples}</p>
            <div class="table-responsive"><table class="table table-sm">
            <thead><tr><th>收费项目列</th><th>识别结果</th><th>正数行</th><th>负数行</th><th>金额合计</th><th>说明</th></tr></thead>
            <tbody>{stats_rows}</tbody></table></div>
            </div></div>{fee_mapping_form}'''
            warning = '''<div class="alert alert-warning"><strong>已识别为收款明细表。</strong>
            历史金额只用于识别收费项目列，不会自动入账。金额必须由用户后续确认。</div>'''
        elif data_type == 'unknown':
            warning = '<div class="alert alert-warning">未能可靠判断数据类型，请检查列头或手动选择导入类型。</div>'
        self._html(self._page('导入预览', f'''
        <div class="import-hero import-hero-pro">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
                <div>
                    <div class="page-kicker">IMPORT PREVIEW</div>
                    <h4 class="mb-2">导入预览核对</h4>
                    <p class="mb-0 text-muted">先确认文件类型、字段映射和影响预估，再执行写入。历史金额不会自动入账。</p>
                </div>
                <a href="/import" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> 返回导入页</a>
            </div>
        </div>
        {warning}
        <div class="metric-grid import-summary-grid">
            <div class="metric-card primary"><div class="metric-label">文件类型</div><div class="metric-value fs-5">{h(type_names.get(data_type, data_type))}</div></div>
            <div class="metric-card"><div class="metric-label">列头行</div><div class="metric-value fs-5">第 {header_idx + 1} 行</div></div>
            <div class="metric-card success"><div class="metric-label">数据行</div><div class="metric-value fs-5">{len(data_rows)}</div></div>
            <div class="metric-card warning"><div class="metric-label">已匹配字段</div><div class="metric-value fs-5">{len(col_map)}</div></div>
        </div>
        <div class="card import-file-card mb-3"><div class="card-body d-flex flex-wrap justify-content-between gap-2">
            <div><span class="text-muted small">当前文件</span><div class="fw-bold">{h(filename)}</div></div>
            <div class="text-muted small align-self-center">确认导入时会自动备份数据库。</div>
        </div></div>
        {audit_html}
        {analysis_html}
        {mapping_form}
        <div class="row g-3">
        <div class="col-md-5"><div class="card import-review-card"><div class="card-header"><i class="bi bi-diagram-3"></i> 字段匹配</div>
        <div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>系统字段</th><th>表格列</th></tr></thead><tbody>{mapped}</tbody></table></div></div></div>
        <div class="col-md-7"><div class="card import-review-card"><div class="card-header"><i class="bi bi-table"></i> 前几行数据</div>
        <div class="table-responsive"><table class="table table-sm mb-0"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div></div>
        </div>
        ''', 'import'))

    def _render_mapping_form(self, filename, headers, col_map, data_type, upload_token):
        labels = {
            'building': '楼栋', 'unit': '单元/座', 'room_number': '房号',
            'floor': '楼层', 'category': '类别', 'area': '面积',
            'owner_name': '业主/用户', 'owner_phone': '联系电话',
            'tenant_name': '租户', 'shop_name': '店铺名称',
            'business_type': '业态', 'contract_start': '合同开始日期',
            'contract_end': '合同到期日期', 'rent_period': '催缴租金租期',
        }
        rows = ''
        options = ['<option value="">不导入</option>'] + [
            f'<option value="{idx}">{{label}}</option>'.replace('{label}', h(label))
            for idx, label in enumerate(headers)
        ]
        for key in self._manual_mapping_fields():
            selected = col_map.get(key)
            field_options = ''.join(
                opt.replace(f'value="{selected}"', f'value="{selected}" selected', 1)
                if selected is not None else opt
                for opt in options
            )
            rows += f'''<div class="col-md-4">
                <label class="form-label">{h(labels[key])}</label>
                <select name="col_{key}" class="form-select form-select-sm">{field_options}</select>
            </div>'''
        return f'''
        <div class="card mb-3 import-mapping-card"><div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
        <span><i class="bi bi-sliders"></i> 字段映射确认</span>
        <span class="badge status-warning">确认后再写入</span>
        </div>
        <div class="card-body">
        <p class="small text-muted">如果系统识别错列，请在这里手动调整。确认后会按当前映射导入，并自动备份。</p>
        <form method="POST" action="/import/upload" class="row g-3">
            <input type="hidden" name="mode" value="import">
            <input type="hidden" name="data_type" value="{h(data_type)}">
            <input type="hidden" name="filename" value="{h(filename)}">
            <input type="hidden" name="upload_token" value="{h(upload_token)}">
            {rows}
            <div class="col-12">
                <div class="batch-bar mb-0">
                    <button class="btn btn-primary"><i class="bi bi-cloud-upload"></i> 使用此映射确认导入</button>
                    <a href="/import" class="btn btn-outline-secondary"><i class="bi bi-x-circle"></i> 取消</a>
                </div>
            </div>
        </form>
        </div></div>'''

    def _render_basic_info_analysis(self, headers, data_rows):
        analysis = analyze_basic_info(headers, data_rows)
        labels = {
            'room_number': '房号',
            'owner_name': '业主/用户',
            'owner_phone': '联系电话',
            'tenant_name': '租户',
            'shop_name': '店铺名称',
            'business_type': '业态',
            'area': '面积',
            'contract_start': '合同开始日期',
            'contract_end': '合同到期日期', 'rent_period': '催缴租金租期',
        }
        rows = ''
        for key, label in labels.items():
            examples = '、'.join(h(x) for x in analysis['examples'].get(key, [])) or '-'
            rows += f'<tr><td>{label}</td><td>{analysis["field_counts"].get(key, 0)}</td><td class="small text-muted">{examples}</td></tr>'
        return f'''
        <div class="card mb-3 import-review-card"><div class="card-header"><i class="bi bi-clipboard-data"></i> 基础资料识别分析</div>
        <div class="table-responsive"><table class="table table-sm mb-0">
        <thead><tr><th>资料项</th><th>可识别行数</th><th>示例</th></tr></thead>
        <tbody>{rows}</tbody></table></div></div>'''

    def _render_import_impact(self, data_type, headers, data_rows, col_map):
        if data_type not in ('rooms', 'payment_ledger'):
            return ''
        db = get_db()
        result = preview_basic_info_import(db, headers, data_rows, col_map)
        db.close()
        errors = '；'.join(h(x) for x in result['errors'][:5]) or '-'
        skips = '；'.join(h(x) for x in result['skip_examples']) or '-'
        invalid_contracts = '；'.join(h(x) for x in result['invalid_contracts']) or '-'
        return f'''
        <div class="card mb-3 import-impact-card"><div class="card-header"><i class="bi bi-speedometer2"></i> 确认导入前影响预估</div>
        <div class="card-body">
        <div class="row text-center g-2 mb-3">
        <div class="col-md-3"><div class="summary-tile success"><div class="label">将新增房间</div><strong>{result['imported_rooms']}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile"><div class="label">将更新房间</div><strong>{result['updated_rooms']}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile"><div class="label">将新增业主</div><strong>{result['imported_owners']}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile warning"><div class="label">将跳过行</div><strong>{result['skipped']}</strong></div></div>
        </div>
        <p class="small text-muted mb-1"><strong>跳过示例：</strong>{skips}</p>
        <p class="small text-muted mb-1"><strong>合同日期异常：</strong>{invalid_contracts}</p>
        <p class="small text-muted mb-0"><strong>处理错误：</strong>{errors}</p>
        </div></div>'''

    def _render_import_audit(self, data_type, headers, data_rows, col_map):
        if data_type not in ('rooms', 'payment_ledger'):
            return ''
        db = get_db()
        result = preview_basic_info_import(db, headers, data_rows, col_map)
        db.close()
        changed_rooms = result.get('changed_rooms', [])
        problem_rows = result.get('problem_rows', [])
        skip_rows = [r for r in problem_rows if '合同日期异常' not in r.get('reason', '')]
        risk_rows = [r for r in problem_rows if '合同日期异常' in r.get('reason', '')]
        csv_link = ''
        if problem_rows:
            csv_token = self._save_problem_rows_csv(problem_rows)
            csv_link = f'<a class="btn btn-sm btn-outline-primary" href="/import/problem_rows/{h(csv_token)}.csv"><i class="bi bi-download"></i> 下载问题行 CSV</a>'
        return f'''
        <div class="card mb-3 import-audit-card">
            <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-2">
                <span><i class="bi bi-shield-check"></i> 导入审核台</span>
                {csv_link}
            </div>
            <div class="card-body">
                <div class="import-audit-grid">
                    <section class="import-audit-section success">
                        <div class="import-audit-title"><span>可导入房间</span><strong>{len(changed_rooms)}</strong></div>
                        {self._render_audit_room_rows(changed_rooms)}
                    </section>
                    <section class="import-audit-section warning">
                        <div class="import-audit-title"><span>跳过行</span><strong>{len(skip_rows)}</strong></div>
                        {self._render_audit_problem_rows(skip_rows, '暂无跳过行')}
                    </section>
                    <section class="import-audit-section danger">
                        <div class="import-audit-title"><span>风险行</span><strong>{len(risk_rows)}</strong></div>
                        {self._render_audit_problem_rows(risk_rows, '暂无风险行')}
                    </section>
                </div>
            </div>
        </div>'''

    def _render_audit_room_rows(self, changed_rooms):
        if not changed_rooms:
            return '<div class="import-audit-empty">暂无可导入房间</div>'
        rows = []
        for item in changed_rooms[:8]:
            contract = '-'
            if item.get('contract_start') or item.get('contract_end'):
                contract = f'{h(item.get("contract_start") or "")} ~ {h(item.get("contract_end") or "")}'
            rows.append(f'''
            <div class="import-audit-row">
                <div><strong>{h(item.get('building'))}-{h(item.get('room_number'))}</strong><small>{h(item.get('owner_name') or '未识别业主')}</small></div>
                <div class="text-end"><span>{h(item.get('area'))}㎡</span><small>{contract}</small></div>
            </div>''')
        if len(changed_rooms) > 8:
            rows.append(f'<div class="import-audit-more">另有 {len(changed_rooms) - 8} 行，可在确认导入后到房间管理核对。</div>')
        return ''.join(rows)

    def _render_audit_problem_rows(self, rows, empty_text):
        if not rows:
            return f'<div class="import-audit-empty">{h(empty_text)}</div>'
        html = []
        for row in rows[:8]:
            html.append(f'''
            <div class="import-audit-row problem">
                <div><strong>第 {row.get('row_no')} 行</strong><small>{h(row.get('reason'))}</small></div>
                <div><small>{h(row.get('raw'))}</small></div>
            </div>''')
        if len(rows) > 8:
            html.append(f'<div class="import-audit-more">另有 {len(rows) - 8} 行，请下载 CSV 核对。</div>')
        return ''.join(html)
