from server.base_shared import *
import time
import traceback


def _write_request_error(handler, exc):
    log_dir = os.environ.get('PM_LOG_DIR') or os.path.join(BASE, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, 'request_error.log')
    user = {}
    try:
        user = handler._get_current_user() or {}
    except Exception:
        user = {}
    lines = [
        '=' * 80,
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Path: {getattr(handler, 'path', '')}",
        f"Client: {handler.client_address[0] if getattr(handler, 'client_address', None) else ''}",
        f"User: {user.get('username', '')}",
        f"Error: {exc}",
        'Traceback:',
        ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        '',
    ]
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return path

class BaseHandlerPart2(BaseHttpHandler):
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

    def do_GET(self):
        from server.router import handle_get
        try:
            return handle_get(self)
        except Exception as exc:
            _write_request_error(self, exc)
            return self._error(500, '服务器处理请求时出错，错误日志已记录到本机数据目录 logs/request_error.log')

    def do_POST(self):
        from server.router import handle_post
        try:
            return handle_post(self)
        except Exception as exc:
            _write_request_error(self, exc)
            return self._error(500, '服务器处理请求时出错，错误日志已记录到本机数据目录 logs/request_error.log')
