#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance result center page for SaaS delivery."""

import datetime as dt
from pathlib import Path

from server.saas_production_acceptance_history import append_history, get_history, history_rows
from server.saas_production_acceptance_package import build_evidence_package
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_FILES = [
    ('acceptance-result', '验收留档', 'release/saas-production-acceptance-result.md'),
    ('release-evidence', '上线证据', 'release/saas-release-evidence.md'),
    ('isolation-evidence', '隔离证据', 'release/saas-isolation-evidence.md'),
]
EVIDENCE_BY_KEY = {key: (label, rel) for key, label, rel in EVIDENCE_FILES}
FORBIDDEN = ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id']


def _safe_text(value):
    text = str(value or '').strip()
    for forbidden in FORBIDDEN:
        text = text.replace(forbidden, '[redacted]')
    return text


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
<section class="card" style="margin-bottom:18px"><div class="card-h">交付证据包</div><div class="card-b"><p class="sub">下载脱敏后的正式交付证据包，包含验收留档、上线证据、租户隔离证据、签收历史和备份覆盖说明。</p><div class="actions"><a class="ghost-link" href="/backoffice/production-acceptance/evidence-package.zip">下载交付证据包</a></div><div class="hint">证据包不包含 生产环境文件、生产密钥、客户上传文件内容或真实服务器绝对路径。</div></div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">生产验收签收</div><div class="card-b"><p class="sub">现场验收通过后填写执行人、服务器域名、客户签收人和实施人员，生成正式验收留档。</p><div class="actions"><a class="ghost-link" href="/backoffice/production-acceptance/signoff">填写生产验收签收信息</a><a class="ghost-link" href="/backoffice/production-acceptance/signoff/print">打印签收表</a><a class="ghost-link" href="/backoffice/production-acceptance/signoff/download.md">下载 Markdown</a></div></div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">一键验收总入口</div><div class="card-b"><p><code>scripts/saas_production_acceptance_gate.py</code></p><p class="sub">串联 生产环境文件 现场校验、生产预检、运行状态、首租户业务冒烟、租户隔离证据和上线证据报告；失败即停止交付。</p></div></section>
<section class="grid"><div class="card"><div class="card-h">验收结果留档文件</div><div class="card-b"><p><code>release/saas-production-acceptance-result.md</code></p><p class="sub">记录执行人、服务器域名、PASS/FAIL、客户签收人和实施人员签字。</p></div></div>
<div class="card"><div class="card-h">上线证据报告</div><div class="card-b"><p><code>release/saas-release-evidence.md</code></p><p class="sub">上线门禁和部署资产的脱敏证据汇总。</p></div></div>
<div class="card"><div class="card-h">租户隔离证据</div><div class="card-b"><p><code>release/saas-isolation-evidence.md</code></p><p class="sub">证明租户隔离、客户上传数据与系统自身数据隔离。</p></div></div>
<div class="card"><div class="card-h">首租户冒烟说明</div><div class="card-b"><p><code>scripts/saas_production_first_tenant_smoke.py</code></p><p class="sub">覆盖登录、收费对象、收费项目、出账、收款、报表、导出和租户隔离。</p></div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">现场执行顺序</div><div class="card-b"><ol><li>运行 <code>scripts/saas_production_acceptance_gate.py</code>。</li><li>查看 <code>release/saas-production-acceptance-result.md</code>。</li><li>核对 <code>release/saas-release-evidence.md</code> 和 <code>release/saas-isolation-evidence.md</code>。</li><li>填写生产验收签收信息并生成留档。</li></ol><div class="hint">本页不展示生产密钥、数据库密码、内部字段或客户真实数据。</div></div></section>'''
    return _page('生产验收结果中心', body)


def _read_evidence(key):
    if key not in EVIDENCE_BY_KEY:
        return None, None, None
    label, rel = EVIDENCE_BY_KEY[key]
    path = ROOT / rel
    text = '# 证据文件未生成\n' if not path.exists() else path.read_text(encoding='utf-8')
    return label, rel, _safe_text(text)


