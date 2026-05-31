#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base handler class with shared methods and URL routing."""

import http.server, urllib.parse, re, json, os

from server.db import get_db, h, qs, log_audit

BASE = os.environ.get('PM_RESOURCE_DIR') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BaseHandler(http.server.BaseHTTPRequestHandler):
    """Base mixin providing shared HTTP methods and routing.
    Other mixins inherit from this or add methods to Handler."""

    def log_message(self, *a): pass

    def _html(self, html, code=200):
        b = html.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _redirect(self, url, flash=''):
        c = ''
        if flash:
            c = urllib.parse.urlencode({'flash': flash})
            url = url + ('&' if '?' in url else '?') + c
        url = urllib.parse.quote(url, safe='/:?=&%')
        self.send_response(302)
        self.send_header('Location', url)
        self.end_headers()

    def _json(self, data):
        b = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _post(self):
        l = int(self.headers.get('Content-Length', 0))
        return urllib.parse.parse_qs(self.rfile.read(l).decode('utf-8'), keep_blank_values=True)

    def _load_template(self, name):
        path = os.path.join(BASE, 'templates', name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return f'<h1>模板加载失败</h1><p>{path}</p>'

    def _get_current_user(self):
        cookie = self.headers.get("Cookie", "")
        m = re.search(r"session_token=([^;]+)", cookie)
        if not m: return None
        token = m.group(1)
        db = get_db()
        u = db.execute("SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=? AND u.is_active=1", (token,)).fetchone()
        db.close()
        return dict(u) if u else None

    def _get_flash(self):
        q = urllib.parse.urlparse(self.path).query
        p = urllib.parse.parse_qs(q)
        msg = p.get('flash', [None])[0]
        if msg: return f'<div class="alert alert-info alert-dismissible fade show">{h(msg)}<button type="button" class="btn btn-close" data-bs-dismiss="alert"></button></div>'
        return ''

    def _page(self, title, content, active='', top_actions=''):
        flash = self._get_flash()
        html = self._load_template('base.html')
        cur_user = self._get_current_user()
        role = cur_user.get("role") if cur_user else ""
        nav_groups = [
            ('工作台', [('index', '/', 'bi-speedometer2', '收费工作台')]),
            ('基础资料', [
                ('owners', '/owners', 'bi-people', '业主管理'),
                ('rooms', '/rooms', 'bi-door-open', '房间管理'),
                ('fee_types', '/fee_types', 'bi-tags', '收费项目'),
                ('batch_ops', '/batch_ops', 'bi-pencil-square', '批量更新'),
                ('meter', '/meter_readings', 'bi-clipboard-data', '抄表管理'),
                ('import', '/import', 'bi-upload', '数据导入'),
            ]),
            ('收费业务', [
                ('billing', '/billing', 'bi-cash-coin', '物业收费'),
                ('commercial_billing', '/commercial_billing', 'bi-building', '商业收费'),
                ('shared_expenses', '/shared_expenses', 'bi-diagram-3', '公摊分摊'),
                ('bills', '/bills', 'bi-receipt', '账单管理'),
                ('payments', '/payments', 'bi-credit-card', '缴费记录'),
                ('payment_orders', '/payment_orders', 'bi-phone', '支付订单'),
                ('collections', '/collections', 'bi-telephone-outbound', '客服催费对象'),
                ('reminders', '/reminders', 'bi-bell', '催缴管理'),
            ]),
            ('财务核对', [
                ('invoices', '/invoices', 'bi-receipt-cutoff', '发票管理'),
                ('reports', '/reports', 'bi-graph-up', '对账报表'),
                ('closing', '/closing', 'bi-lock', '期末结账'),
            ]),
            ('系统维护', [
                ('audit_logs', '/audit_logs', 'bi-journal-check', '操作日志'),
                ('backups', '/backups', 'bi-cloud', '数据备份'),
            ]),
        ]
        if role == "readonly":
            allowed = {'index', 'owners', 'rooms', 'bills', 'collections', 'reminders', 'reports'}
        else:
            allowed = {'index', 'owners', 'rooms', 'fee_types', 'batch_ops', 'meter', 'billing',
                       'commercial_billing', 'bills', 'payments', 'invoices',
                       'payment_orders', 'reports', 'closing', 'backups', 'import', 'reminders', 'audit_logs', 'shared_expenses'}
        user_html = ''
        if cur_user:
            role_label = {"admin": "管理员", "operator": "财务收费", "readonly": "客服只读"}.get(cur_user["role"], cur_user["role"])
            user_html = f'''<div class="sidebar-user">
                <div class="d-flex align-items-center justify-content-between gap-2">
                    <div><div class="name"><i class="bi bi-person-circle"></i> {h(cur_user["display_name"] or cur_user["username"])}</div>
                    <div class="role">{role_label}</div></div>
                    <a href="/logout" class="btn btn-sm btn-outline-light" title="退出"><i class="bi bi-box-arrow-right"></i></a>
                </div>
            </div>'''
        if cur_user and cur_user["role"] == "admin":
            nav_groups[-1][1].append(("users", "/users", "bi-people-fill", "操作员管理"))
            allowed.add('users')
        nav_parts = []
        for group_name, items in nav_groups:
            visible = [item for item in items if item[0] in allowed]
            if not visible:
                continue
            links = ''.join(
                f'<a class="nav-link{" active" if active == a[0] else ""}" href="{a[1]}"><i class="bi {a[2]}"></i><span>{a[3]}</span></a>'
                for a in visible
            )
            nav_parts.append(f'<div class="nav-section"><div class="nav-section-title">{group_name}</div>{links}</div>')
        nav_html = ''.join(nav_parts)
        icons = {'index': 'bi-speedometer2', 'rooms': 'bi-door-open', 'owners': 'bi-people',
                 'fee_types': 'bi-tags', 'batch_ops': 'bi-pencil-square', 'meter': 'bi-clipboard-data', 'repairs': 'bi-tools',
                 'parking': 'bi-car-front', 'invoices': 'bi-receipt-cutoff', 'deposits': 'bi-cash-stack',
                 'reminders': 'bi-bell', 'billing': 'bi-cash-coin', 'commercial_billing': 'bi-building',
                 'shared_expenses': 'bi-diagram-3',
                 'bills': 'bi-receipt', 'payments': 'bi-credit-card', 'payment_orders': 'bi-phone', 'closing': 'bi-lock',
                 'backups': 'bi-cloud', 'import': 'bi-upload', 'reports': 'bi-graph-up',
                 'collections': 'bi-telephone-outbound', 'audit_logs': 'bi-journal-check'}
        icon = icons.get(active, 'bi-speedometer2')
        html = html.replace('{TITLE}', h(title))
        html = html.replace('{CONTENT}', content)
        html = html.replace('{NAV}', nav_html)
        html = html.replace('{USER_HTML}', user_html)
        html = html.replace('{ICON}', icon)
        html = html.replace('{TOP_ACTIONS}', top_actions)
        html = html.replace("{FLASH}", flash)
        return html

    def _audit_context(self):
        u = self._get_current_user() or {}
        return {
            'username': u.get('username') or '',
            'role': u.get('role') or '',
            'ip': self.client_address[0] if self.client_address else '',
        }

    def _audit(self, action, entity_type='', entity_id=None, old_value=None, new_value=None, reason=''):
        ctx = self._audit_context()
        log_audit(action, entity_type, entity_id, ctx['username'], ctx['role'], ctx['ip'], old_value, new_value, reason)

    def _audit_logs(self, q):
        u = self._get_current_user()
        if not u or u.get('role') != 'admin':
            return self._redirect('/?flash=无权限访问操作日志')
        action = qs(q, 'action')
        entity = qs(q, 'entity_type')
        kw = qs(q, 'keyword')
        cond = []
        vals = []
        if action:
            cond.append('action=?'); vals.append(action)
        if entity:
            cond.append('entity_type=?'); vals.append(entity)
        if kw:
            cond.append('(username LIKE ? OR reason LIKE ? OR old_value LIKE ? OR new_value LIKE ?)')
            vals.extend([f'%{kw}%', f'%{kw}%', f'%{kw}%', f'%{kw}%'])
        sql = 'SELECT * FROM audit_logs'
        if cond:
            sql += ' WHERE ' + ' AND '.join(cond)
        sql += ' ORDER BY created_at DESC,id DESC LIMIT 300'
        db = get_db()
        rows = db.execute(sql, vals).fetchall()
        actions = db.execute('SELECT DISTINCT action FROM audit_logs ORDER BY action').fetchall()
        entities = db.execute("SELECT DISTINCT entity_type FROM audit_logs WHERE entity_type IS NOT NULL AND entity_type<>'' ORDER BY entity_type").fetchall()
        db.close()
        action_opts = '<option value="">全部动作</option>' + ''.join(
            f'<option value="{h(r["action"])}"{" selected" if action==r["action"] else ""}>{h(r["action"])}</option>' for r in actions
        )
        entity_opts = '<option value="">全部对象</option>' + ''.join(
            f'<option value="{h(r["entity_type"])}"{" selected" if entity==r["entity_type"] else ""}>{h(r["entity_type"])}</option>' for r in entities
        )
        body = ''.join(
            f'''<tr><td><small>{h(r["created_at"])}</small></td><td><span class="badge status-info">{h(r["action"])}</span></td>
            <td>{h(r["entity_type"] or "-")} #{h(r["entity_id"] or "")}</td><td>{h(r["username"] or "系统")}</td>
            <td>{h(r["reason"] or "-")}</td><td><details><summary>详情</summary><pre class="small mb-0">old: {h(r["old_value"] or "")}\nnew: {h(r["new_value"] or "")}</pre></details></td></tr>'''
            for r in rows
        ) or '<tr><td colspan="6" class="text-center text-muted py-4">暂无操作日志</td></tr>'
        self._html(self._page('操作日志', f'''
        <div class="alert alert-info"><i class="bi bi-journal-check"></i> 记录金额修改、账单删除、备份恢复、用户登录、数据导入等关键操作，便于内部核对。</div>
        <form method="GET" action="/audit_logs" class="row g-2 mb-3">
            <div class="col-md-3"><select name="action" class="form-select">{action_opts}</select></div>
            <div class="col-md-3"><select name="entity_type" class="form-select">{entity_opts}</select></div>
            <div class="col-md-4"><input name="keyword" class="form-control" value="{h(kw)}" placeholder="搜索操作人/原因/详情"></div>
            <div class="col-md-2"><button class="btn btn-primary w-100">筛选</button></div>
        </form>
        <div class="table-responsive"><table class="table table-hover align-middle small">
        <thead><tr><th>时间</th><th>动作</th><th>对象</th><th>操作人</th><th>原因</th><th>详情</th></tr></thead><tbody>{body}</tbody></table></div>
        ''', 'audit_logs'))

    def _empty_state(self, icon, message, btn_text=None, btn_link=None):
        """渲染空状态引导卡片。"""
        btn = ''
        if btn_text and btn_link:
            btn = f'<a href="{btn_link}" class="btn btn-primary mt-3"><i class="bi {icon}"></i> {btn_text}</a>'
        return f'''
        <tr><td colspan="99">
        <div class="text-center py-5">
            <i class="bi {icon}" style="font-size:3rem;color:#ccc"></i>
            <p class="text-muted mt-2 mb-0">{message}</p>
            {btn}
        </div>
        </td></tr>'''

    def _error(self, code=404, msg=None):
        """渲染友好错误页面。"""
        titles = {400: '请求错误', 403: '无权限', 404: '页面未找到', 500: '服务器错误'}
        title = titles.get(code, '错误')
        desc = msg or {'400': '请求格式不正确。', '403': '您没有权限访问此页面。',
                       '404': '您访问的页面不存在，请检查链接是否正确。',
                       '500': '服务器内部错误，请稍后再试。'}.get(str(code), '')
        self._html(self._page(f'{code} {title}', f'''
        <div class="text-center py-5">
            <h1 class="display-1 text-muted">{code}</h1>
            <h4 class="mb-3">{title}</h4>
            <p class="text-muted mb-4">{desc}</p>
            <a href="/" class="btn btn-primary"><i class="bi bi-house-door"></i> 返回首页</a>
        </div>'''), code)

    def _serve_static(self, path):
        static_root = os.path.realpath(os.path.join(BASE, 'static'))
        filepath = os.path.realpath(os.path.join(BASE, path.lstrip('/')))
        if not (filepath == static_root or filepath.startswith(static_root + os.sep)):
            return self._error(404)
        if os.path.exists(filepath) and os.path.isfile(filepath):
            ext = os.path.splitext(filepath)[1]
            ct = {'.js': 'application/javascript', '.css': 'text/css',
                  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                  '.gif': 'image/gif'}.get(ext, 'application/octet-stream')
            with open(filepath, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._error(404)

    # ── GET routing ────────────────────────────────────────────
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if p.startswith('/api/v1/'):
            return self._api_get(p)
        if p == '/owner-portal/login': return self._owner_portal_login_page()
        if p == '/owner-portal/send-code': return self._redirect('/owner-portal/login')
        if p == '/owner-portal/logout': return self._owner_portal_logout()
        if p == '/owner-portal/dashboard': return self._owner_portal_dashboard()
        if p == '/owner-portal/rooms': return self._owner_portal_rooms_page()
        if p == '/owner-portal/bills': return self._owner_portal_bills_page()
        if (m := re.match(r'^/owner-portal/bills/(\d+)$', p)): return self._owner_portal_bill_detail_page(int(m.group(1)))
        if p == '/owner-portal/payment-orders': return self._owner_portal_payment_orders_page()
        if (m := re.match(r'^/owner-portal/payment-orders/([^/]+)$', p)): return self._owner_portal_payment_order_detail_page(m.group(1))
        if p == '/owner-portal/payments': return self._owner_portal_payments_page()
        if p == '/owner-portal/notifications': return self._owner_portal_notifications_page()
        if p == '/owner-portal/invoice-requests': return self._owner_portal_invoice_requests_page()
        if p not in ('/login', '/logout', '/register') and not p.startswith('/static/'):
            u = self._get_current_user()
            if not u:
                return self._redirect('/login')
        if p == '/login': return self._login()
        elif p == '/register': return self._register()
        elif p == '/logout': return self._logout()
        elif p == '/': return self._index()
        elif p == '/rooms': return self._rooms(q)
        elif p == '/late_fee_config': return self._late_fee_config()
        elif p == '/rooms/create': return self._room_form(None)
        elif (m := re.match(r'^/rooms/(\d+)/edit$', p)): return self._room_form(int(m.group(1)))
        elif p == '/owners': return self._owners(q)
        elif p == '/owners/create': return self._owner_form(None)
        elif (m := re.match(r'^/owners/(\d+)/edit$', p)): return self._owner_form(int(m.group(1)))
        elif p == '/fee_types': return self._fee_types()
        elif p == '/batch_ops': return self._batch_ops(q)
        elif p == '/fee_types/create': return self._fee_type_form(None)
        elif p == '/elevator_tiers': return self._elevator_tiers()
        elif (m := re.match(r'^/fee_types/(\d+)/edit$', p)): return self._fee_type_form(int(m.group(1)))
        elif p == '/meter_readings': return self._meter_list(q)
        elif p == '/meter_readings/create': return self._meter_form()
        elif p == '/repairs': return self._repairs(q)
        elif p == '/repairs/create': return self._repair_form(None)
        elif (m := re.match(r'^/repairs/(\d+)$', p)): return self._repair_detail(int(m.group(1)))
        elif p == '/invoices': return self._invoices(q)
        elif (m := re.match(r'^/invoices/(\d+)/print$', p)): return self._invoice_print(int(m.group(1)))
        elif p == '/deposits': return self._deposits(q)
        elif p == '/deposits/create': return self._deposit_form(None)
        elif (m := re.match(r'^/deposits/(\d+)/edit$', p)): return self._deposit_form(int(m.group(1)))
        elif (m := re.match(r'^/deposits/(\d+)/refund$', p)): return self._deposit_refund(int(m.group(1)))
        elif p == '/parking': return self._parking(q)
        elif p == '/parking/create': return self._parking_form(None)
        elif (m := re.match(r'^/parking/(\d+)/edit$', p)): return self._parking_form(int(m.group(1)))
        elif p == '/reminders': return self._reminders(q)
        elif p == '/collections': return self._collections(q)
        elif p == '/reminders/print': return self._reminder_print(q)
        elif p == '/billing': return self._billing()
        elif p == '/billing/calc': return self._redirect('/billing?flash=请从收费页面选择房间和费用后生成账单')
        elif p == '/commercial_billing': return self._commercial_billing()
        elif p == '/shared_expenses': return self._shared_expenses(q)
        elif p == '/bills': return self._bills(q)
        elif p == '/bills/review': return self._bills_review(q)
        elif p == '/bills/generate': return self._bill_gen(q)
        elif p == '/bills/export': return self._bill_export()
        elif p == '/bills/export_generated': return self._bill_export_generated(q)
        elif (m := re.match(r'^/bills/(\d+)$', p)): return self._bill_detail(int(m.group(1)), q)
        elif (m := re.match(r'^/bills/(\d+)/print$', p)): return self._bill_print(int(m.group(1)))
        elif (m := re.match(r'^/bills/(\d+)/pay$', p)): return self._bill_pay(int(m.group(1)))
        elif (m := re.match(r'^/bills/(\d+)/edit$', p)): return self._bill_edit(int(m.group(1)))
        elif p == '/bills/print_batch': return self._bill_print_batch(q)
        elif p == '/bills/receipt': return self._bill_receipt(q)
        elif p == '/bills/receipt_setup': return self._receipt_setup(q)
        elif p == '/bills/export_receipt': return self._export_receipt(q)
        elif p == '/payments': return self._payments(q)
        elif p == '/payments/export.csv': return self._payments_csv(q)
        elif p == '/payment_orders': return self._payment_orders(q)
        elif (m := re.match(r'^/payment_orders/([^/]+)$', p)): return self._payment_order_detail(m.group(1))
        elif p == '/users': return self._users()
        elif p == '/users/create': return self._user_form(None)
        elif (m := re.match(r'^/users/(\d+)/edit$', p)): return self._user_form(int(m.group(1)))
        elif p == '/import': return self._import_page()
        elif p == '/import/template/basic.csv': return self._basic_import_template()
        elif (m := re.match(r'^/import/problem_rows/([A-Za-z0-9_-]+)\.csv$', p)): return self._import_problem_rows_download(m.group(1))
        elif (m := re.match(r'^/import/fee_mapping/([A-Za-z0-9_-]+)\.csv$', p)): return self._fee_mapping_csv_download(m.group(1))
        elif p == '/audit_logs': return self._audit_logs(q)
        elif p == '/backups': return self._backups(q)
        elif p == '/backups/cleanup': return self._backup_cleanup_preview(q)
        elif (m := re.match(r'^/backups/(.+)/restore$', p)): return self._backup_restore_confirm(m.group(1))
        elif (m := re.match(r'^/backups/(.+)/delete$', p)): return self._backup_delete_confirm(m.group(1))
        elif p == '/closing': return self._closing()
        elif p == '/closing/reopen': return self._closing_reopen_confirm(q)
        elif p == '/export/kingdee': return self._export_kingdee(q)
        elif p == '/reports': return self._reports(q)
        elif p == '/reports/reconciliation.csv': return self._reports_reconciliation_csv(q)
        elif p == '/reports/collections.csv': return self._reports_collections_csv(q)
        elif p == '/reports/reconciliation/print': return self._reports_reconciliation_print(q)
        elif (m := re.match(r'^/api/rooms/(\d+)/meter/(\d+)$', p)):
            return self._api_meter(int(m.group(1)), int(m.group(2)))
        elif (m := re.match(r'^/api/owners/(\d+)/info$', p)): return self._api_owner_info(int(m.group(1)))
        elif p == '/api/search_rooms': return self._api_search_rooms(q)
        elif p == '/api/search_owners': return self._api_search_owners(q)
        elif p.startswith('/static/'): return self._serve_static(p)
        elif p == '/api/stats': return self._api_stats()
        else: self._error(404)

    # ── POST routing ───────────────────────────────────────────
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p.startswith('/api/v1/'):
            return self._api_post(p, self._post())
        if p == '/owner-portal/login':
            return self._owner_portal_login_post(self._post())
        if p == '/owner-portal/send-code':
            return self._owner_portal_send_code_post(self._post())
        if (m := re.match(r'^/owner-portal/bills/(\d+)/preview-payment$', p)):
            return self._owner_portal_bill_preview_payment_post(int(m.group(1)), self._post())
        if (m := re.match(r'^/owner-portal/bills/(\d+)/create-order$', p)):
            return self._owner_portal_create_order_post(int(m.group(1)), self._post())
        if (m := re.match(r'^/owner-portal/payment-orders/([^/]+)/mock-paid$', p)):
            return self._owner_portal_mock_paid_post(m.group(1))
        # 文件上传不经过 _post()（multipart 由 _import_upload 自行解析）
        if p == '/import/upload':
            u = self._get_current_user()
            if not u:
                return self._redirect('/login')
            if u.get('role') == 'readonly':
                return self._redirect('/?flash=无权限执行写操作')
            return self._import_upload()
        d = self._post()
        u = None
        if p not in ('/login', '/register'):
            u = self._get_current_user()
            if not u:
                return self._redirect('/login')
            if u.get('role') == 'readonly':
                return self._redirect('/?flash=无权限执行写操作')
            if (p in ('/backups/create', '/backups/cleanup') or re.match(r'^/backups/.+/(restore|delete)$', p)) and u.get('role') != 'admin':
                return self._redirect('/backups?flash=无权限执行备份维护操作')
        if p == '/login': return self._login_post(d)
        elif p == '/register': return self._register_post(d)
        elif p == '/rooms/create': return self._room_create(d)
        elif (m := re.match(r'^/rooms/(\d+)/edit$', p)): return self._room_edit(int(m.group(1)), d)
        elif p == '/late_fee_config/update': return self._late_fee_config_update(d)
        elif (m := re.match(r'^/rooms/(\d+)/delete$', p)): return self._room_delete(int(m.group(1)))
        elif p == '/owners/create': return self._owner_create(d)
        elif (m := re.match(r'^/owners/(\d+)/edit$', p)): return self._owner_edit(int(m.group(1)), d)
        elif (m := re.match(r'^/owners/(\d+)/delete$', p)): return self._owner_delete(int(m.group(1)))
        elif p == '/fee_types/create': return self._fee_type_create(d)
        elif p == '/batch_ops/room_rate': return self._batch_room_rate(d)
        elif p == '/batch_ops/fee_rate': return self._batch_fee_rate(d)
        elif p == '/elevator_tiers/update': return self._elevator_tiers_update(d)
        elif (m := re.match(r'^/fee_types/(\d+)/edit$', p)): return self._fee_type_edit(int(m.group(1)), d)
        elif (m := re.match(r'^/fee_types/(\d+)/delete$', p)): return self._fee_type_delete(int(m.group(1)))
        elif p == '/meter_readings/create': return self._meter_create(d)
        elif (m := re.match(r'^/meter_readings/(\d+)/confirm$', p)): return self._meter_confirm(int(m.group(1)))
        elif (m := re.match(r'^/meter_readings/(\d+)/delete$', p)): return self._meter_delete(int(m.group(1)))
        elif p == '/invoices/create': return self._invoice_create(d)
        elif (m := re.match(r'^/invoices/(\d+)/delete$', p)): return self._invoice_delete(int(m.group(1)))
        elif p == '/deposits/create': return self._deposit_create(d)
        elif (m := re.match(r'^/deposits/(\d+)/edit$', p)): return self._deposit_edit(int(m.group(1)), d)
        elif (m := re.match(r'^/deposits/(\d+)/refund$', p)): return self._deposit_refund_post(int(m.group(1)), d)
        elif (m := re.match(r'^/deposits/(\d+)/delete$', p)): return self._deposit_delete(int(m.group(1)))
        elif p == '/parking/create': return self._parking_create(d)
        elif (m := re.match(r'^/parking/(\d+)/edit$', p)): return self._parking_edit(int(m.group(1)), d)
        elif (m := re.match(r'^/parking/(\d+)/delete$', p)): return self._parking_delete(int(m.group(1)))
        elif p == '/repairs/create': return self._repair_create(d)
        elif (m := re.match(r'^/repairs/(\d+)/status$', p)): return self._repair_status(int(m.group(1)), d)
        elif (m := re.match(r'^/repairs/(\d+)/delete$', p)): return self._repair_delete(int(m.group(1)))
        elif p == '/billing/calc': return self._billing_calc(d)
        elif p == '/shared_expenses/allocate': return self._shared_expense_allocate(d)
        elif p == '/bills/generate': return self._bill_generate(d)
        elif p == '/bills/undo_generated': return self._bill_undo_generated(d)
        elif (m := re.match(r'^/bills/(\d+)/pay$', p)): return self._bill_pay_post(int(m.group(1)), d)
        elif (m := re.match(r'^/bills/(\d+)/edit$', p)): return self._bill_edit_post(int(m.group(1)), d)
        elif (m := re.match(r'^/bills/(\d+)/delete$', p)): return self._bill_delete(int(m.group(1)), d)
        elif p == '/users/create': return self._user_create(d)
        elif (m := re.match(r'^/users/(\d+)/edit$', p)): return self._user_edit(int(m.group(1)), d)
        elif (m := re.match(r'^/users/(\d+)/delete$', p)): return self._user_delete(int(m.group(1)))
        elif p == '/backups/create': return self._backup_create()
        elif p == '/backups/cleanup': return self._backup_cleanup_apply(d)
        elif (m := re.match(r'^/backups/(.+)/restore$', p)): return self._backup_restore(m.group(1))
        elif (m := re.match(r'^/backups/(.+)/delete$', p)): return self._backup_delete(m.group(1))
        elif p == '/closing/close': return self._closing_close(d)
        elif p == '/closing/reopen': return self._closing_reopen(d)
        elif p == '/bills/batch_pay': return self._batch_pay(d)
        elif p == '/bills/batch_edit': return self._bill_batch_edit(d)
        elif p == '/bills/batch_edit/preview': return self._bill_batch_edit_preview(d)
        elif p == '/bills/batch_edit/apply': return self._bill_batch_edit_apply(d)
        elif p == '/bills/export_selected': return self._export_selected(d)
        elif p == '/bills/receipt_by_ids': return self._receipt_by_ids(d)
        elif p == '/bills/print_selected': return self._print_selected(d)
        else: self._error(404)
