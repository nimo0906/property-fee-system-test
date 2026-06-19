#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance result center page for SaaS delivery."""

import datetime as dt
from pathlib import Path

from server.saas_user_pages import _h, _page

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_FILES = [
    ('acceptance-result', '验收留档', 'release/saas-production-acceptance-result.md'),
    ('release-evidence', '上线证据', 'release/saas-release-evidence.md'),
    ('isolation-evidence', '隔离证据', 'release/saas-isolation-evidence.md'),
]
EVIDENCE_BY_KEY = {key: (label, rel) for key, label, rel in EVIDENCE_FILES}


def evidence_summary(root=ROOT):
    rows = []
    for key, label, rel in EVIDENCE_FILES:
        path = Path(root) / rel
        exists = path.exists()
        updated = '未生成'
        if exists:
            updated = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        rows.append({'key': key, 'label': label, 'path': rel, 'status': '存在' if exists else '缺失', 'updated_at': updated})
    return rows


def _summary_rows():
    rows = []
    for row in evidence_summary():
        preview_url = f'/backoffice/production-acceptance/evidence/{row["key"]}'
        download_url = f'{preview_url}/download'
        rows.append(f'<tr><td>{_h(row["label"])}：{_h(row["status"])}</td><td><code>{_h(row["path"])}</code></td><td>{_h(row["updated_at"])}</td><td><a class="ghost-link" href="{_h(preview_url)}">预览</a> <a class="ghost-link" href="{_h(download_url)}">下载</a></td></tr>')
    return ''.join(rows)


def _render_production_acceptance(user):
    body = f'''
<section class="hero"><div><h1>生产验收结果中心</h1><div class="sub">实施人员现场交付统一入口：一键验收总入口、验收结果留档文件、上线证据报告、租户隔离证据和首租户冒烟说明。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">证据文件摘要</div><div class="card-b"><table><thead><tr><th>状态</th><th>文件</th><th>最近生成时间</th><th>操作</th></tr></thead><tbody>{_summary_rows()}</tbody></table></div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">一键验收总入口</div><div class="card-b"><p><code>scripts/saas_production_acceptance_gate.py</code></p><p class="sub">串联 .env 现场校验、生产预检、运行状态、首租户业务冒烟、租户隔离证据和上线证据报告；失败即停止交付。</p></div></section>
<section class="grid"><div class="card"><div class="card-h">验收结果留档文件</div><div class="card-b"><p><code>release/saas-production-acceptance-result.md</code></p><p class="sub">记录执行人、服务器域名、PASS/FAIL、客户签收人和实施人员签字。</p></div></div>
<div class="card"><div class="card-h">上线证据报告</div><div class="card-b"><p><code>release/saas-release-evidence.md</code></p><p class="sub">上线门禁和部署资产的脱敏证据汇总。</p></div></div>
<div class="card"><div class="card-h">租户隔离证据</div><div class="card-b"><p><code>release/saas-isolation-evidence.md</code></p><p class="sub">证明租户隔离、客户上传数据与系统自身数据隔离。</p></div></div>
<div class="card"><div class="card-h">首租户冒烟说明</div><div class="card-b"><p><code>scripts/saas_production_first_tenant_smoke.py</code></p><p class="sub">覆盖登录、收费对象、收费项目、出账、收款、报表、导出和租户隔离。</p></div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">现场执行顺序</div><div class="card-b"><ol><li>运行 <code>scripts/saas_production_acceptance_gate.py</code>。</li><li>查看 <code>release/saas-production-acceptance-result.md</code>。</li><li>核对 <code>release/saas-release-evidence.md</code> 和 <code>release/saas-isolation-evidence.md</code>。</li><li>由客户签收人和实施人员补充签字。</li></ol><div class="hint">本页不展示生产密钥、数据库密码、内部字段或客户真实数据。</div></div></section>'''
    return _page('生产验收结果中心', body)


def _read_evidence(key):
    if key not in EVIDENCE_BY_KEY:
        return None, None, None
    label, rel = EVIDENCE_BY_KEY[key]
    path = ROOT / rel
    if not path.exists():
        return label, rel, '# 证据文件未生成\n'
    text = path.read_text(encoding='utf-8')
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo', 'tenant_id', 'project_id']:
        text = text.replace(forbidden, '[redacted]')
    return label, rel, text


def register_production_acceptance_pages(app, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/production-acceptance/evidence/{evidence_key}', response_class=HTMLResponse)
    def production_evidence_preview(evidence_key: str, user=Depends(current_user)):
        label, rel, text = _read_evidence(evidence_key)
        if not rel:
            raise HTTPException(status_code=404, detail='not_found')
        body = f'<section class="hero"><div><h1>{_h(label)}预览</h1><div class="sub"><code>{_h(rel)}</code></div></div></section><section class="card"><div class="card-b"><pre>{_h(text)}</pre></div></section>'
        return HTMLResponse(_page(f'{label}预览', body))

    @app.get('/backoffice/production-acceptance/evidence/{evidence_key}/download')
    def production_evidence_download(evidence_key: str, user=Depends(current_user)):
        from fastapi.responses import Response
        label, rel, text = _read_evidence(evidence_key)
        if not rel:
            raise HTTPException(status_code=404, detail='not_found')
        filename = rel.split('/')[-1]
        return Response(text, media_type='text/markdown; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    @app.get('/backoffice/production-acceptance', response_class=HTMLResponse)
    def production_acceptance_page(user=Depends(current_user)):
        try:
            return HTMLResponse(_render_production_acceptance(user))
        except Exception:
            raise HTTPException(status_code=403, detail='forbidden')