def _signoff_markdown(data):
    f = {key: _safe_text(value) for key, value in data.items()}
    return (
        '# SaaS 生产上线验收结果留档\n\n'
        f'执行人：{f.get("operator_name")}\n'
        f'服务器域名：{f.get("server_domain")}\n'
        f'验收结论：{f.get("acceptance_status")}\n\n'
        '## 验收结果\n\n'
        '- 生产一键验收：已执行\n- 首租户业务冒烟：已确认\n- 租户隔离证据：已确认\n'
        '- 上线证据报告：已确认\n- 客户上传数据与系统自身数据隔离：已确认\n- 业务数据不进入授权云服务：已确认\n\n'
        '## 证据文件\n\n- 本验收留档：release/saas-production-acceptance-result.md\n'
        '- 上线证据：release/saas-release-evidence.md\n- 租户隔离证据：release/saas-isolation-evidence.md\n\n'
        '## 签收\n\n'
        f'客户签收人：{f.get("customer_signer")}\n\n'
        f'实施人员签字：{f.get("implementation_signer")}\n\n'
        f'签收日期：{f.get("signoff_date")}\n\n'
        f'备注：{f.get("notes")}\n'
    )


def _write_signoff(data):
    path = ROOT / 'release' / 'saas-production-acceptance-result.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    text = _signoff_markdown(data)
    path.write_text(text, encoding='utf-8')
    append_history(ROOT, data, text)
    return text


def _require_admin(user):
    if user.get('role_code') not in {'system_admin', 'platform_admin'}:
        raise PermissionDenied('admin only')


def _render_signoff_form(user, message=''):
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    body = f'''<section class="hero"><div><h1>生产验收签收表</h1><div class="sub">填写后生成正式生产验收留档；只记录系统侧交付证据，不保存生产密钥、内部编号或客户上传文件内容。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>{notice}
<section class="card"><div class="card-h">签收信息</div><div class="card-b"><form method="post" action="/backoffice/production-acceptance/signoff"><label>执行人</label><input name="operator_name" required placeholder="例如 实施A"><label>服务器域名</label><input name="server_domain" required placeholder="例如 saas.example.com"><label>验收结论</label><input name="acceptance_status" required value="PASS"><label>客户签收人</label><input name="customer_signer" required placeholder="例如 客户负责人B"><label>实施人员</label><input name="implementation_signer" required placeholder="例如 实施C"><label>签收日期</label><input name="signoff_date" required placeholder="例如 2026-06-19"><label>备注</label><input name="notes" placeholder="例如 现场验收通过"><button class="primary">保存并生成验收留档</button><div class="hint">客户上传数据与系统自身数据隔离；业务数据不进入授权云服务；本表仅保存系统侧验收摘要。</div></form><div class="actions" style="margin-top:12px"><a class="ghost-link" href="/backoffice/production-acceptance/signoff/print">打印签收表</a><a class="ghost-link" href="/backoffice/production-acceptance/signoff/download.md">下载 Markdown</a><a class="ghost-link" href="/backoffice/production-acceptance">返回结果中心</a></div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">签收历史记录</div><div class="card-b"><table><thead><tr><th>序号</th><th>执行人</th><th>客户签收人</th><th>签收日期</th><th>备注</th><th>操作</th></tr></thead><tbody>{history_rows(ROOT, _h)}</tbody></table><div class="hint">历史记录保存在系统侧 release/production_acceptance_signoffs/history.json，不进入租户业务数据或客户上传目录。</div></div></section>'''
    return _page('生产验收签收表', body)


