#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Visual login page for SaaS commercial backoffice."""

from server.saas_user_pages import _h


def _login_page(message=''):
    notice = f'<div class="notice">{_h(message)}</div>' if message else ''
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>商业版员工后台登录 · 物业收费管理系统 SaaS</title>
<style>
:root{{--ink:#132238;--muted:#64748b;--line:#d6e0ec;--paper:#fff;--brand:#0f4fd7;--deep:#071a3a;--gold:#b88732;}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:radial-gradient(circle at 16% 12%,#dfeaff 0,#f4f7fb 32%,#edf2f8 100%);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{min-height:100vh;display:grid;grid-template-columns:1.08fr .92fr;gap:28px;align-items:center;max-width:1180px;margin:0 auto;padding:42px 26px}}.brand{{position:relative;padding:42px;border:1px solid rgba(15,79,215,.16);border-radius:32px;background:linear-gradient(145deg,rgba(255,255,255,.72),rgba(255,255,255,.36));box-shadow:0 34px 90px rgba(15,42,86,.13);overflow:hidden}}
.brand:before{{content:"";position:absolute;right:-120px;top:-120px;width:320px;height:320px;border-radius:50%;background:linear-gradient(135deg,rgba(15,79,215,.18),rgba(184,135,50,.16))}}.mark{{display:inline-grid;place-items:center;width:54px;height:54px;border-radius:18px;background:var(--deep);color:#fff;font-weight:900;letter-spacing:.08em;margin-bottom:26px}}
h1{{font-size:42px;line-height:1.08;margin:0 0 16px;letter-spacing:-.04em}}.lead{{font-size:17px;color:var(--muted);max-width:620px}}.points{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:30px}}.point{{border:1px solid var(--line);background:rgba(255,255,255,.72);border-radius:18px;padding:15px;font-weight:800}}.point span{{display:block;font-weight:500;color:var(--muted);font-size:13px;margin-top:3px}}
.panel{{background:var(--paper);border:1px solid var(--line);border-radius:28px;box-shadow:0 28px 72px rgba(16,36,70,.16);padding:30px}}.panel-h{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:18px}}.badge{{border:1px solid #bfd1ea;border-radius:999px;padding:6px 11px;color:#174ea6;background:#eef5ff;font-weight:800;font-size:12px}}h2{{margin:0;font-size:25px}}label{{display:block;font-weight:850;margin-top:12px;color:#26364d}}input,select{{width:100%;border:1px solid var(--line);border-radius:14px;padding:12px 13px;margin-top:6px;background:#fbfdff;font:inherit}}button{{width:100%;border:0;border-radius:15px;background:linear-gradient(135deg,var(--brand),#0b2f83);color:#fff;font-weight:900;padding:13px;margin-top:18px;cursor:pointer}}.hint,.notice{{font-size:12px;color:var(--muted);margin-top:12px}}.notice{{border:1px solid #ffd79a;background:#fff8e8;color:#7a4d00;border-radius:12px;padding:9px}}.foot{{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}}.pill{{border:1px solid var(--line);border-radius:999px;padding:5px 9px;font-size:12px;color:#40546d;background:#fff}}
@media(max-width:880px){{.wrap{{grid-template-columns:1fr;padding:24px}}h1{{font-size:32px}}.points{{grid-template-columns:1fr}}}}
</style></head><body><main class="wrap"><section class="brand"><div class="mark">PM</div><h1>物业收费管理系统 SaaS</h1><p class="lead">正式商业云端后台。不同公司独立登录、独立项目、独立收费数据；客户数据隔离，系统自身数据隔离，授权和业务边界分开。</p><div class="points"><div class="point">客户数据隔离<span>收费对象、账单、收款、导入按公司隔离。</span></div><div class="point">系统自身数据隔离<span>部署、备份、授权绑定不混入客户上传数据。</span></div><div class="point">商业授权边界<span>授权云服务只管授权，不承载业务数据。</span></div><div class="point">云端交付闭环<span>Linux/VPS、腾讯云、阿里云部署检查。</span></div></div></section><section class="panel"><div class="panel-h"><div><h2>商业版员工后台登录</h2><div class="hint">演示/测试环境可直接填写公司、项目和角色进入；正式环境接 PostgreSQL 账号密码校验。</div></div><span class="badge">SaaS</span></div>{notice}<form method="post" action="/login"><label>客户公司</label><input name="tenant_name" required placeholder="例如 金桥物业"><label>项目名称</label><input name="project_name" required placeholder="例如 金桥一期"><label>登录账号</label><input name="username" required placeholder="例如 tenant_admin"><label>角色</label><select name="role_code"><option value="system_admin">租户管理员</option><option value="finance">财务</option><option value="cashier">收费员</option><option value="frontdesk">客服业务编辑</option><option value="executive">管理层只读</option><option value="platform_admin">平台管理员</option></select><button>进入员工后台</button></form><div class="foot"><span class="pill">正式商业云端后台</span><span class="pill">租户隔离</span><span class="pill">备份审计</span></div></section></main></body></html>'''


def register_login_pages(app, service, repository, sessions):
    from fastapi import Form
    from fastapi.responses import HTMLResponse, RedirectResponse
    import secrets

    @app.get('/login', response_class=HTMLResponse)
    def login_page(message: str = ''):
        return HTMLResponse(_login_page(message))

    @app.post('/login')
    def login_submit(tenant_name: str = Form(...), project_name: str = Form(...), username: str = Form(...), role_code: str = Form(...)):
        tenant_name = tenant_name.strip()
        project_name = project_name.strip()
        username = username.strip()
        if repository:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail='password login required in persistent mode')
        tenant_id = service.create_tenant(tenant_name)
        project_id = service.create_project(tenant_id, project_name)
        user = service.create_user(tenant_id, username, role_code)
        user.update({'tenant_name': tenant_name, 'project_name': project_name, 'project_id': project_id, 'is_active': 1})
        sid = secrets.token_hex(16)
        sessions[sid] = user
        response = RedirectResponse('/backoffice', status_code=303)
        response.set_cookie('session_id', sid, httponly=True, samesite='lax')
        return response
