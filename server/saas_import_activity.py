#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import activity rendering helpers for SaaS backoffice."""

from pathlib import PurePosixPath

from server.saas_user_pages import _h


def display_filename(value):
    return PurePosixPath(str(value or '').replace('\\', '/')).name


def render_import_activity(files=None, logs=None):
    return _render_files(files or []) + _render_logs(logs or [])


def _render_files(files):
    rows = ''.join(_file_row(row) for row in files[-5:]) or '<tr><td colspan="5">暂无上传文件</td></tr>'
    return f'''<section class="card" style="margin-top:18px"><div class="card-h">最近上传文件</div><div class="card-b"><table><thead><tr><th>文件名</th><th>状态</th><th>大小</th><th>存储位置</th><th>类型</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''


def _file_row(row):
    return f'''<tr><td>{_h(display_filename(row.get('original_name')))}</td><td>{_h(row.get('status'))}</td><td>{_h(row.get('file_size'))}</td><td>{_h(row.get('storage_key'))}</td><td>{_h(row.get('import_type'))}</td></tr>'''


def _render_logs(logs):
    import_logs = [row for row in logs if str(row.get('action', '')).startswith('import.')]
    rows = ''.join(_log_row(row) for row in import_logs[-5:]) or '<tr><td colspan="3">暂无导入审计</td></tr>'
    return f'''<section class="card" style="margin-top:18px"><div class="card-h">最近导入审计</div><div class="card-b"><table><thead><tr><th>动作</th><th>结果</th><th>入口</th></tr></thead><tbody>{rows}</tbody></table><div class="hint"><a class="ghost-link" href="/backoffice/audit-logs">查看完整审计日志</a></div></div></section>'''


def _log_row(row):
    detail = row.get('detail') or {}
    result = ''
    if row.get('action') == 'import.confirm':
        result = f"写入 {detail.get('created_count', 0)} 行，跳过 {detail.get('skipped_count', 0)} 行"
    elif row.get('action') == 'import.preview':
        result = f"有效 {detail.get('valid_count', 0)} 行，错误 {detail.get('error_count', 0)} 行"
    else:
        result = _h(detail)
    return f'''<tr><td>{_h(row.get('action'))}</td><td>{_h(result)}</td><td><a class="ghost-link" href="/backoffice/audit-logs">审计日志</a></td></tr>'''
