#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Views for confirming payment-ledger fee mappings."""

import csv, io

from server.db import get_db, h
from server.import_cache import load_import_file, save_import_file
from server.payment_ledger import analyze_payment_ledger


class ImportFeeMappingMixin:
    def _render_fee_mapping_form(self, filename, upload_token, fee_stats):
        if not fee_stats:
            return ''
        fee_types = self._active_fee_type_names()
        rows = ''
        for stat in fee_stats:
            name = stat['name']
            options = [
                ('reference', '仅作为参考，不导入金额'),
                ('ignore', '忽略此列'),
            ] + [(f'fee:{fee}', fee) for fee in fee_types]
            suggested = self._suggest_fee_type(name, fee_types)
            option_html = ''
            for value, label in options:
                selected = ' selected' if value == f'fee:{suggested}' else ''
                option_html += f'<option value="{h(value)}"{selected}>{h(label)}</option>'
            rows += f'''<tr>
                <td>{h(name)}</td><td>{h(stat["action"])}</td>
                <td>{stat["positive"]}</td><td>{stat["negative"]}</td><td>{h(stat["total"])}</td>
                <td><select name="fee_map_{h(name)}" class="form-select form-select-sm">{option_html}</select></td>
                <td><small>{h(stat["note"])}</small></td>
            </tr>'''
        return f'''
        <div class="card mb-3 import-mapping-card"><div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
        <span><i class="bi bi-link-45deg"></i> 收费标准匹配确认</span>
        <span class="badge status-info">只核对，不入账</span>
        </div>
        <div class="card-body">
        <p class="small text-muted">这里只确认 Excel 收费列与系统收费标准的对应关系，不导入历史金额。</p>
        <form method="POST" action="/import/upload">
            <input type="hidden" name="mode" value="confirm_fee_mapping">
            <input type="hidden" name="data_type" value="payment_ledger">
            <input type="hidden" name="filename" value="{h(filename)}">
            <input type="hidden" name="upload_token" value="{h(upload_token)}">
            <div class="table-responsive"><table class="table table-sm align-middle">
            <thead><tr><th>Excel列</th><th>识别</th><th>正数行</th><th>负数行</th><th>金额合计</th><th>匹配到系统收费标准</th><th>说明</th></tr></thead>
            <tbody>{rows}</tbody></table></div>
            <div class="batch-bar mb-0">
                <button class="btn btn-outline-primary"><i class="bi bi-check2-circle"></i> 确认收费项目匹配</button>
                <a href="/import" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> 返回导入页</a>
            </div>
        </form>
        </div></div>'''

    def _render_fee_mapping_result(self, filename, headers, data_rows, form):
        db = get_db()
        rooms = [dict(r) for r in db.execute("SELECT building, room_number, category, area FROM rooms").fetchall()]
        db.close()
        analysis = analyze_payment_ledger(headers, data_rows, rooms)
        rows = ''
        records = []
        for stat in analysis['fee_stats']:
            name = stat['name']
            choice = form.getvalue(f'fee_map_{name}', 'reference')
            label = self._fee_mapping_label(choice)
            records.append({
                'name': name, 'action': stat['action'], 'label': label,
                'positive': stat['positive'], 'negative': stat['negative'],
                'total': stat['total'], 'note': stat['note'],
            })
            rows += f'''<tr>
                <td>{h(name)}</td><td>{h(label)}</td><td>{stat["positive"]}</td>
                <td>{stat["negative"]}</td><td>{h(stat["total"])}</td><td><small>{h(stat["note"])}</small></td>
            </tr>'''
        csv_token = self._save_fee_mapping_csv(records)
        self._html(self._page('收费项目匹配确认结果', f'''
        <div class="import-hero import-hero-pro">
            <div>
                <div class="page-kicker">FEE MAPPING</div>
                <h4 class="mb-2">收费项目匹配确认结果</h4>
                <p class="mb-0 text-muted">匹配结果已记录在本页供核对；当前版本不写入历史金额。</p>
            </div>
        </div>
        <div class="alert alert-warning"><strong>未导入历史金额。</strong>金额只作为识别和核对依据，后续生成账单仍需用户确认。</div>
        <div class="metric-grid import-summary-grid">
            <div class="metric-card primary"><div class="metric-label">识别收费列</div><div class="metric-value fs-5">{len(analysis['fee_stats'])}</div></div>
            <div class="metric-card warning"><div class="metric-label">金额入账状态</div><div class="metric-value fs-5">未导入</div></div>
            <div class="metric-card"><div class="metric-label">核对文件</div><div class="metric-value fs-6">{h(filename)}</div></div>
            <div class="metric-card success"><div class="metric-label">可导出清单</div><div class="metric-value fs-5">CSV</div></div>
        </div>
        <div class="batch-bar">
            <a class="btn btn-outline-primary" href="/import/fee_mapping/{h(csv_token)}.csv"><i class="bi bi-download"></i> 下载 CSV 核对清单</a>
            <button class="btn btn-outline-secondary" onclick="window.print()"><i class="bi bi-printer"></i> 打印核对清单</button>
            <a href="/import" class="btn btn-primary"><i class="bi bi-arrow-left"></i> 返回导入页</a>
        </div>
        <div class="table-responsive"><table class="table table-sm align-middle">
        <thead><tr><th>Excel列</th><th>确认匹配</th><th>正数行</th><th>负数行</th><th>金额合计</th><th>说明</th></tr></thead>
        <tbody>{rows}</tbody></table></div>
        ''', 'import'))

    def _active_fee_type_names(self):
        db = get_db()
        rows = db.execute("SELECT name FROM fee_types WHERE is_active=1 ORDER BY sort_order,id").fetchall()
        db.close()
        return [r['name'] for r in rows]

    def _suggest_fee_type(self, ledger_name, fee_types):
        for fee in fee_types:
            if ledger_name in fee or fee in ledger_name:
                return fee
        return ''

    def _fee_mapping_label(self, choice):
        if choice == 'ignore':
            return '忽略'
        if choice == 'reference':
            return '仅作为参考，不导入金额'
        if choice.startswith('fee:'):
            return choice[4:]
        return '仅作为参考，不导入金额'

    def _save_fee_mapping_csv(self, records):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['Excel原始列名', '系统识别结果', '用户确认匹配', '正数行数', '负数行数', '金额合计', '说明', '金额入账状态'])
        for item in records:
            writer.writerow([
                item['name'], item['action'], item['label'], item['positive'],
                item['negative'], item['total'], item['note'], '未导入历史金额',
            ])
        return save_import_file(buf.getvalue().encode('utf-8-sig'))

    def _fee_mapping_csv_download(self, token):
        try:
            data = load_import_file(token)
        except FileNotFoundError:
            return self._error(404)
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="fee_mapping_review.csv"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
