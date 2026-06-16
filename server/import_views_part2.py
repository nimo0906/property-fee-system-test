from server.import_views_helpers import *

class ImportViewMixinPart2:
    def _render_problem_rows(self, problem_rows, csv_token):
        if not problem_rows:
            return '''
            <div class="card mb-3"><div class="card-header">问题行明细</div>
            <div class="card-body text-muted">本次没有问题行。</div></div>'''
        rows = ''.join(
            f'<tr><td>{r["row_no"]}</td><td>{h(r["reason"])}</td><td><small>{h(r["raw"])}</small></td></tr>'
            for r in problem_rows[:100]
        )
        more = ''
        if len(problem_rows) > 100:
            more = '<p class="small text-muted">仅显示前 100 条，完整内容请下载 CSV。</p>'
        return f'''
        <div class="card mb-3 import-review-card"><div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
        <span><i class="bi bi-file-earmark-spreadsheet"></i> 问题行明细</span>
        <a class="btn btn-sm btn-outline-primary" href="/import/problem_rows/{h(csv_token)}.csv"><i class="bi bi-download"></i> 下载问题行 CSV</a>
        </div>
        <div class="card-body">
        <p class="small text-muted">这些行未导入或需要人工核对。可下载 CSV，修正后单独重新导入。</p>
        {more}
        <div class="table-responsive"><table class="table table-sm">
        <thead><tr><th>行号</th><th>原因</th><th>原始数据</th></tr></thead>
        <tbody>{rows}</tbody></table></div>
        </div></div>'''

    def _save_problem_rows_csv(self, problem_rows):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['行号', '原因', '原始数据'])
        for row in problem_rows:
            writer.writerow([row.get('row_no', ''), row.get('reason', ''), row.get('raw', '')])
        return save_import_file(buf.getvalue().encode('utf-8-sig'))

    def _import_problem_rows_download(self, token):
        try:
            data = load_import_file(token)
        except FileNotFoundError:
            return self._error(404)
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="problem_rows.csv"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _render_changed_rooms(self, changed_rooms):
        if not changed_rooms:
            return '<tr><td colspan="10" class="text-center text-muted py-3">本次没有新增或更新房间</td></tr>'
        rows = []
        for item in changed_rooms[:100]:
            room_id = item.get('room_id')
            edit = f'<a class="btn btn-sm btn-outline-primary" href="/rooms/{room_id}/edit?source=import">编辑</a>' if room_id else '-'
            contract = ''
            if item.get('contract_start') or item.get('contract_end'):
                contract = f'{h(item.get("contract_start") or "")} ~ {h(item.get("contract_end") or "")}'
            rows.append(f'''<tr>
                <td><span class="badge status-{'success' if item.get('action') == '新增' else 'info'}">{h(item.get('action'))}</span></td>
                <td>{h(item.get('building'))}</td>
                <td><strong>{h(item.get('room_number'))}</strong></td>
                <td>{h(item.get('floor'))}</td>
                <td>{h(item.get('area'))}</td>
                <td>{h(item.get('owner_name'))}</td>
                <td>{h(item.get('owner_phone'))}</td>
                <td><small>{contract or '-'}</small></td>
                <td><small>{h(item.get('notes'))}</small></td>
                <td>{edit}</td>
            </tr>''')
        if len(changed_rooms) > 100:
            rows.append('<tr><td colspan="10" class="text-muted text-center">仅显示前 100 条，请到房间管理继续核对</td></tr>')
        return ''.join(rows)

    def _render_import_billing_next(self, changed_rooms):
        valid = [r for r in changed_rooms if r.get('building') and r.get('category')]
        if not valid:
            return ''
        buildings = sorted({r.get('building') for r in valid})
        categories = sorted({r.get('category') for r in valid})
        params = {}
        if len(buildings) == 1:
            params['building'] = buildings[0]
        if len(categories) == 1:
            params['category'] = categories[0]
        href = '/bills/generate'
        if params:
            href += '?' + urllib.parse.urlencode(params)
        building_scope = '、'.join(buildings[:5]) if len(buildings) <= 5 else f'{len(buildings)} 个楼栋'
        category_scope = '、'.join(categories[:5]) if len(categories) <= 5 else f'{len(categories)} 个类别'
        scope = f'楼栋：{building_scope}；类别：{category_scope}'
        return f'''
        <div class="card mb-3 import-next-card"><div class="card-header text-primary"><i class="bi bi-signpost-2"></i> 下一步生成账单</div>
        <div class="card-body">
        <p class="small text-muted mb-2">基础资料核对无误后，可直接进入账单生成页。系统会带上本次导入范围；进入后仍需先预览，再确认生成。</p>
        <p class="small mb-3">本次范围：{h(scope)}</p>
        <a class="btn btn-primary" href="{h(href)}"><i class="bi bi-receipt"></i> 按导入范围生成账单预览</a>
        <a class="btn btn-outline-secondary" href="/rooms">先查看房间</a>
        </div></div>'''
