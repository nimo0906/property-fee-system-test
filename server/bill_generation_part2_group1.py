from server.bill_generation_shared import *

class BillGenerationMixinPart2Group1(BaseHandler):
    def _render_bill_generation_preview(self, period, due_day, ft_ids, plan, filters=None, period_start='', period_end='', precheck=False):
        filters = filters or {}
        fee_totals = {}
        category_totals = {}
        room_keys = set()
        for item in plan['items']:
            fee_totals[item['fee_name']] = fee_totals.get(item['fee_name'], 0) + item['amount']
            category_totals[item['category']] = category_totals.get(item['category'], 0) + item['amount']
            room_keys.add(item['room_id'])
        fee_rows = ''.join(f'<tr><td>{h(k)}</td><td class="text-end">¥{m(v)}</td></tr>' for k, v in fee_totals.items())
        cat_rows = ''.join(f'<tr><td>{h(k)}</td><td class="text-end">¥{m(v)}</td></tr>' for k, v in category_totals.items())
        detail_rows = ''.join(
            f'<tr><td>{h(x["building"])}-{h(x["room_number"])}</td><td>{h(x["category"])}</td><td>{h(x["fee_name"])}</td><td>{h(x["formula"])}</td><td class="text-end">¥{m(x["amount"])}</td></tr>'
            for x in plan['items'][:50]
        )
        ids = ','.join(str(x) for x in ft_ids)
        filter_summary = self._bill_filter_summary(filters)
        service_range = f'{h(period_start)} 至 {h(period_end)}'
        hidden_filters = ''.join(
            f'<input type="hidden" name="{h(k)}" value="{h(v)}">'
            for k, v in filters.items() if v
        )
        title = '出账前核对' if precheck else '生成账单预览'
        alert = (
            '<strong>出账前核对</strong>：请核对户数、收费项目、金额合计和异常清单；确认后才会写入账单。'
            if precheck else
            '<strong>生成账单预览</strong>：当前页面只预览，不写入账单。确认后才会生成。'
        )
        confirm_label = '确认生成账单' if precheck else '确认生成账单'
        warning_html = self._render_bill_generation_warnings(plan['items'])
        reviewed = '<input type="hidden" name="reviewed" value="1">' if precheck else ''
        self._html(self._page(title, f'''
        <div class="alert alert-warning">{alert}</div>
        <div class="alert alert-light border">生成范围：{filter_summary}；服务期：{service_range}</div>
        <div class="row text-center g-2 mb-3">
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">涉及房间</div><strong>{len(room_keys)}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">收费项目 / 将生成账单</div><strong>{len(plan['items'])}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">跳过重复</div><strong>{plan['skipped']}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">金额合计</div><strong>¥{m(sum(x['amount'] for x in plan['items']))}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">合同期外跳过</div><strong>{plan.get('inactive', 0)}</strong></div></div>
        </div>
        <div class="row g-3">
        <div class="col-md-6"><div class="card"><div class="card-header">按收费项目汇总</div><table class="table table-sm mb-0">{fee_rows}</table></div></div>
        <div class="col-md-6"><div class="card"><div class="card-header">按房间类别汇总</div><table class="table table-sm mb-0">{cat_rows}</table></div></div>
        </div>
        <div class="card mt-3"><div class="card-header">前 50 条账单明细</div><div class="table-responsive">
        <table class="table table-sm mb-0"><thead><tr><th>房间</th><th>类别</th><th>收费项目</th><th>公式</th><th class="text-end">金额</th></tr></thead><tbody>{detail_rows}</tbody></table></div></div>
        {warning_html}
        <form method="POST" action="/bills/generate" class="mt-3">
            <input type="hidden" name="mode" value="confirm">
            {reviewed}
            <input type="hidden" name="period" value="{h(period)}">
            <input type="hidden" name="period_start" value="{h(period_start)}">
            <input type="hidden" name="period_end" value="{h(period_end)}">
            <input type="hidden" name="due_day" value="{due_day}">
            <input type="hidden" name="fee_type_ids" value="{h(ids)}">
            {hidden_filters}
            <button class="btn btn-success btn-lg">{confirm_label}</button>
            <a href="/bills/generate" class="btn btn-outline-secondary btn-lg">返回修改</a>
        </form>
        ''', 'bills'))

    def _render_bill_generation_result(self, period, generated_count, plan, filters=None, backup_name='', period_start='', period_end='', use_range_links=True):
        filters = filters or {}
        total = sum(x['amount'] for x in plan['items'])
        detail_rows = ''.join(
            f'<tr><td><a href="/bills/{x["bill_id"]}">{h(x["bill_number"])}</a></td>'
            f'<td>{h(x["building"])}-{h(x["room_number"])}</td><td>{h(x["category"])}</td>'
            f'<td>{h(x["fee_name"])}</td><td>{h(x["formula"])}</td><td class="text-end">¥{m(x["amount"])}</td>'
            f'<td><a class="btn btn-sm btn-outline-warning" href="/bills/{x["bill_id"]}/edit">直接修正</a></td></tr>'
            for x in plan['items'][:100]
        )
        if not detail_rows:
            detail_rows = '<tr><td colspan="7" class="text-center text-muted py-3">本次没有新生成账单</td></tr>'
        warning_html = self._render_bill_generation_warnings(plan['items'])
        backup_html = ''
        if backup_name:
            backup_html = f'''<div class="alert alert-light border"><strong>自动备份：</strong><code>{h(backup_name)}</code>
            <form method="POST" action="/backups/{h(backup_name)}/restore" class="d-inline ms-2" onsubmit="return confirm('恢复会覆盖当前数据，确定恢复到生成账单前？')"><button class="btn btn-sm btn-outline-warning">恢复到生成前</button></form></div>'''
        export_ids = ','.join(str(x['bill_id']) for x in plan['items'])
        export_html = ''
        undo_html = ''
        if export_ids:
            export_html = f'<a class="btn btn-outline-success" href="/bills/export_generated?ids={h(export_ids)}"><i class="bi bi-download"></i> 导出本次生成CSV</a>'
            undo_html = f'''<form method="POST" action="/bills/undo_generated" class="d-inline" onsubmit="return confirm('只会删除未缴费账单；已有缴费记录的账单会跳过。确定撤销本次生成？')">
                <input type="hidden" name="period" value="{h(period)}">
                <input type="hidden" name="bill_ids" value="{h(export_ids)}">
                <button class="btn btn-outline-danger">撤销本次生成</button>
            </form>'''
        more = ''
        if len(plan['items']) > 100:
            more = '<p class="small text-muted">仅显示前 100 条，请到账单列表继续查看。</p>'
        range_query = f'period_start={h(period_start)}&amp;period_end={h(period_end)}' if use_range_links and period_start and period_end else f'period={h(period)}'
        self._html(self._page('账单生成结果', f"""
        <div class="alert alert-success"><strong>账单生成结果</strong>：本次生成完成，请核对明细后再进入收费。</div>
        {backup_html}
        <div class="alert alert-light border">生成范围：{self._bill_filter_summary(filters)}；服务期：{h(period_start)} 至 {h(period_end)}</div>
        <div class="row text-center g-2 mb-3">
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">本次生成账单</div><strong>{generated_count}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">跳过重复</div><strong>{plan['skipped']}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">合同期外跳过</div><strong>{plan.get('inactive', 0)}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">金额合计</div><strong>¥{m(total)}</strong></div></div>
        </div>
        <div class="card"><div class="card-header">本次生成账单明细</div><div class="table-responsive">
        <table class="table table-sm mb-0"><thead><tr><th>账单编号</th><th>房间</th><th>类别</th><th>收费项目</th><th>公式</th><th class="text-end">金额</th><th>修正</th></tr></thead><tbody>{detail_rows}</tbody></table>
        </div></div>{more}
        {warning_html}
        <div class="mt-3 d-flex gap-2">
            <a class="btn btn-primary" href="/bills/review?{range_query}">去核对工作台</a>
            <a class="btn btn-outline-primary" href="/bills?{range_query}">查看账单列表</a>
            {export_html}
            {undo_html}
            <a class="btn btn-outline-secondary" href="/bills/generate">继续生成</a>
        </div>
        """, 'bills'))
