from server.bill_generation_shared import *

class BillGenerationMixinPart2Group2(BaseHandler):
    def _bill_undo_generated(self, d):
        raw = qs(d, 'bill_ids')
        ids = [x for x in raw.split(',') if x.strip().isdigit()]
        period = date_to_period(qs(d, 'period'))
        if not ids:
            return self._redirect('/bills?flash=缺少要撤销的账单')
        if is_period_closed(period):
            return self._redirect('/bills?flash=' + period + '已结账，无法撤销生成账单')
        db = get_db()
        deleted = 0
        skipped = []
        try:
            for bid in ids:
                bill = db.execute("SELECT * FROM bills WHERE id=?", (bid,)).fetchone()
                if not bill:
                    skipped.append((bid, '账单不存在'))
                    continue
                paid = db.execute("SELECT COUNT(*) FROM payments WHERE bill_id=?", (bid,)).fetchone()[0]
                if paid > 0 or bill['status'] in ('paid', 'partial'):
                    skipped.append((bid, '已有缴费记录'))
                    continue
                db.execute("DELETE FROM bills WHERE id=?", (bid,))
                deleted += 1
            db.commit()
        finally:
            db.close()
        return self._render_bill_undo_result(period, deleted, skipped)

    def _render_bill_undo_result(self, period, deleted, skipped):
        skip_rows = ''.join(
            f'<tr><td>{h(bid)}</td><td>{h(reason)}</td></tr>' for bid, reason in skipped
        ) or '<tr><td colspan="2" class="text-muted text-center">无</td></tr>'
        self._html(self._page('撤销生成结果', f'''
        <div class="alert alert-info"><strong>撤销生成结果</strong>：已处理本次生成账单撤销请求。</div>
        <div class="row text-center g-2 mb-3">
        <div class="col-md-6"><div class="border rounded p-3"><div class="text-muted small">删除账单</div><strong>{deleted}</strong></div></div>
        <div class="col-md-6"><div class="border rounded p-3"><div class="text-muted small">跳过账单</div><strong>{len(skipped)}</strong></div></div>
        </div>
        <div class="card"><div class="card-header">跳过原因</div>
        <table class="table table-sm mb-0"><thead><tr><th>账单ID</th><th>原因</th></tr></thead><tbody>{skip_rows}</tbody></table></div>
        <div class="mt-3 d-flex gap-2">
            <a class="btn btn-primary" href="/bills?period={h(period)}">返回账单列表</a>
            <a class="btn btn-outline-secondary" href="/bills/generate">重新生成</a>
        </div>
        ''', 'bills'))

    def _render_bill_generation_warnings(self, items):
        warnings = []
        for x in items:
            room = f'{x.get("building")}-{x.get("room_number")}'
            if not x.get('owner_id'):
                warnings.append((room, x.get('fee_name'), '无业主'))
            try:
                if float(x.get('area') or 0) <= 0:
                    warnings.append((room, x.get('fee_name'), '面积为0'))
            except (TypeError, ValueError):
                warnings.append((room, x.get('fee_name'), '面积异常'))
            if x.get('calc_method') == 'meter' and x.get('amount', 0) <= 0:
                warnings.append((room, x.get('fee_name'), '抄表类无读数或金额为0'))
        if not warnings:
            return """
        <div class="card mt-3"><div class="card-header">异常核对清单</div>
        <div class="card-body text-muted">未发现明显异常。仍建议人工核对金额后收费。</div></div>"""
        rows = ''.join(
            f'<tr><td>{h(room)}</td><td>{h(fee)}</td><td><span class="badge bg-warning text-dark">{h(reason)}</span></td></tr>'
            for room, fee, reason in warnings[:100]
        )
        return f"""
        <div class="card mt-3 border-warning"><div class="card-header text-warning">异常核对清单</div>
        <div class="card-body"><p class="small text-muted">这些项目不一定是错误，但收费前必须人工确认。</p>
        <table class="table table-sm mb-0"><thead><tr><th>房间</th><th>收费项目</th><th>提示</th></tr></thead><tbody>{rows}</tbody></table>
        </div></div>"""

    def _bill_filter_summary(self, filters):
        parts = []
        if filters.get('building'):
            parts.append('楼栋 ' + h(filters['building']))
        if filters.get('category'):
            parts.append('类别 ' + h(filters['category']))
        if filters.get('room_from') or filters.get('room_to'):
            parts.append('房号 ' + h(filters.get('room_from') or '最小') + ' 至 ' + h(filters.get('room_to') or '最大'))
        return '；'.join(parts) if parts else '全部房间'
