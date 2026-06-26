from server.backups_shared import *
from server.ui_components import render_kv_table

class BackupMixinPart2(BaseHandler):
    def _backup_delete_confirm(self, name):
        fp = _safe_backup_path(name)
        if not fp or not os.path.exists(fp):
            return self._redirect('/backups?flash=备份文件不存在')
        type_key, type_label = describe_backup_name(name)
        size = _format_size(os.path.getsize(fp))
        mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M:%S')
        backup_table = render_kv_table([
            ('备份文件', f'<code>{h(name)}</code>'),
            ('备份类型', h(type_label)),
            ('文件大小', h(size)),
            ('创建时间', h(mtime)),
        ])
        self._html(self._page('删除备份确认', f'''
        <div class="alert alert-danger"><strong>删除备份确认</strong>：删除后无法从系统内恢复，请确认这个备份已经不需要。</div>
        <div class="card"><div class="card-header">将删除的备份</div>
        <div class="card-body">{backup_table}</div></div>
        <form method="POST" action="/backups/{h(name)}/delete" class="d-inline"
            onsubmit="return confirm('最后确认：删除后无法从系统内恢复，确定删除？')">
            <button class="btn btn-danger">确认删除</button>
        </form>
        <a href="/backups" class="btn btn-outline-secondary">取消</a>
        ''', 'backups'))

    def _backup_delete(self, name):
        fp = _safe_backup_path(name)
        if fp and os.path.exists(fp):
            os.remove(fp)
            self._audit('backup_delete', 'backup', None, {'backup': name}, None, '删除备份文件')
        self._redirect('/backups?flash=已删除')
