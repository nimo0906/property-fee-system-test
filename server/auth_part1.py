from server.auth_shared import *
from server.ui_components import render_form, render_table

class AuthMixinPart1(BaseHandler):
    def _is_default_admin_password_active(self):
        db = get_db()
        rows = db.execute("SELECT password_hash FROM users WHERE username=? AND is_active=1", ("admin",)).fetchall()
        db.close()
        return any(verify_password("admin123", row["password_hash"]) for row in rows)

    def _default_admin_user_id(self):
        db = get_db()
        rows = db.execute("SELECT id,password_hash FROM users WHERE username=? AND is_active=1", ("admin",)).fetchall()
        db.close()
        for row in rows:
            if verify_password("admin123", row["password_hash"]):
                return row["id"]
        return None

    def _default_password_warning_html(self):
        admin_id = self._default_admin_user_id()
        if not admin_id:
            return ""
        return f"""<div class="alert alert-warning border-warning alert-warning-compact d-flex justify-content-between align-items-center flex-wrap gap-2">
            <div class="alert-warning-text"><strong><i class="bi bi-shield-exclamation"></i> 检测到默认管理员密码仍在使用</strong>
            <div class="small mt-1">本地版不需要注册互联网账号；建议先改 admin 密码，再按岗位建账号。</div></div>
            <a href="/users/{admin_id}/edit" class="btn btn-sm btn-warning"><i class="bi bi-key"></i> 修改默认密码</a>
        </div>"""

    def _login(self):
        """登录页面"""
        flash = self._get_flash()
        self._html('''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>登录 - 物业管理收费系统</title>
<link href="/static/vendor/bootstrap/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="/static/vendor/bootstrap-icons/bootstrap-icons.min.css">
<link rel="stylesheet" href="/static/auth.css"></head><body class="auth-page">
<div class="auth-shell">
  <section class="auth-copy"><div class="auth-kicker">PROPERTY FINANCE</div><h1>物业收费系统</h1><p>本地桌面财务控制台。登录后进行账单生成、收费登记、合同预警和报表核对。</p></section>
  <section class="auth-card"><div class="auth-inner">
    <div class="auth-brand-row"><img src="/static/brand-emblem.png" alt="金沙国际"><div><b>登录系统</b><span>财务控制台 v2.0</span></div></div>
''' + flash + '''
<form method=POST action="/login">
<div class="mb-3"><label class="form-label">用户名</label><div class="input-group auth-input-group"><span class="input-group-text"><i class="bi bi-person"></i></span><input name="username" class="form-control" required autofocus></div></div>
<div class="mb-3"><label class="form-label">密码</label><div class="input-group auth-input-group"><span class="input-group-text"><i class="bi bi-lock"></i></span><input name="password" type="password" class="form-control" required id="loginPwd"><button class="btn btn-outline-secondary" type="button" onclick="var p=document.getElementById('loginPwd');p.type=p.type=='password'?'text':'password';this.querySelector('i').className=this.querySelector('i').className.includes('eye-slash')?'bi bi-eye':'bi bi-eye-slash'"><i class="bi bi-eye-slash"></i></button></div></div>
<button class="btn btn-primary auth-primary w-100"><i class="bi bi-box-arrow-in-right"></i> 登录</button>
<div class="auth-secondary-line"><span class="text-muted">本机离线运行</span><a href="/register">申请账号</a></div>
<div class="auth-hint"><div><b>次要说明区</b><br>没有账号可提交申请，需管理员启用后登录。</div></div>
</form></div></section>
</div></body></html>''')

    def _register(self):
        """账号申请页面：提交后默认停用，等待管理员审核启用。"""
        flash = self._get_flash()
        self._html("""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>申请账号 - 物业管理收费系统</title>
<link href="/static/vendor/bootstrap/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="/static/vendor/bootstrap-icons/bootstrap-icons.min.css">
<link rel="stylesheet" href="/static/auth.css"></head><body class="auth-page">
<div class="auth-shell">
  <section class="auth-copy"><div class="auth-kicker">ACCOUNT REQUEST</div><h1>申请账号</h1><p>提交后由管理员审核启用。账号只用于本机物业收费系统，不会创建互联网账户。</p></section>
  <section class="auth-card"><div class="auth-inner">
    <div class="auth-brand-row"><img src="/static/brand-emblem.png" alt="金沙国际"><div><b>申请账号</b><span>等待管理员审核启用</span></div></div>
""" + flash + """
<form method=POST action="/register">
<div class="mb-3"><label class="form-label">用户名</label><div class="input-group auth-input-group"><span class="input-group-text"><i class="bi bi-person"></i></span><input name="username" class="form-control" required autofocus></div></div>
<div class="mb-3"><label class="form-label">显示名</label><div class="input-group auth-input-group"><span class="input-group-text"><i class="bi bi-person-badge"></i></span><input name="display_name" class="form-control" placeholder="例如：张三"></div></div>
<div class="mb-3"><label class="form-label">密码</label><div class="input-group auth-input-group"><span class="input-group-text"><i class="bi bi-lock"></i></span><input name="password" type="password" class="form-control" required></div></div>
<div class="mb-3"><label class="form-label">确认密码</label><div class="input-group auth-input-group"><span class="input-group-text"><i class="bi bi-shield-check"></i></span><input name="password_confirm" type="password" class="form-control" required></div></div>
<button class="btn btn-primary auth-primary w-100"><i class="bi bi-person-plus"></i> 提交申请</button>
<div class="auth-secondary-line"><a class="auth-link" href="/login"><i class="bi bi-arrow-left"></i> 返回登录</a><span class="text-muted">管理员启用后可登录</span></div>
<div class="auth-hint"><div><b>审核说明</b><br>申请提交后会显示为待审核/停用，管理员在账号管理中启用后才能登录。</div></div>
</form></div></section>
</div></body></html>""")

    def _register_post(self, d):
        username = qs(d, "username", "").strip()
        display_name = qs(d, "display_name", "").strip()
        password = qs(d, "password", "")
        password_confirm = qs(d, "password_confirm", "")
        if not username or not password:
            return self._redirect("/register?flash=用户名和密码不能为空")
        if not re.match(r"^[A-Za-z0-9_\-]{3,32}$", username):
            return self._redirect("/register?flash=用户名需为3-32位字母、数字、下划线或短横线")
        if len(password) < 6:
            return self._redirect("/register?flash=密码至少6位")
        if password != password_confirm:
            return self._redirect("/register?flash=两次输入的密码不一致")
        pw_hash = hash_password(password)
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users(username,password_hash,display_name,role,is_active) VALUES(?,?,?,?,0)",
                (username, pw_hash, display_name or username, "operator")
            )
            db.commit()
        except Exception:
            db.close()
            return self._redirect("/register?flash=用户名已存在")
        db.close()
        self._audit('register_request', 'user', None, None, {'username': username}, '申请账号，待管理员启用')
        return self._redirect("/login?flash=账号申请已提交，请联系管理员启用后再登录")

    def _login_post(self, d):
        """验证登录（含登录频率限制）"""
        ip = self.client_address[0]
        locked = check_login_rate(ip)
        if locked > 0:
            return self._redirect("/login?flash=登录尝试过于频繁，请" + str(locked) + "分钟后再试")

        username = qs(d, "username", "").strip()
        password = qs(d, "password", "")
        if not username or not password:
            return self._redirect("/login?flash=请输入用户名和密码")
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not u or not verify_password(password, u['password_hash']):
            db.close()
            record_login_attempt(ip, False)
            self._audit('login_failed', 'user', None, None, {'username': username}, '用户名或密码错误')
            return self._redirect("/login?flash=用户名或密码错误")
        if not u["is_active"]:
            db.close()
            record_login_attempt(ip, False)
            self._audit('login_inactive', 'user', u["id"], None, {'username': username}, '账号未启用')
            return self._redirect("/login?flash=账号已提交，待管理员启用")
        record_login_attempt(ip, True)
        cleanup_old_sessions()
        if is_legacy_sha256_hash(u['password_hash']):
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), u['id']))
        token = secrets.token_hex(32)
        db.execute("INSERT INTO sessions(token,user_id) VALUES(?,?)", (token, u["id"]))
        db.commit(); db.close()
        self._audit('login_success', 'user', u["id"], None, {'username': username}, '登录成功')
        # 设置Cookie并重定向
        self.send_response(302)
        self.send_header("Set-Cookie", f"session_token={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400")
        self.send_header("Location", "/")
        self.end_headers()

    def _logout(self):
        """登出：清除会话"""
        cookie = self.headers.get("Cookie", "")
        m = re.search(r"session_token=([^;]+)", cookie)
        if m:
            db = get_db()
            db.execute("DELETE FROM sessions WHERE token=?", (m.group(1),))
            db.commit(); db.close()
            self._audit('logout', 'session', None, None, None, '退出登录')
        self.send_response(302)
        self.send_header("Set-Cookie", "session_token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
        self.send_header("Location", "/login")
        self.end_headers()

    def _users(self):
        u = self._get_current_user()
        if not u or u["role"] not in ("admin", "manager"):
            return self._redirect("/?flash=无权限访问")
        db = get_db()
        rows = db.execute("SELECT * FROM users ORDER BY id").fetchall()
        db.close()
        role_names = {"admin":"管理员","system_admin":"系统管理员","manager":"业务管理员","finance":"财务","cashier":"收费员","frontdesk":"客服业务编辑","executive":"管理层只读","operator":"旧版财务收费","readonly":"旧版只读"}
        role_order = [
            ("admin", "超级管理员"),
            ("system_admin", "系统管理员"),
            ("manager", "业务管理员"),
            ("finance", "财务"),
            ("cashier", "收费员"),
            ("frontdesk", "客服业务编辑"),
            ("executive", "管理层只读"),
            ("operator", "旧版财务收费"),
            ("readonly", "旧版只读"),
        ]
        role_counts = {key: sum(1 for r in rows if r["role"] == key) for key, _ in role_order}
        rh = ""
        for r in rows:
            rl = role_names.get(r["role"], r["role"])
            rl_badge = "danger" if r["role"]=="admin" else "primary" if r["role"]=="manager" else "info" if r["role"]=="operator" else "secondary"
            st_badge = "success" if r["is_active"] else "secondary"
            st_text = "启用" if r["is_active"] else "待审核/停用"
            rh += "<tr>"
            rh += "<td>" + str(r["id"]) + "</td>"
            rh += "<td><strong>" + h(r["username"]) + "</strong></td>"
            rh += "<td>" + h(r["display_name"] or "-") + "</td>"
            rh += "<td><span class='badge bg-" + rl_badge + "'>" + rl + "</span></td>"
            rh += "<td><span class='badge bg-" + st_badge + "'>" + st_text + "</span></td>"
            rh += "<td><small>" + h(str(r["created_at"] or "")[:10]) + "</small></td>"
            rh += "<td>"
            rh += "<a href='/users/" + str(r["id"]) + "/edit' class='btn btn-sm btn-outline-primary'><i class='bi bi-pencil'></i></a> "
            rh += "<form method=POST action='/users/" + str(r["id"]) + "/delete' style=display:inline onsubmit=\"return confirm('确定删除？')\"><button class='btn btn-sm btn-outline-danger'><i class='bi bi-trash'></i></button></form>"
            rh += "</td></tr>"
        users_table = render_table(
            ['ID', '用户名', '显示名', '角色', '状态', '创建时间', '操作'],
            rh,
            empty_text='暂无操作员',
            col_count=7,
        )
        role_strip = ''.join(
            '<div class="maintenance-role-pill{}"><span>{}</span><strong>{}</strong></div>'.format(
                ' danger' if key == 'admin' else ' muted' if count == 0 else '',
                h(label),
                count,
            )
            for key, label in role_order
            for count in [role_counts[key]]
        )
        guide = f'''<div class="card mb-3 maintenance-console-card role-guide-grid"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><strong>首次账号设置建议</strong></div><div class="card-body"><div class="maintenance-role-strip">{role_strip}</div><div class="maintenance-maintenance-links mt-3"><a href="/users?role=finance">财务：资料维护</a><a href="/users?role=frontdesk">客服业务编辑：业主、房间、合同、抄表、导入和催缴</a></div><div class="small text-muted mt-2">超级管理员：admin 保留</div></div></div>'''
        body = (
            '<div class="operator-console">'
            '<div class="page-intro"><div><h2 class="mb-1">操作员管理</h2></div><div class="export-actions"><a href="/users/create" class="btn btn-primary btn-sm"><i class="bi bi-plus-lg"></i> 添加操作员</a></div></div>'
            f'<div class="row g-2 mb-3"><div class="col-md-3 col-6"><div class="summary-tile primary"><div class="label">账号总数</div><strong>{len(rows)}</strong></div></div><div class="col-md-3 col-6"><div class="summary-tile success"><div class="label">启用账号</div><strong>{sum(1 for r in rows if r["is_active"])}</strong></div></div><div class="col-md-3 col-6"><div class="summary-tile"><div class="label">管理员</div><strong>{sum(1 for r in rows if r["role"] == "admin")}</strong></div></div><div class="col-md-3 col-6"><div class="summary-tile warning"><div class="label">停用账号</div><strong>{sum(1 for r in rows if not r["is_active"])}</strong></div></div></div>'
            + self._default_password_warning_html()
            + guide
            + '<div class="card maintenance-console-card"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><strong>操作员档案</strong></div><div class="card-body p-0">'
            + users_table
            + '</div></div>'
            '</div>'
        )
        self._html(self._page("操作员管理", body, "users"))

    def _user_form(self, uid):
        """添加/编辑操作员表单"""
        u = self._get_current_user()
        if not u or u["role"] not in ("admin", "manager"):
            return self._redirect("/?flash=无权限访问")
        db = get_db(); user = None
        if uid: user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        db.close()
        if uid and not user:
            return self._redirect("/users?flash=操作员不存在或已删除")
        if u["role"] == "manager" and user and user["role"] == "admin":
            return self._redirect("/users?flash=无权限编辑超级管理员")
        a = f"/users/{uid}/edit" if uid else "/users/create"
        t = "编辑操作员" if uid else "添加操作员"
        un = h(user["username"]) if user else ""
        dn = h(user["display_name"] or "") if user else ""
        role = user["role"] if user else "finance"
        active = user["is_active"] if user else 1
        pw_required = "" if uid else "required"
        pw_label = "密码" if uid else "密码 *"
        admin_option = ''
        if uid and user and user["role"] == "admin":
            admin_option = '<option value="admin" selected>管理员</option>'
        legacy_option = ''
        if uid and role in ("operator", "readonly"):
            legacy_label = "旧版财务收费" if role == "operator" else "旧版客服只读"
            legacy_option = f'<option value="{role}" selected>{legacy_label}</option>'
        fields_html = f'''
<div class="col-md-6"><label>用户名 <span class="text-danger">*</span></label><input name="username" class="form-control" value="{un}" required></div>
<div class="col-md-6"><label>{pw_label}</label><input name="password" type="password" class="form-control" {"required" if not uid else ""} placeholder="留空不修改密码"></div>
<div class="col-md-6"><label>显示名</label><input name="display_name" class="form-control" value="{dn}"></div>
<div class="col-md-3"><label>角色</label><select name="role" class="form-select">
<option value="manager"{" selected" if role=="manager" else ""} {"disabled" if u["role"]!="admin" else ""}>业务管理员</option>
<option value="finance"{" selected" if role=="finance" else ""}>财务</option>
<option value="cashier"{" selected" if role=="cashier" else ""}>收费员</option>
<option value="frontdesk"{" selected" if role=="frontdesk" else ""}>客服业务编辑</option>
<option value="executive"{" selected" if role=="executive" else ""}>管理层只读</option>
{admin_option}
{legacy_option}</select></div>
<div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" name="is_active" id="ia" {"checked" if active else ""}><label class="form-check-label" for="ia">启用</label></div></div>'''
        form_html = render_form(fields_html, action=a, submit_text='<i class="bi bi-check-lg"></i> 保存', cancel_url='/users')
        self._html(self._page(t, form_html, "users"))
