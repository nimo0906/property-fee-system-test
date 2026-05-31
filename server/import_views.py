#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Views and helpers for import preview/result pages."""

import csv, io, urllib.parse

from server.db import h
from server.import_cache import load_import_file, save_import_file


class ImportViewMixin:
    def _simple_import_result(self, imported_rooms=0, updated_rooms=0, imported_owners=0, skipped=0, errors=None):
        return {
            'imported_rooms': imported_rooms,
            'updated_rooms': updated_rooms,
            'imported_owners': imported_owners,
            'skipped': skipped,
            'errors': errors or [],
            'invalid_contracts': [],
            'skip_examples': [],
            'changed_rooms': [],
            'problem_rows': [],
        }

    def _render_import_result(self, filename, data_type, total_rows, backup_name, result):
        type_names = {
            'owners': '业主信息',
            'rooms': '房间基础资料',
            'bills': '账单记录',
            'payment_ledger': '收款明细表基础资料',
        }
        skip_examples = ''.join(f'<li>{h(x)}</li>' for x in result.get('skip_examples', [])[:20])
        invalid_contracts = ''.join(f'<li>{h(x)}</li>' for x in result.get('invalid_contracts', [])[:20])
        errors = ''.join(f'<li>{h(x)}</li>' for x in result.get('errors', [])[:20])
        changed_rows = self._render_changed_rooms(result.get('changed_rooms', []))
        problem_rows = result.get('problem_rows', [])
        problem_csv_token = self._save_problem_rows_csv(problem_rows)
        problem_rows_html = self._render_problem_rows(problem_rows, problem_csv_token)
        billing_next_html = self._render_import_billing_next(result.get('changed_rooms', []))
        amount_note = '本次只处理基础资料；历史收款流水和金额不会自动入账，需要用户后续核对确认。'
        if data_type == 'bills':
            amount_note = '账单字段已按本次确认导入；收款流水和历史实收金额仍需用户后续核对确认。'
        self._html(self._page('导入结果', f'''
        <div class="import-hero import-hero-pro">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
                <div>
                    <div class="page-kicker">IMPORT RESULT</div>
                    <h4 class="mb-2">导入结果复核</h4>
                    <p class="mb-0 text-muted">处理完成。系统已在写入前创建自动备份，历史金额不会自动入账。</p>
                </div>
                <span class="badge status-success fs-6 px-3 py-2">已创建备份</span>
            </div>
        </div>
        <div class="alert alert-warning">
            <strong>未导入历史金额。</strong>{h(amount_note)}
        </div>
        <div class="card import-file-card mb-3"><div class="card-body">
            <div class="row g-3 align-items-center">
                <div class="col-md-4"><span class="text-muted small">文件</span><div class="fw-bold">{h(filename)}</div></div>
                <div class="col-md-3"><span class="text-muted small">类型</span><div class="fw-bold">{h(type_names.get(data_type, data_type))}</div></div>
                <div class="col-md-2"><span class="text-muted small">数据行</span><div class="fw-bold">{total_rows} 行</div></div>
                <div class="col-md-3"><span class="text-muted small">自动备份</span><div><code>{h(backup_name)}</code></div></div>
            </div>
        </div></div>
        <div class="row text-center g-2 mb-3">
        <div class="col-md-3"><div class="summary-tile success"><div class="label">新增房间</div><strong>{result.get('imported_rooms', 0)}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile"><div class="label">更新房间</div><strong>{result.get('updated_rooms', 0)}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile"><div class="label">新增业主</div><strong>{result.get('imported_owners', 0)}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile warning"><div class="label">跳过行数</div><strong>{result.get('skipped', 0)}</strong></div></div>
        </div>
        <div class="card mb-3 import-review-card"><div class="card-header"><i class="bi bi-exclamation-diamond"></i> 异常和跳过明细</div>
        <div class="card-body">
        <h6>跳过示例</h6><ul>{skip_examples or '<li class="text-muted">无</li>'}</ul>
        <h6>合同日期异常</h6><ul>{invalid_contracts or '<li class="text-muted">无</li>'}</ul>
        <h6>处理错误</h6><ul>{errors or '<li class="text-muted">无</li>'}</ul>
        </div></div>
        <div class="card mb-3 import-review-card"><div class="card-header"><i class="bi bi-pencil-square"></i> 数据核对与修正</div>
        <div class="card-body">
        <p class="small text-muted">请重点核对楼栋、房号、面积、业主、电话、合同日期。发现错误可直接点击“编辑”修正。</p>
        <div class="table-responsive"><table class="table table-sm align-middle">
        <thead><tr><th>动作</th><th>楼栋</th><th>房号</th><th>楼层</th><th>面积</th><th>业主/租户</th><th>电话</th><th>合同日期</th><th>备注</th><th>修正</th></tr></thead>
        <tbody>{changed_rows}</tbody></table></div>
        </div></div>
        {problem_rows_html}
        {billing_next_html}
        <div class="batch-bar">
            <a href="/import" class="btn btn-primary">继续导入</a>
            <a href="/backups" class="btn btn-outline-secondary">查看备份</a>
            <a href="/rooms" class="btn btn-outline-secondary">查看房间</a>
            <form method="POST" action="/backups/{h(backup_name)}/restore" class="d-inline"
                  onsubmit="return confirm('撤销本次导入会把数据库恢复到导入前状态，当前导入后的改动都会被覆盖。确定撤销？')">
                <button class="btn btn-outline-danger">撤销本次导入</button>
            </form>
        </div>
        ''', 'import'))

    def _render_problem_rows(self, problem_rows, csv_token):
        if not problem_rows:
            return '''
            <div class="card mb-3"><div class="card-header">问题行明细</div>
            <div class="card-body text-muted">本次没有问题行。</div></div>'''
        rows = ''.join(
            f'<tr><td>{r["row_no"]}</td><td>{h(r["reason"])}</td><td><small>{h(r["raw"])}</small></td></tr>'
            for r in problem_rows[:100]
        )
        more = ''
        if len(problem_rows) > 100:
            more = '<p class="small text-muted">仅显示前 100 条，完整内容请下载 CSV。</p>'
        return f'''
        <div class="card mb-3 import-review-card"><div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
        <span><i class="bi bi-file-earmark-spreadsheet"></i> 问题行明细</span>
        <a class="btn btn-sm btn-outline-primary" href="/import/problem_rows/{h(csv_token)}.csv"><i class="bi bi-download"></i> 下载问题行 CSV</a>
        </div>
        <div class="card-body">
        <p class="small text-muted">这些行未导入或需要人工核对。可下载 CSV，修正后单独重新导入。</p>
        {more}
        <div class="table-responsive"><table class="table table-sm">
        <thead><tr><th>行号</th><th>原因</th><th>原始数据</th></tr></thead>
        <tbody>{rows}</tbody></table></div>
        </div></div>'''

    def _save_problem_rows_csv(self, problem_rows):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['行号', '原因', '原始数据'])
        for row in problem_rows:
            writer.writerow([row.get('row_no', ''), row.get('reason', ''), row.get('raw', '')])
        return save_import_file(buf.getvalue().encode('utf-8-sig'))

    def _import_problem_rows_download(self, token):
        try:
            data = load_import_file(token)
        except FileNotFoundError:
            return self._error(404)
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="problem_rows.csv"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _render_changed_rooms(self, changed_rooms):
        if not changed_rooms:
            return '<tr><td colspan="10" class="text-center text-muted py-3">本次没有新增或更新房间</td></tr>'
        rows = []
        for item in changed_rooms[:100]:
            room_id = item.get('room_id')
            edit = f'<a class="btn btn-sm btn-outline-primary" href="/rooms/{room_id}/edit">编辑</a>' if room_id else '-'
            contract = ''
            if item.get('contract_start') or item.get('contract_end'):
                contract = f'{h(item.get("contract_start") or "")} ~ {h(item.get("contract_end") or "")}'
            rows.append(f'''<tr>
                <td><span class="badge status-{'success' if item.get('action') == '新增' else 'info'}">{h(item.get('action'))}</span></td>
                <td>{h(item.get('building'))}</td>
                <td><strong>{h(item.get('room_number'))}</strong></td>
                <td>{h(item.get('floor'))}</td>
                <td>{h(item.get('area'))}</td>
                <td>{h(item.get('owner_name'))}</td>
                <td>{h(item.get('owner_phone'))}</td>
                <td><small>{contract or '-'}</small></td>
                <td><small>{h(item.get('notes'))}</small></td>
                <td>{edit}</td>
            </tr>''')
        if len(changed_rooms) > 100:
            rows.append('<tr><td colspan="10" class="text-muted text-center">仅显示前 100 条，请到房间管理继续核对</td></tr>')
        return ''.join(rows)

    def _render_import_billing_next(self, changed_rooms):
        valid = [r for r in changed_rooms if r.get('building') and r.get('category')]
        if not valid:
            return ''
        buildings = sorted({r.get('building') for r in valid})
        categories = sorted({r.get('category') for r in valid})
        params = {}
        if len(buildings) == 1:
            params['building'] = buildings[0]
        if len(categories) == 1:
            params['category'] = categories[0]
        href = '/bills/generate'
        if params:
            href += '?' + urllib.parse.urlencode(params)
        building_scope = '、'.join(buildings[:5]) if len(buildings) <= 5 else f'{len(buildings)} 个楼栋'
        category_scope = '、'.join(categories[:5]) if len(categories) <= 5 else f'{len(categories)} 个类别'
        scope = f'楼栋：{building_scope}；类别：{category_scope}'
        return f'''
        <div class="card mb-3 import-next-card"><div class="card-header text-primary"><i class="bi bi-signpost-2"></i> 下一步生成账单</div>
        <div class="card-body">
        <p class="small text-muted mb-2">基础资料核对无误后，可直接进入账单生成页。系统会带上本次导入范围；进入后仍需先预览，再确认生成。</p>
        <p class="small mb-3">本次范围：{h(scope)}</p>
        <a class="btn btn-primary" href="{h(href)}"><i class="bi bi-receipt"></i> 按导入范围生成账单预览</a>
        <a class="btn btn-outline-secondary" href="/rooms">先查看房间</a>
        </div></div>'''