def _printable_signoff_html(user):
    label, rel, text = _read_evidence('acceptance-result')
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>生产验收签收表（打印版）</title><style>body{{font:14px/1.7 "Songti SC","SimSun",serif;color:#111;margin:32px}}h1{{text-align:center;font-size:24px}}pre{{white-space:pre-wrap;border:1px solid #333;padding:12px}}.sign{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;margin-top:42px}}.line{{border-bottom:1px solid #111;height:34px}}.toolbar{{margin-bottom:16px}}@media print{{.toolbar{{display:none}}body{{margin:18mm}}}}</style></head><body><div class="toolbar"><button onclick="window.print()">打印签收表</button></div><h1>生产验收签收表（打印版）</h1><p>客户公司：{_h(user.get('tenant_name'))}　项目名称：{_h(user.get('project_name'))}</p><pre>{_h(text)}</pre><p>客户上传数据与系统自身数据隔离；业务数据不进入授权云服务。</p><div class="sign"><div>客户签字<div class="line"></div></div><div>实施人员签字<div class="line"></div></div><div>签收日期<div class="line"></div></div></div></body></html>'''


def register_production_acceptance_pages(app, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse, Response

    @app.get('/backoffice/production-acceptance/signoff', response_class=HTMLResponse)
    def production_signoff_page(user=Depends(current_user), message: str = ''):
        try:
            _require_admin(user)
            return HTMLResponse(_render_signoff_form(user, message))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/production-acceptance/signoff')
    def production_signoff_submit(operator_name: str = Form(...), server_domain: str = Form(...), acceptance_status: str = Form(...), customer_signer: str = Form(...), implementation_signer: str = Form(...), signoff_date: str = Form(...), notes: str = Form(''), user=Depends(current_user)):
        try:
            _require_admin(user)
            _write_signoff({'operator_name': operator_name, 'server_domain': server_domain, 'acceptance_status': acceptance_status, 'customer_signer': customer_signer, 'implementation_signer': implementation_signer, 'signoff_date': signoff_date, 'notes': notes})
            return RedirectResponse('/backoffice/production-acceptance/signoff?message=%E9%AA%8C%E6%94%B6%E7%95%99%E6%A1%A3%E5%B7%B2%E7%94%9F%E6%88%90', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/production-acceptance/signoff/print', response_class=HTMLResponse)
    def production_signoff_print(user=Depends(current_user)):
        try:
            _require_admin(user)
            return HTMLResponse(_printable_signoff_html(user))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/production-acceptance/signoff/download.md')
    def production_signoff_download(user=Depends(current_user)):
        try:
            _require_admin(user)
            label, rel, text = _read_evidence('acceptance-result')
            return Response(text, media_type='text/markdown; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="saas-production-acceptance-result.md"'})
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')


    @app.get('/backoffice/production-acceptance/signoff/history/{record_id}/download.md')
    def production_signoff_history_download(record_id: int, user=Depends(current_user)):
        try:
            _require_admin(user)
            record = get_history(ROOT, record_id)
            if not record:
                raise HTTPException(status_code=404, detail='not_found')
            filename = f'saas-production-acceptance-signoff-{record_id}.md'
            return Response(record.get('markdown') or '', media_type='text/markdown; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{filename}"'})
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')


    @app.get('/backoffice/production-acceptance/evidence-package.zip')
    def production_evidence_package(user=Depends(current_user)):
        try:
            _require_admin(user)
            content = build_evidence_package(ROOT)
            return Response(content, media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="saas-production-acceptance-evidence.zip"'})
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/production-acceptance/evidence/{evidence_key}', response_class=HTMLResponse)
    def production_evidence_preview(evidence_key: str, user=Depends(current_user)):
        label, rel, text = _read_evidence(evidence_key)
        if not rel:
            raise HTTPException(status_code=404, detail='not_found')
        body = f'<section class="hero"><div><h1>{_h(label)}预览</h1><div class="sub"><code>{_h(rel)}</code></div></div></section><section class="card"><div class="card-b"><pre>{_h(text)}</pre></div></section>'
        return HTMLResponse(_page(f'{label}预览', body))

    @app.get('/backoffice/production-acceptance/evidence/{evidence_key}/download')
    def production_evidence_download(evidence_key: str, user=Depends(current_user)):
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
