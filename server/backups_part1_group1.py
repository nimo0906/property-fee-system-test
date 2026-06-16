from server.backups_shared import *

class BackupMixinPart1Group1(BaseHandler):
    def _backups(self, q=None):
        u = self._get_current_user() or {}
        if u.get('role') != 'admin':
            return self._redirect('/?flash=无权限访问数据备份')
        q = q or {}
        selected_type = q.get('type', [''])[0] if isinstance(q.get('type'), list) else q.get('type', '')
        if not os.path.exists(db_module.BACKUP_DIR):
            os.makedirs(db_module.BACKUP_DIR)
        files = []
        for f in sorted(os.listdir(db_module.BACKUP_DIR), reverse=True):
            fp = os.path.join(db_module.BACKUP_DIR, f)
            if os.path.isfile(fp):
                type_key, type_label = describe_backup_name(f)
                if selected_type and type_key != selected_type:
                    continue
                size = os.path.getsize(fp)
                mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                files.append({'name': f, 'type': type_label, 'size': _format_size(size), 'time': mtime})
        latest = files[0] if files else None
        latest_html = (
            f'''<div><strong>最近一次备份：</strong><code>{h(latest["name"])}</code>
            <span class="text-muted ms-2">{h(latest["time"])} · {h(latest["type"])} · {h(latest["size"])}</span></div>'''
            if latest else '<div><strong>最近一次备份：</strong><span class="text-muted">暂无</span></div>'
        )
        type_opts = '<option value="">全部类型</option>' + ''.join(
            f'<option value="{key}"{" selected" if selected_type == key else ""}>{label}</option>'
            for key, _, label in BACKUP_TYPES
        )
        rows = ''.join(
            f'''<tr>
                <td><small>{h(f["name"])}</small></td>
                <td><span class="badge bg-info text-dark">{h(f["type"])}</span></td>
                <td>{f["size"]}</td>
                <td>{f["time"]}</td>
                <td>
                    <a class="btn btn-sm btn-outline-primary" href="/backups/{h(f["name"])}/preview"><i class="bi bi-search"></i> 预览</a>
                    <a class="btn btn-sm btn-warning" href="/backups/{h(f["name"])}/restore"><i class="bi bi-arrow-counterclockwise"></i> 恢复</a>
                    <a class="btn btn-sm btn-danger" href="/backups/{h(f["name"])}/delete"><i class="bi bi-trash"></i></a>
                </td>
            </tr>'''
            for f in files
        )
        self._html(self._page('数据备份', f'''
        <div class="alert alert-info">
            <i class="bi bi-info-circle"></i>
            备份文件保存在 <code>backups/</code> 目录。系统启动和每日首次使用会自动备份；
            结账或大批量修改前仍建议手动创建备份。
            恢复备份会<strong>覆盖当前数据库</strong>，操作不可撤销。
            <div class="mt-2">{latest_html}
            <div><strong>备份目录：</strong><code>{h(db_module.BACKUP_DIR)}</code></div></div>
        </div>
        <div class="d-flex gap-2 mb-3">
            <form method=POST action="/backups/create">
                <button class="btn btn-primary"><i class="bi bi-cloud-arrow-up"></i> 创建备份</button>
            </form>
            <form method=GET action="/backups" class="d-flex gap-2">
                <select name="type" class="form-select">{type_opts}</select>
                <button class="btn btn-outline-primary">筛选</button>
            </form>
            <a class="btn btn-outline-danger" href="/backups/cleanup?keep=10"><i class="bi bi-trash3"></i> 清理自动备份</a>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle">
                <thead>
                    <tr><th>备份文件</th><th>类型</th><th>大小</th><th>创建时间</th><th style="width:180px">操作</th></tr>
                </thead>
                <tbody>
                    {rows or '<tr><td colspan="5" class="text-center text-muted py-4">暂无备份文件，点击"创建备份"生成</td></tr>'}
                </tbody>
            </table>
        </div>
        ''', 'closing'))

    def _backup_create(self):
        try:
            name = create_db_backup('backup')
            self._redirect('/backups?flash=备份创建成功: ' + name)
        except FileNotFoundError:
            self._redirect('/backups?flash=数据库文件不存在')

    def _backup_preview(self, name):
        bp = _safe_backup_path(name)
        if not bp or not os.path.exists(bp):
            return self._redirect('/backups?flash=备份文件不存在')
        type_key, type_label = describe_backup_name(name)
        size = _format_size(os.path.getsize(bp))
        mtime = datetime.fromtimestamp(os.path.getmtime(bp)).strftime('%Y-%m-%d %H:%M:%S')
        summary_html = _backup_summary_html(read_backup_data_summary(bp))
        self._html(self._page('备份预览', f'''
        <div class="alert alert-info"><strong>备份预览</strong>：只读取备份摘要，不会覆盖当前数据库。</div>
        <div class="card"><div class="card-header">备份文件</div>
        <div class="card-body"><table class="table table-borderless mb-0">
        <tr><td class="text-muted" style="width:130px">备份文件</td><td><code>{h(name)}</code></td></tr>
        <tr><td class="text-muted">备份类型</td><td>{h(type_label)}</td></tr>
        <tr><td class="text-muted">文件大小</td><td>{h(size)}</td></tr>
        <tr><td class="text-muted">创建时间</td><td>{h(mtime)}</td></tr>
        </table></div></div>{summary_html}
        <a href="/backups" class="btn btn-outline-secondary">返回</a>
        ''', 'backups'))
