#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base handler class with shared methods and URL routing."""

import csv, http.server, io, urllib.parse, re, json, os

from server.db import get_db, h, qs, log_audit
from server.page_layout import render_page

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
        return render_page(self, title, content, active, top_actions)

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

    def _format_audit_value(self, value):
        if not value:
            return ''
        try:
            return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
        except Exception:
            return str(value)

    def _audit_diff_html(self, old_value, new_value):
        changed_fields = self._audit_changed_fields(old_value, new_value)
        if not changed_fields:
            return ''
        try:
            old_data = json.loads(old_value or '{}')
            new_data = json.loads(new_value or '{}')
        except Exception:
            return ''
        rows = []
        for key in changed_fields:
            old = old_data.get(key, '')
            new = new_data.get(key, '')
            rows.append(
                f'<tr><td>{h(key)}</td><td><code>{h(old)}</code></td><td><code>{h(new)}</code></td></tr>'
            )
        return (
            '<div class="mt-2"><div class="fw-semibold text-danger mb-1">字段差异</div>'
            '<table class="table table-sm table-bordered audit-diff-table mb-0">'
            '<thead><tr><th>字段</th><th>原值</th><th>新值</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        )

    def _audit_changed_fields(self, old_value, new_value):
        try:
            old_data = json.loads(old_value or '{}')
            new_data = json.loads(new_value or '{}')
        except Exception:
            return []
        if not isinstance(old_data, dict) or not isinstance(new_data, dict):
            return []
        return [
            key for key in sorted(set(old_data.keys()) | set(new_data.keys()))
            if old_data.get(key, '') != new_data.get(key, '')
        ]

    def _audit_log_filters(self, q):
        action = qs(q, 'action')
        entity = qs(q, 'entity_type')
        kw = qs(q, 'keyword')
        username = qs(q, 'username')
        date_from = qs(q, 'date_from')
        date_to = qs(q, 'date_to')
        risk = qs(q, 'risk')
        cond = []
        vals = []
        if action:
            cond.append('action=?'); vals.append(action)
        if entity:
            cond.append('entity_type=?'); vals.append(entity)
        if username:
            cond.append('username LIKE ?'); vals.append(f'%{username}%')
        if date_from:
            cond.append('created_at>=?'); vals.append(date_from + ' 00:00:00')
        if date_to:
            cond.append('created_at<=?'); vals.append(date_to + ' 23:59:59')
        if risk == 'high':
            cond.append('(action LIKE "%delete%" OR action LIKE "%restore%" OR action LIKE "%reset%" OR action LIKE "%rollback%" OR action LIKE "%amount_update%" OR action LIKE "batch_%")')
        if kw:
            cond.append('(action LIKE ? OR username LIKE ? OR ip LIKE ? OR reason LIKE ? OR old_value LIKE ? OR new_value LIKE ?)')
            vals.extend([f'%{kw}%', f'%{kw}%', f'%{kw}%', f'%{kw}%', f'%{kw}%', f'%{kw}%'])
        return cond, vals, {
            'action': action, 'entity': entity, 'kw': kw,
            'username': username, 'date_from': date_from, 'date_to': date_to, 'risk': risk,
        }

    def _audit_logs(self, q):
        u = self._get_current_user()
        if not u or u.get('role') != 'admin':
            return self._redirect('/?flash=无权限访问操作日志')
        cond, vals, params = self._audit_log_filters(q)
        sql = 'SELECT * FROM audit_logs'
        if cond:
            sql += ' WHERE ' + ' AND '.join(cond)
        sql += ' ORDER BY created_at DESC,id DESC LIMIT 300'
        db = get_db()
        rows = db.execute(sql, vals).fetchall()
        summary_sql = 'SELECT COUNT(*) total, SUM(CASE WHEN action LIKE "%delete%" OR action LIKE "%restore%" OR action LIKE "%reset%" OR action LIKE "%rollback%" OR action LIKE "%amount_update%" OR action LIKE "batch_%" THEN 1 ELSE 0 END) risk_count, SUM(CASE WHEN action LIKE "login_%" THEN 1 ELSE 0 END) login_count FROM audit_logs'
        if cond:
            summary_sql += ' WHERE ' + ' AND '.join(cond)
        summary = db.execute(summary_sql, vals).fetchone()
        actions = db.execute('SELECT DISTINCT action FROM audit_logs ORDER BY action').fetchall()
        entities = db.execute("SELECT DISTINCT entity_type FROM audit_logs WHERE entity_type IS NOT NULL AND entity_type<>'' ORDER BY entity_type").fetchall()
        db.close()
        action_opts = '<option value="">全部动作</option>' + ''.join(
            f'<option value="{h(r["action"])}"{" selected" if params["action"]==r["action"] else ""}>{h(r["action"])}</option>' for r in actions
        )
        entity_opts = '<option value="">全部对象</option>' + ''.join(
            f'<option value="{h(r["entity_type"])}"{" selected" if params["entity"]==r["entity_type"] else ""}>{h(r["entity_type"])}</option>' for r in entities
        )
        query = urllib.parse.urlencode({
            'action': params['action'], 'entity_type': params['entity'], 'keyword': params['kw'],
            'username': params['username'], 'date_from': params['date_from'], 'date_to': params['date_to'], 'risk': params['risk'],
        })
        body = ''.join(
            f'''<tr><td><input type="checkbox" name="log_ids" value="{r["id"]}" form="auditDeleteForm"></td><td><small>{h(r["created_at"])}</small></td><td><span class="badge status-info">{h(r["action"])}</span></td>
            <td>{h(r["entity_type"] or "-")} #{h(r["entity_id"] or "")}</td><td>{h(r["username"] or "系统")}</td>
            <td>{h(r["reason"] or "-")}</td><td><details><summary>格式化详情</summary><pre class="small mb-0">old: {h(self._format_audit_value(r["old_value"]))}\nnew: {h(self._format_audit_value(r["new_value"]))}</pre>{self._audit_diff_html(r["old_value"], r["new_value"])}</details></td></tr>'''
            for r in rows
        ) or '<tr><td colspan="7" class="text-center text-muted py-4">暂无操作日志</td></tr>'
        self._html(self._page('操作日志', f'''
        <div class="alert alert-info"><i class="bi bi-journal-check"></i> 记录金额修改、账单删除、备份恢复、用户登录、数据导入等关键操作，便于内部核对。</div>
        <div class="metric-grid mb-3">
            <div class="metric-card primary"><div class="metric-label">审计摘要</div><div class="metric-value">{summary["total"] or 0}</div><small class="text-muted">当前筛选日志</small></div>
            <div class="metric-card danger"><div class="metric-label">高风险操作</div><div class="metric-value">{summary["risk_count"] or 0}</div><small class="text-muted">删除/恢复/清空/金额修改</small></div>
            <div class="metric-card success"><div class="metric-label">登录事件</div><div class="metric-value">{summary["login_count"] or 0}</div><small class="text-muted">登录成功/失败/停用</small></div>
        </div>
        <div class="d-flex gap-2 flex-wrap mb-3"><span class="badge bg-light text-dark border">高风险快捷筛选</span>
            <a class="btn btn-sm {"btn-danger" if params["risk"]=="high" else "btn-outline-danger"}" href="/audit_logs?risk=high"><i class="bi bi-shield-exclamation"></i> 只看高风险</a>
            <input type="hidden" name="risk" value="{h(params["risk"])}" form="auditFilterForm">
        </div>
        <form method="GET" action="/audit_logs" class="row g-2 mb-3" id="auditFilterForm">
            <div class="col-md-2"><select name="action" class="form-select">{action_opts}</select></div>
            <div class="col-md-2"><select name="entity_type" class="form-select">{entity_opts}</select></div>
            <div class="col-md-2"><input name="username" class="form-control" value="{h(params["username"])}" placeholder="操作人"></div>
            <div class="col-md-2"><input name="date_from" type="date" class="form-control" value="{h(params["date_from"])}"></div>
            <div class="col-md-2"><input name="date_to" type="date" class="form-control" value="{h(params["date_to"])}"></div>
            <div class="col-md-2"><input name="keyword" class="form-control" value="{h(params["kw"])}" placeholder="原因/详情/IP"></div>
            <div class="col-md-12 d-flex gap-2"><button class="btn btn-primary"><i class="bi bi-search"></i> 筛选</button><a class="btn btn-outline-secondary" href="/audit_logs">重置</a><a class="btn btn-outline-success" href="/audit_logs/export.csv?{h(query)}"><i class="bi bi-download"></i> 导出CSV</a></div>
        </form>
        <form method="POST" action="/audit_logs/delete" id="auditDeleteForm" class="mb-2"
            onsubmit="return confirm('确认删除选中的操作日志？')">
            <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> 删除选中</button>
        </form>
        <div class="table-responsive"><table class="table table-hover align-middle small">
        <thead><tr><th>选择</th><th>时间</th><th>动作</th><th>对象</th><th>操作人</th><th>原因</th><th>详情</th></tr></thead><tbody>{body}</tbody></table></div>
        ''', 'audit_logs'))

    def _audit_logs_csv(self, q):
        u = self._get_current_user()
        if not u or u.get('role') != 'admin':
            return self._redirect('/?flash=无权限访问操作日志')
        cond, vals, _ = self._audit_log_filters(q)
        sql = 'SELECT * FROM audit_logs'
        if cond:
            sql += ' WHERE ' + ' AND '.join(cond)
        sql += ' ORDER BY created_at DESC,id DESC LIMIT 2000'
        db = get_db()
        rows = db.execute(sql, vals).fetchall()
        db.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['created_at','action','entity_type','entity_id','username','role','ip','reason','changed_fields','old_value','new_value'])
        for r in rows:
            changed_fields = ';'.join(self._audit_changed_fields(r['old_value'], r['new_value']))
            w.writerow([r['created_at'], r['action'], r['entity_type'], r['entity_id'], r['username'], r['role'], r['ip'], r['reason'], changed_fields, r['old_value'], r['new_value']])
        raw = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename=audit_logs.csv')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _audit_logs_delete(self, d):
        u = self._get_current_user()
        if not u or u.get('role') != 'admin':
            return self._redirect('/?flash=无权限执行该操作')
        raw = d.get('log_ids', [])
        if isinstance(raw, str):
            raw = [raw]
        ids = [x for x in raw if str(x).isdigit()]
        if not ids:
            return self._redirect('/audit_logs?flash=请勾选要删除的日志')
        db = get_db()
        db.execute(f'DELETE FROM audit_logs WHERE id IN ({",".join("?" * len(ids))})', ids)
        db.commit(); db.close()
        return self._redirect('/audit_logs?flash=已删除选中日志')

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

    # ── routing ───────────────────────────────────────────────
    def do_GET(self):
        from server.router import handle_get
        return handle_get(self)

    def do_POST(self):
        from server.router import handle_post
        return handle_post(self)
