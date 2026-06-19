#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance result center page for SaaS delivery."""

from server.saas_user_pages import _h, _page


def _render_production_acceptance(user):
    body = f'''
<section class="hero"><div><h1>生产验收结果中心</h1><div class="sub">实施人员现场交付统一入口：一键验收总入口、验收结果留档文件、上线证据报告、租户隔离证据和首租户冒烟说明。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">一键验收总入口</div><div class="card-b"><p><code>scripts/saas_production_acceptance_gate.py</code></p><p class="sub">串联 .env 现场校验、生产预检、运行状态、首租户业务冒烟、租户隔离证据和上线证据报告；失败即停止交付。</p></div></section>
<section class="grid"><div class="card"><div class="card-h">验收结果留档文件</div><div class="card-b"><p><code>release/saas-production-acceptance-result.md</code></p><p class="sub">记录执行人、服务器域名、PASS/FAIL、客户签收人和实施人员签字。</p></div></div>
<div class="card"><div class="card-h">上线证据报告</div><div class="card-b"><p><code>release/saas-release-evidence.md</code></p><p class="sub">上线门禁和部署资产的脱敏证据汇总。</p></div></div>
<div class="card"><div class="card-h">租户隔离证据</div><div class="card-b"><p><code>release/saas-isolation-evidence.md</code></p><p class="sub">证明租户隔离、客户上传数据与系统自身数据隔离。</p></div></div>
<div class="card"><div class="card-h">首租户冒烟说明</div><div class="card-b"><p><code>scripts/saas_production_first_tenant_smoke.py</code></p><p class="sub">覆盖登录、收费对象、收费项目、出账、收款、报表、导出和租户隔离。</p></div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">现场执行顺序</div><div class="card-b"><ol><li>运行 <code>scripts/saas_production_acceptance_gate.py</code>。</li><li>查看 <code>release/saas-production-acceptance-result.md</code>。</li><li>核对 <code>release/saas-release-evidence.md</code> 和 <code>release/saas-isolation-evidence.md</code>。</li><li>由客户签收人和实施人员补充签字。</li></ol><div class="hint">本页不展示生产密钥、数据库密码、内部字段或客户真实数据。</div></div></section>'''
    return _page('生产验收结果中心', body)


def register_production_acceptance_pages(app, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/production-acceptance', response_class=HTMLResponse)
    def production_acceptance_page(user=Depends(current_user)):
        try:
            return HTMLResponse(_render_production_acceptance(user))
        except Exception:
            raise HTTPException(status_code=403, detail='forbidden')
