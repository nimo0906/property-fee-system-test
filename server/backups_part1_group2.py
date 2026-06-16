from server.backups_shared import *
import urllib.parse

class BackupMixinPart1Group2(BaseHandler):
    def _backup_restore_confirm(self, name):
        bp = _safe_backup_path(name)
        if not bp or not os.path.exists(bp):
            return self._redirect('/backups?flash=备份文件不存在')
        type_key, type_label = describe_backup_name(name)
        size = _format_size(os.path.getsize(bp))
        mtime = datetime.fromtimestamp(os.path.getmtime(bp)).strftime('%Y-%m-%d %H:%M:%S')
        summary_html = _backup_summary_html(read_backup_data_summary(bp))
        self._html(self._page('恢复备份确认', f'''
        <div class="alert alert-danger"><strong>恢复备份确认</strong>：恢复会覆盖当前数据库，请确认选择正确。</div>
        <div class="card"><div class="card-header">将恢复的备份</div>
        <div class="card-body"><table class="table table-borderless mb-0">
        <tr><td class="text-muted" style="width:130px">备份文件</td><td><code>{h(name)}</code></td></tr>
        <tr><td class="text-muted">备份类型</td><td>{h(type_label)}</td></tr>
        <tr><td class="text-muted">文件大小</td><td>{h(size)}</td></tr>
        <tr><td class="text-muted">创建时间</td><td>{h(mtime)}</td></tr>
        </table></div></div>
        {summary_html}
        <div class="alert alert-warning">当前数据会先自动备份为 <code>auto_before_restore_*.db</code>，恢复后如果发现选错，可以在备份页再恢复该自动备份。</div>
        <form method="POST" action="/backups/{h(name)}/restore" class="row g-2 align-items-end"
            onsubmit="return confirm('最后确认：恢复会覆盖当前数据，确定继续？')">
            <div class="col-md-4"><label class="form-label">为避免误操作，请输入“恢复”</label>
            <input class="form-control" name="confirm_text" required placeholder="恢复"></div>
            <div class="col-auto"><button class="btn btn-danger">确认恢复</button></div>
            <div class="col-auto"><a href="/backups" class="btn btn-outline-secondary">取消</a></div>
        </form>
        ''', 'backups'))

    def _backup_restore(self, name, d=None):
        bp = _safe_backup_path(name)
        if not bp or not os.path.exists(bp):
            return self._redirect('/backups?flash=备份文件不存在')
        if (qs(d or {}, 'confirm_text') or '').strip() != '恢复':
            safe_name = urllib.parse.quote(name, safe='')
            return self._redirect(f'/backups/{safe_name}/restore', '请输入“恢复”后再确认')
        restore_backup_name = ''
        if os.path.exists(db_module.DB_PATH):
            restore_backup_name = create_db_backup('auto_before_restore')
        shutil.copy2(bp, db_module.DB_PATH)
        db_init()
        self._audit('backup_restore', 'backup', None, {'backup': name}, {'restore_backup': restore_backup_name}, '恢复数据库备份')
        summary = read_backup_data_summary(db_module.DB_PATH)
        if summary['ok']:
            summary_html = f'''
        <div class="card"><div class="card-header">当前数据库摘要</div><div class="card-body">
        <div class="row g-3 mb-3">
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">房间数</div><div class="fs-4 fw-bold">{summary['rooms']}</div></div></div>
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">业主数</div><div class="fs-4 fw-bold">{summary['owners']}</div></div></div>
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">账单数</div><div class="fs-4 fw-bold">{summary['bills']}</div></div></div>
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">缴费记录数</div><div class="fs-4 fw-bold">{summary['payments']}</div></div></div>
        </div>
        <table class="table table-sm mb-0">
            <tr><td class="text-muted" style="width:140px">账单金额合计</td><td>{m(summary['bill_amount'])}</td></tr>
            <tr><td class="text-muted">缴费金额合计</td><td>{m(summary['payment_amount'])}</td></tr>
            <tr><td class="text-muted">最近账期</td><td>{h(summary['periods'] or '无')}</td></tr>
            <tr><td class="text-muted">主要楼栋</td><td>{h(summary['buildings'] or '无')}</td></tr>
        </table></div></div>'''
        else:
            summary_html = f'<div class="alert alert-warning">当前数据库摘要读取失败：{h(summary["error"])}</div>'
        self._html(self._page('恢复完成', f'''
        <div class="alert alert-success"><strong>恢复完成</strong>：已从 <code>{h(name)}</code> 恢复数据。</div>
        <div class="card"><div class="card-header">恢复结果</div><div class="card-body">
        <table class="table table-borderless mb-0">
            <tr><td class="text-muted" style="width:150px">恢复的备份</td><td><code>{h(name)}</code></td></tr>
            <tr><td class="text-muted">恢复前自动备份</td><td><code>{h(restore_backup_name or '无')}</code></td></tr>
        </table></div></div>
        {summary_html}
        <div class="d-flex gap-2 flex-wrap">
            <a class="btn btn-primary" href="/">去首页</a>
            <a class="btn btn-outline-primary" href="/rooms">查看房间</a>
            <a class="btn btn-outline-primary" href="/bills">查看账单</a>
            <a class="btn btn-outline-secondary" href="/backups">返回备份</a>
        </div>
        ''', 'backups'))

    def _backup_cleanup_preview(self, q=None):
        q = q or {}
        raw_keep = q.get('keep', ['10'])[0] if isinstance(q.get('keep'), list) else q.get('keep', '10')
        selected_type = q.get('type', [''])[0] if isinstance(q.get('type'), list) else q.get('type', '')
        plan = build_backup_cleanup_plan(raw_keep, selected_type)
        rows = ''.join(
            f'''<tr>
                <td><small>{h(item["name"])}</small></td>
                <td><span class="badge bg-warning text-dark">{h(item["type_label"])}</span></td>
                <td>{h(_format_size(item["size_bytes"]))}</td>
                <td>{h(datetime.fromtimestamp(item["mtime"]).strftime('%Y-%m-%d %H:%M:%S'))}</td>
            </tr>'''
            for item in plan['items']
        )
        summary_rows = ''.join(
            f'<tr><td>{h(label)}</td><td>保留最近 {plan["keep"]} 个</td><td>{plan["kept_by_type"].get(key, 0)} 个</td></tr>'
            for key, _, label in BACKUP_TYPES
            if key in _automatic_backup_type_keys()
        )
        type_opts = '<option value="">全部自动备份类型</option>' + ''.join(
            f'<option value="{key}"{" selected" if selected_type == key else ""}>{label}</option>'
            for key, _, label in BACKUP_TYPES
            if key in _automatic_backup_type_keys()
        )
        self._html(self._page('自动备份清理预览', f'''
        <div class="alert alert-warning">
            <strong>自动备份清理预览</strong>：默认只清理自动备份（<code>auto_before_*.db</code>），
            手动备份 <code>backup_*.db</code> 永远不会被本功能自动删除。
        </div>
        <form method="GET" action="/backups/cleanup" class="row g-2 align-items-end mb-3">
            <div class="col-auto">
                <label class="form-label">每类保留最近</label>
                <input class="form-control" name="keep" value="{plan['keep']}" type="number" min="1" max="100">
            </div>
            <div class="col-auto">
                <label class="form-label">清理类型</label>
                <select class="form-select" name="type">{type_opts}</select>
            </div>
            <div class="col-auto"><button class="btn btn-outline-primary">重新预览</button></div>
        </form>
        <div class="card mb-3"><div class="card-header">清理统计</div><div class="card-body">
            <p class="mb-2">将删除 <strong>{plan['total_count']}</strong> 个旧自动备份，预计释放 <strong>{h(_format_size(plan['total_size']))}</strong>。</p>
            <table class="table table-sm mb-0"><thead><tr><th>类型</th><th>规则</th><th>当前保留数</th></tr></thead><tbody>{summary_rows}</tbody></table>
        </div></div>
        <div class="table-responsive"><table class="table table-hover align-middle">
            <thead><tr><th>将删除的备份文件</th><th>类型</th><th>大小</th><th>创建时间</th></tr></thead>
            <tbody>{rows or '<tr><td colspan="4" class="text-center text-muted py-4">没有超过保留数量的自动备份，无需清理</td></tr>'}</tbody>
        </table></div>
        <form method="POST" action="/backups/cleanup" class="d-inline" onsubmit="return confirm('确认清理这些旧自动备份？手动备份不会删除。')">
            <input type="hidden" name="keep" value="{plan['keep']}">
            <input type="hidden" name="type" value="{h(selected_type)}">
            <button class="btn btn-danger" {'disabled' if plan['total_count'] == 0 else ''}>确认清理</button>
        </form>
        <a href="/backups" class="btn btn-outline-secondary">返回备份列表</a>
        ''', 'backups'))

    def _backup_cleanup_apply(self, d):
        raw_keep = d.get('keep', ['10'])[0] if isinstance(d.get('keep'), list) else d.get('keep', '10')
        selected_type = d.get('type', [''])[0] if isinstance(d.get('type'), list) else d.get('type', '')
        plan = build_backup_cleanup_plan(raw_keep, selected_type)
        deleted_count = 0
        freed_size = 0
        for item in plan['items']:
            if not os.path.basename(item['path']).startswith('auto_'):
                continue
            if os.path.exists(item['path']):
                freed_size += os.path.getsize(item['path'])
                os.remove(item['path'])
                deleted_count += 1
        self._redirect(f'/backups?flash=已清理自动备份 {deleted_count} 个，释放空间 {_format_size(freed_size)}')
