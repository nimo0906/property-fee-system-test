#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deployment checklist pages for SaaS backoffice."""

from pathlib import Path

from server.saas_deploy import validate_deployment_assets
from server.saas_password_policy import password_policy_summary
from server.saas_user_pages import _h, _page

ROOT = Path(__file__).resolve().parents[1]


def _render_deploy_checklist(user):
    result = validate_deployment_assets(ROOT)
    files = result.get('files', [])
    missing = result.get('missing', [])
    isolation = result.get('isolation', {})
    nginx_tls = result.get('nginx_tls', {})
    port_binding = result.get('port_binding', {})
    restart_policy = result.get('restart_policy', {})
    healthcheck = result.get('healthcheck', {})
    status = 'PASS' if result.get('ok') else 'WARN'
    file_items = ''.join(f'<li>{_h(name)}</li>' for name in files)
    missing_items = ''.join(f'<li>{_h(name)}</li>' for name in missing) or '<li>无</li>'
    compose_ports = ', '.join(port_binding.get('ports') or []) or '无'
    policy_items = ''.join(f'<li>{_h(text)}</li>' for text in password_policy_summary())
    body = f'''
<section class="hero"><div><h1>VPS 上线操作清单</h1><div class="sub">正式商业云端后台上线前的只读清单。这里展示部署资产、目录隔离、端口绑定、HTTPS 终止要求和备份恢复路径，不执行任何线上操作。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><strong>部署检查：</strong>{_h(status)}<span class="hint"> · 只读校验结果基于当前仓库文件</span></div></section>
<section class="grid"><div class="card"><div class="card-h">部署资产</div><div class="card-b"><ul><li>scripts/saas_preflight_check.py</li><li>scripts/saas_acceptance_check.py</li><li>scripts/saas_ops_check.py</li><li>docs/saas-cloud-ops-runbook.md</li><li>docs/saas-phase-1-closure-report.md</li><li>scripts/saas_phase1_closure_check.py</li><li>docker compose up -d</li><li>deploy/nginx/property-saas.conf</li><li>deploy/systemd/property-saas.service</li><li>scripts/saas_backup.sh</li><li>scripts/saas_restore.sh --verify-metadata</li></ul><div class="hint">已存在文件：<ul>{file_items}</ul></div><div class="hint">缺失文件：<ul>{missing_items}</ul></div></div></div>
<div class="card"><div class="card-h">隔离与运行边界</div><div class="card-b"><p class="sub">客户目录：{_h(isolation.get('customer_files'))}</p><p class="sub">系统目录：{_h(isolation.get('system_files'))}</p><p class="sub">备份目录：{_h(isolation.get('backups'))}</p><p class="sub">日志目录：{_h(isolation.get('logs'))}</p><p class="sub">应用端口：{_h(compose_ports)}</p><p class="sub">Nginx TLS：{_h(nginx_tls.get('status'))}</p><p class="sub">重启策略：postgres={_h(restart_policy.get('postgres'))}，app={_h(restart_policy.get('app'))}</p><p class="sub">健康检查：postgres={_h(healthcheck.get('postgres_has_healthcheck'))}，app={_h(healthcheck.get('app_has_healthcheck'))}</p><p class="sub">生产前必须在 Nginx 或上游负载均衡终止 HTTPS。</p></div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">密码策略</div><div class="card-b"><ul>{policy_items}</ul></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">上线步骤</div><div class="card-b"><ol><li>准备 .env.example 对应的生产环境变量，不提交真实 .env。</li><li>执行 scripts/saas_preflight_check.py。</li><li>执行 scripts/saas_acceptance_check.py。</li><li>执行 scripts/saas_ops_check.py。</li><li>执行 scripts/saas_phase1_closure_check.py，确认第一阶段收口。</li><li>使用 docker compose up -d 启动 PostgreSQL 和 app。</li><li>确认应用仅绑定 127.0.0.1:8000。</li><li>配置 deploy/nginx/property-saas.conf 进行 HTTPS 终止。</li><li>安装 deploy/logrotate/property-saas：日志轮转安装。</li><li>按管理员重置密码流程抽查租户管理员和平台管理员边界。</li><li>执行 scripts/saas_backup.sh 和 scripts/saas_restore.sh --verify-metadata 做演练，并保留恢复演练证据。</li></ol><div class="hint">本页只展示 checklist，不展示 POSTGRES_PASSWORD、APP_SECRET_KEY 或其他敏感值。</div></div></section>'''
    return _page('VPS 上线操作清单', body)


def register_deploy_pages(app, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/deploy-checklist', response_class=HTMLResponse)
    def deploy_checklist(user=Depends(current_user)):
        try:
            return HTMLResponse(_render_deploy_checklist(user))
        except Exception:
            raise HTTPException(status_code=403, detail='forbidden')
