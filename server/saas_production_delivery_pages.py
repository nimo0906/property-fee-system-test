#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production delivery overview page for on-site SaaS operators."""

import datetime as dt
from pathlib import Path

from server.saas_deploy import validate_deployment_assets
from server.saas_production_acceptance_history import load_history
from server.saas_production_acceptance_package import package_precheck
from server.saas_user_pages import _h, _page

ROOT = Path(__file__).resolve().parents[1]

STEPS = [
    ('1. 生产部署自检', '先确认服务器、端口、Nginx、systemd、日志和目录隔离。', '/backoffice/deploy-checklist', 'scripts/saas_production_precheck.py'),
    ('2. 首租户业务冒烟', '用首租户完成登录、收费对象、收费项目、出账、收款、报表、导出和租户隔离。', '/backoffice/deploy-checklist', 'scripts/saas_production_first_tenant_smoke.py'),
    ('3. 生产一键验收', '串联生产环境校验、预检、运行状态、首租户冒烟、隔离证据和上线证据。', '/backoffice/deploy-checklist', 'scripts/saas_production_acceptance_gate.py'),
    ('4. 生产验收结果中心', '查看验收留档、上线证据、租户隔离证据和证据文件摘要。', '/backoffice/production-acceptance', 'release/saas-production-acceptance-result.md'),
    ('5. 下载交付证据包', '下载脱敏证据包，包含留档、上线证据、隔离证据、签收历史和备份覆盖说明。', '/backoffice/production-acceptance/evidence-package.zip', 'saas-production-acceptance-evidence.zip'),
    ('6. 填写生产验收签收', '填写执行人、服务器域名、客户签收人和实施人员，生成正式验收留档。', '/backoffice/production-acceptance/signoff', 'release/saas-production-acceptance-result.md'),
    ('7. 查看签收历史', '核对每次签收记录均可追溯和下载，避免覆盖后无法查证。', '/backoffice/production-acceptance/signoff', 'production_acceptance_signoffs/history.json'),
    ('8. 备份恢复覆盖核验', '确认 system-files 覆盖生产验收签收历史和当前验收留档。', '/backoffice/backups', 'scripts/saas_backup.sh'),
]


def delivery_status_summary(root=ROOT):
    root = Path(root)
    deploy = validate_deployment_assets(root)
    precheck = package_precheck(root)
    missing = [row for row in precheck if row.get('status') == '缺失']
    history_count = len(load_history(root))
    result_path = root / 'release' / 'saas-production-acceptance-result.md'

    updated = '未生成'
    if result_path.exists():
        updated = dt.datetime.fromtimestamp(
            result_path.stat().st_mtime, dt.timezone.utc
        ).strftime('%Y-%m-%d %H:%M:%S UTC')

    backup_ok = any(
        row.get('package_name') == 'backup-coverage.md'
        and row.get('status') == '自动生成'
        for row in precheck
    )
    ready = (
        deploy.get('ok')
        and not missing
        and history_count > 0
        and result_path.exists()
        and backup_ok
    )
    return {
        'deploy_assets': 'PASS' if deploy.get('ok') else 'WARN',
        'evidence_missing_count': len(missing),
        'signoff_history_count': history_count,
        'acceptance_result_updated_at': updated,
        'backup_coverage': 'PASS' if backup_ok else 'WARN',
        'decision': '可以进入客户签收' if ready else '暂缓客户签收',
    }


def _status_summary_card():
    status = delivery_status_summary(ROOT)
    return f'''
<section class="card" style="margin-bottom:18px">
  <div class="card-h">交付状态汇总</div>
  <div class="card-b">
    <table><tbody>
      <tr><th>部署资产状态</th><td>{_h(status['deploy_assets'])}</td></tr>
      <tr><th>证据缺失数量</th><td>{_h(status['evidence_missing_count'])}</td></tr>
      <tr><th>签收历史数量</th><td>{_h(status['signoff_history_count'])}</td></tr>
      <tr><th>最近验收留档</th><td>{_h(status['acceptance_result_updated_at'])}</td></tr>
      <tr><th>备份覆盖说明</th><td>{_h(status['backup_coverage'])}</td></tr>
      <tr><th>当前签收建议</th><td>{_h(status['decision'])}</td></tr>
    </tbody></table>
    <div class="hint">如果显示“暂缓客户签收”，请先补齐缺失证据、生成验收留档、完成签收历史或修复部署资产。</div>
  </div>
</section>'''


def _step_rows():
    return ''.join(
        f'<tr><td>{_h(name)}</td><td>{_h(desc)}</td><td><a class="ghost-link" href="{_h(href)}">进入</a></td><td><code>{_h(asset)}</code></td></tr>'
        for name, desc, href, asset in STEPS
    )


def _render(user):
    body = f'''
<section class="hero"><div><h1>生产交付总览</h1><div class="sub">现场实施人员统一入口：按顺序完成部署自检、首租户冒烟、生产验收、证据包、签收、历史追溯和备份恢复覆盖核验。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{_status_summary_card()}
<section class="card" style="margin-bottom:18px"><div class="card-h">现场实施顺序</div><div class="card-b"><table><thead><tr><th>步骤</th><th>通过口径</th><th>入口</th><th>关键资产</th></tr></thead><tbody>{_step_rows()}</tbody></table><div class="hint">客户上传数据与系统自身数据隔离；业务数据不进入授权云服务；本页不展示生产密钥、数据库密码、内部字段或真实服务器路径。</div></div></section>
<section class="grid"><div class="card"><div class="card-h">上线门禁</div><div class="card-b"><p><code>scripts/saas_release_gate.py</code></p><p class="sub">所有生产交付检查必须通过后再签收。</p><a class="ghost-link" href="/backoffice/deploy-checklist">查看部署自检</a></div></div>
<div class="card"><div class="card-h">证据留存</div><div class="card-b"><p class="sub">下载证据包前先查看预检状态，缺失项会占位进入总包但应在交付前补齐。</p><a class="ghost-link" href="/backoffice/production-acceptance">进入生产验收结果中心</a></div></div>
<div class="card"><div class="card-h">签收归档</div><div class="card-b"><p class="sub">签收表和历史记录属于系统侧交付证据，不进入客户上传目录。</p><a class="ghost-link" href="/backoffice/production-acceptance/signoff">填写生产验收签收</a></div></div>
<div class="card"><div class="card-h">备份恢复</div><div class="card-b"><p class="sub">恢复演练选择 system-files 后核对生产验收签收历史仍可查看和下载。</p><a class="ghost-link" href="/backoffice/backups">查看备份恢复</a></div></div></section>'''
    return _page('生产交付总览', body)


def register_production_delivery_pages(app, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/production-delivery', response_class=HTMLResponse)
    def production_delivery_page(user=Depends(current_user)):
        try:
            return HTMLResponse(_render(user))
        except Exception:
            raise HTTPException(status_code=403, detail='forbidden')
