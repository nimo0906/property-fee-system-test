#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Permission matrix page for SaaS backoffice."""

from server.saas_user_pages import _h, _page


_ROLE_ROWS = [
    (
        '平台管理员',
        '客户开通、跨租户账号处理、查看平台全局上线状态',
        '平台管理员不能直接创建客户员工；不能承载客户上传业务数据',
        '平台账号与客户公司业务数据隔离，客户员工必须归属具体租户',
    ),
    (
        '租户管理员',
        '租户管理员只能管理本公司员工、维护项目边界、备份恢复演练',
        '不能操作其他公司账号、账单、收款、导入文件或备份记录',
        '所有业务写入必须带 tenant_id；项目数据再带 project_id',
    ),
    (
        '财务',
        '维护收费对象和收费项目、生成并审核账单、登记收款、导入、查看报表',
        '不能管理账号、停用员工、重置密码或执行备份恢复',
        '只能读写本租户本项目的收费业务数据',
    ),
    (
        '收费员',
        '收费员可收款但不能改收费项目；可查看账单和收款结果',
        '不能改收费项目、不能出账、不能管理账号、不能备份恢复',
        '收款流水只进入当前租户和项目',
    ),
    (
        '客服业务编辑',
        '维护收费对象、处理导入预览和导入确认',
        '不能收款、不能出账、不能改账号、不能备份恢复',
        '上传数据与系统自身配置分开保存，确认导入后才写业务表',
    ),
    (
        '管理层只读',
        '只读查看业务数据、报表和审计',
        '管理层只读不能提交业务写入，不能 POST 修改数据',
        '只读访问仍限定在本租户、本项目范围内',
    ),
]


def _render_permission_page(user):
    rows = ''.join(
        '<tr>'
        f'<td><strong>{_h(role)}</strong></td>'
        f'<td>{_h(can_do)}</td>'
        f'<td>{_h(cannot_do)}</td>'
        f'<td>{_h(boundary)}</td>'
        '</tr>'
        for role, can_do, cannot_do, boundary in _ROLE_ROWS
    )
    body = f'''
<section class="hero"><div><h1>权限矩阵</h1><div class="sub">正式商业云端后台角色边界说明：明确可做、不可做、租户隔离和客户上传数据隔离，避免不同公司数据混在一起。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">角色权限边界</div><div class="card-b"><table><thead><tr><th>角色</th><th>可做</th><th>不可做</th><th>租户隔离</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">安全原则</div><div class="card-b"><p class="sub">租户隔离：A 公司不能读取或写入 B 公司的业主、收费对象、账单、收款、导入文件、报表和审计日志。</p><p class="sub">客户上传数据与系统自身账号、部署配置、授权配置分层隔离；业务数据不进入平台系统租户。</p><p class="sub">密码不展示在页面、日志或审计明细；重置密码只记录操作人、目标账号、租户和时间，不记录明文。</p><p class="sub">高风险操作进入审计，包括账号、密码、导入、出账、收款、备份和恢复演练。</p><p><a class="ghost-link" href="/backoffice">返回后台首页</a></p></div></section>'''
    return _page('权限矩阵', body)


def register_permission_pages(app, current_user):
    from fastapi import Depends
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/permissions', response_class=HTMLResponse)
    def permission_page(user=Depends(current_user)):
        return HTMLResponse(_render_permission_page(user))
