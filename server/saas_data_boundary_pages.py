#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data boundary checklist page for SaaS backoffice."""

from datetime import datetime

from server.saas_isolation_self_check import run_isolation_self_check
from server.saas_user_pages import _h, _page


_BOUNDARY_ROWS = [
    ('公司数据隔离', '收费对象、账单、收款、导入文件、审计日志', '每张业务表必须带 tenant_id；项目级业务数据必须带 project_id', 'A 公司不能读取 B 公司数据；平台租户不承载客户业务数据'),
    ('客户上传数据隔离', 'Excel 导入文件、附件、客户原始业务材料', 'tenants/{tenant_id}/projects/{project_id}', '客户上传文件不能写入系统目录；预览不写库，确认导入才写业务表'),
    ('系统自身数据隔离', '系统模板、默认角色、部署配置、运行资产', 'system/', '系统配置不能写入客户上传目录；页面不展示生产密钥或真实路径'),
    ('备份恢复边界', '数据库备份、客户文件备份、系统文件备份、恢复演练', '备份按 database、tenant-files、system-files 分区校验', '恢复演练必须显式选择范围，避免把客户文件和系统文件混合恢复'),
]


def _rows():
    return ''.join(
        '<tr>'
        f'<td><strong>{_h(name)}</strong></td><td>{_h(scope)}</td>'
        f'<td>{_h(storage)}</td><td>{_h(rule)}</td>'
        '</tr>'
        for name, scope, storage, rule in _BOUNDARY_ROWS
    )


def _render(user):
    body = f'''
<section class="hero"><div><h1>数据边界检查</h1><div class="sub">正式商业云端版用于演示和自查多公司隔离：公司业务数据、客户上传数据、系统自身数据、备份恢复数据必须分层保存，不能混在一起。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">边界清单</div><div class="card-b"><table><thead><tr><th>边界</th><th>覆盖对象</th><th>隔离键 / 存储前缀</th><th>检查规则</th></tr></thead><tbody>{_rows()}</tbody></table></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">租户隔离自动自检</div><div class="card-b"><p class="sub">一键检查当前租户是否能越权读取其他租户数据，覆盖收费对象、账单、收款、导入文件、审计日志。</p><div class="actions"><form method="post" action="/backoffice/data-boundaries/self-check"><button class="primary">查看页面化结果</button></form><form method="post" action="/api/isolation/self-check"><button class="ghost">获取 JSON 结果</button></form></div><div class="hint">页面和接口都只返回 PASS/FAIL 摘要，不展示客户业务明细、真实路径、数据库密码或应用密钥。</div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">上线验收口径</div><div class="card-b"><p class="sub">收费对象、账单、收款、导入文件、审计日志只能按当前租户和项目查询。</p><p class="sub">数据库备份和恢复演练记录只展示状态、范围和校验结果，不展示真实服务器目录、数据库密码或应用密钥。</p><p class="sub">平台管理员用于客户开通、跨租户账号处理和上线运维；平台租户不承载客户业务数据。</p><p><a class="ghost-link" href="/backoffice">返回后台首页</a></p></div></section>'''
    return _page('数据边界检查', body)


def _result_rows(result):
    rows = []
    for item in result.get('checks', []):
        status = 'PASS' if item.get('status') == 'pass' else 'FAIL'
        cls = 'on' if status == 'PASS' else 'off'
        rows.append(
            '<tr>'
            f'<td>{_h(item.get("name"))}</td><td><span class="status {cls}">{status}</span></td>'
            f'<td>{_h(item.get("message"))}</td>'
            '</tr>'
        )
    return ''.join(rows)


def _render_self_check_result(user, result, checked_at):
    overall = 'PASS' if result.get('status') == 'pass' else 'FAIL'
    cls = 'on' if overall == 'PASS' else 'off'
    body = f'''
<section class="hero"><div><h1>租户隔离自检结果</h1><div class="sub">当前租户项目范围：{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></div><div class="badge tenant-scope">检查时间 {_h(checked_at)}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><strong>总体结果：</strong><span class="status {cls}">{overall}</span><span class="hint"> · checked_scope={_h(result.get('checked_scope'))}</span></div></section>
<section class="card"><div class="card-h">检查项</div><div class="card-b"><table><thead><tr><th>对象</th><th>结果</th><th>说明</th></tr></thead><tbody>{_result_rows(result)}</tbody></table></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">安全说明</div><div class="card-b"><p class="sub">不展示客户业务明细，不展示真实路径，不展示数据库密码或应用密钥。</p><p class="sub">自检仅验证当前登录账号所在租户和项目是否能读取其他租户金丝雀数据；金丝雀数据会在自检后清理。</p><p><a class="ghost-link" href="/backoffice/data-boundaries">返回数据边界检查</a></p></div></section>'''
    return _page('租户隔离自检结果', body)


def register_data_boundary_pages(app, current_user, service=None, repository=None):
    from fastapi import Depends
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/data-boundaries', response_class=HTMLResponse)
    def data_boundary_page(user=Depends(current_user)):
        return HTMLResponse(_render(user))

    @app.post('/backoffice/data-boundaries/self-check', response_class=HTMLResponse)
    def data_boundary_self_check_page(user=Depends(current_user)):
        result = run_isolation_self_check(user, service, repository)
        checked_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return HTMLResponse(_render_self_check_result(user, result, checked_at))
