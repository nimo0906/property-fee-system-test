#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import confirmation result rendering for SaaS backoffice."""

from server.saas_user_pages import _h, _page


def render_confirm_result(user, import_id, result, already_confirmed=False, review=None):
    note = '<p class="sub">该批次已确认过，本次不会重复写入。</p>' if already_confirmed else '<p class="sub">只写入有效行；错误行未污染正式数据。</p>'
    owner_created = str(result.get("owner_created_count", 0))
    valid_count = (review or {}).get('valid_count', result.get('created_count', 0))
    error_count = (review or {}).get('error_count', 0)
    duplicate_count = result.get('duplicate_skipped_count', 0)
    total_skipped = result.get('skipped_count', 0)
    error_link = f'<a class="ghost-link" href="/api/imports/{_h(import_id)}/errors.csv">下载错误行 CSV</a>' if int(error_count or 0) else ''
    body = (f'<section class="hero"><div><h1>导入结果</h1>'
            f'<div class="sub">导入批次摘要：确认导入后请核对成功、错误、重复和跳过数量，再进入收费对象列表检查。</div></div>'
            f'<div class="badge tenant-scope">{_h(user.get("tenant_name"))} · {_h(user.get("project_name"))}</div></section>'
            f'<section class="card"><div class="card-h">导入批次摘要</div><div class="card-b">'
            f'<p><strong>批次 ID：{_h(import_id)}</strong></p>'
            f'<p>预览有效：{_h(valid_count)}</p>'
            f'<p>预览错误：{_h(error_count)}</p>'
            f'<p>成功导入：{str(result.get("created_count", 0))}</p>'
            f'<p>自动创建业主：{owner_created}</p>'
            f'<p>错误跳过：{_h(error_count)}</p>'
            f'<p>重复跳过：{_h(duplicate_count)}</p>'
            f'<p>总跳过：{_h(total_skipped)}</p>'
            f'<p>跳过错误：{_h(total_skipped)}</p>{note}'
            f'<div class="actions"><a class="ghost-link" href="/backoffice/charge-targets">查看收费对象</a>'
            f'<a class="ghost-link" href="/backoffice/imports">继续导入</a>{error_link}</div></div></section>')
    return _page('导入结果', body)
