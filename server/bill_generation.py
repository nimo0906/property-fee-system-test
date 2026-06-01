#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill generation — grouped by fee type category."""

from server.db import get_db, get_period, is_period_closed, h, m, qs, room_active_in_period, date_to_period, period_to_date, add_months
from server.base import BaseHandler
from server.billing_engine import calculate_bill_amount, fee_applies_to_category, fee_applies_to_room
from server.backups import create_db_backup
from datetime import timedelta


def _cycle_month_count(cycle):
    return {'monthly': 1, 'quarterly': 3, 'semiannual': 6}.get(str(cycle or '').strip(), 1)


def _room_billing_months(room):
    try:
        if room['unit'] == '商场' and room['category'] in ('商户', '商业'):
            return _cycle_month_count(room['payment_cycle'])
    except Exception:
        pass
    return 1


def _cycle_period_label(period, months):
    months = max(1, int(months or 1))
    if months == 1:
        return period
    try:
        y, mo = [int(x) for x in period[:7].split('-')]
        end = add_months(__import__('datetime').date(y, mo, 1), months - 1)
        return f"{y}-{mo:02d}~{end.year}-{end.month:02d}"
    except Exception:
        return period


def _cycle_due_date(period, fallback_due):
    if '~' not in period:
        return fallback_due
    try:
        y, mo = [int(x) for x in period.split('~')[-1].split('-')]
        return (add_months(__import__('datetime').date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
    except Exception:
        return fallback_due


class BillGenerationMixin(BaseHandler):

    def _bill_gen(self, q=None):
        q = q or {}
        db = get_db()
        mode = qs(q, 'mode')
        fts = db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order").fetchall()
        buildings = db.execute("SELECT DISTINCT building FROM rooms ORDER BY building").fetchall()
        categories = db.execute("SELECT DISTINCT category FROM rooms WHERE category IS NOT NULL AND category<>'' ORDER BY category").fetchall()
        db.close()
        cm_labels = {'area': '按面积', 'meter': '按用量', 'floor': '电梯阶梯', 'fixed': '固定金额', 'household': '按户'}

        # 分组：基础物业费（居民+商户） vs 增值商业服务费
        groups = {'基础物业收费项目': [], '增值商业收费项目': []}
        for f in fts:
            if f['sort_order'] >= 30:
                groups['增值商业收费项目'].append(f)
            else:
                groups['基础物业收费项目'].append(f)

        group_html = ''
        for gname, gfts in groups.items():
            if not gfts:
                continue
            items = ''.join(
                f'''<div class="col-md-4"><div class="form-check card p-3 border">
                <input type="checkbox" name="fee_type_ids" value="{f["id"]}" class="form-check-input" id="ft{f["id"]}"
                    {"checked" if f["calc_method"] != "meter" else ""}>
                <label class="form-check-label" for="ft{f["id"]}"><strong>{h(f["name"])}</strong><br>
                <small class="text-muted">{cm_labels.get(f["calc_method"], f["calc_method"])} {m(f["unit_price"])}{h(f["unit"] or "")}</small></label></div></div>'''
                for f in gfts
            )
            group_html += f'''<div class="card mb-3"><div class="card-header py-2">{gname}</div>
            <div class="card-body"><div class="row g-2">{items}</div></div></div>'''

        selected_building = qs(q, 'building')
        selected_category = qs(q, 'category')
        selected_room_from = qs(q, 'room_from')
        selected_room_to = qs(q, 'room_to')
        default_unit = '商场' if mode == 'commercial' else ''
        building_opts = '<option value="">全部楼栋</option>' + ''.join(
            f'<option value="{h(x["building"])}"{" selected" if selected_building == x["building"] else ""}>{h(x["building"])}</option>'
            for x in buildings
        )
        category_opts = '<option value="">全部类别</option>' + ''.join(
            f'<option value="{h(x["category"])}"{" selected" if selected_category == x["category"] else ""}>{h(x["category"])}</option>'
            for x in categories
        )
        self._html(self._page('生成账单', f'''
        <div class="alert alert-info"><i class="bi bi-info-circle"></i>
        选择账期、房间范围和费用类型，系统只为筛选范围内的房间生成独立账单。
        商业模式仅纳入单元/区域为商场且类型为商户/商业的对象；请先核对面积、物业费单价和缴费周期。</div>
        <form method=POST action="/bills/generate" class="row g-3">
        <input type="hidden" name="mode_scope" value="{h(mode)}">
        <input type="hidden" name="unit" value="{h(default_unit)}">
        <div class="col-md-3"><label>账期 *</label>
        <input type="date" name="period" class="form-control" value="{period_to_date(get_period())}" required><small class="text-muted">按所选日期所在月份生成账单</small></div>
        <div class="col-md-3"><label>截止日(每月)</label>
        <input type="number" name="due_day" class="form-control" value="28" min="1" max="28"></div>
        <div class="col-md-3"><label>楼栋范围</label><select name="building" class="form-select">{building_opts}</select></div>
        <div class="col-md-3"><label>房间类别</label><select name="category" class="form-select">{category_opts}</select></div>
        <div class="col-md-3"><label>起始房号</label><input name="room_from" class="form-control" value="{h(selected_room_from)}" placeholder="如 701，可留空"></div>
        <div class="col-md-3"><label>结束房号</label><input name="room_to" class="form-control" value="{h(selected_room_to)}" placeholder="如 2608，可留空"></div>
        <div class="col-md-6 d-flex align-items-end text-muted small">不填筛选条件时仍按全部房间处理；建议先预览，再确认生成。</div>
        <div class="col-12">{group_html}</div>
        <div class="col-12"><hr>
        <button name="mode" value="preview" class="btn btn-primary btn-lg"><i class="bi bi-eye"></i> 预览生成结果</button>
        <button name="mode" value="confirm" class="btn btn-success btn-lg"><i class="bi bi-file-earmark-plus"></i> 直接生成账单</button>
        <a href="/bills" class="btn btn-outline-secondary">返回</a></div></form>''', 'bills'))

    def _bill_generate(self, d):
        period = date_to_period(qs(d, 'period'))
        if is_period_closed(period):
            return self._redirect('/bills/generate?flash=' + period + '已结账，无法生成新账单')
        db = get_db()
        due_day = int(qs(d, 'due_day', '28'))
        if due_day < 1 or due_day > 28:
            due_day = 28
        parts = period.split('-')
        due_date = f"{parts[0]}-{parts[1]}-{due_day:02d}"
        ft_ids = self._parse_fee_type_ids(d)
        if not ft_ids:
            db.close()
            return self._redirect('/bills/generate?flash=请选择费用类型')
        filters = self._parse_bill_generation_filters(d)
        rooms = self._query_bill_generation_rooms(db, filters)
        if not rooms:
            db.close()
            return self._bill_generation_no_rooms()
        plan = self._build_bill_generation_plan(db, period, due_date, ft_ids, filters)
        if qs(d, 'mode') == 'preview':
            db.close()
            return self._render_bill_generation_preview(period, due_day, ft_ids, plan, filters)
        backup_name = create_db_backup('auto_before_bill_generation')
        g = 0
        generated_items = []
        existing = set(plan['existing_keys'])
        owners_map = plan['owners_map']
        for rm in rooms:
            room_plan = [x for x in plan['items'] if x['room_id'] == rm['id']]
            if not room_plan:
                continue
            for fid in ft_ids:
                item = next((x for x in room_plan if x['fee_type_id'] == fid), None)
                item_period = item.get('billing_period', period) if item else period
                key = f"{rm['id']}:{fid}:{item_period}"
                if key in existing:
                    continue
                if not item:
                    continue
                amt = item['amount']
                oname = (owners_map.get(rm['owner_id']) or '未知')[:10]
                rshort = rm['building'] + '-' + rm['room_number']
                seq = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period=?", (item_period,)).fetchone()[0] + g + 1
                bn = f"{rshort}_{oname}_{item_period.replace('~','-')}_{seq:04d}"
                cur = db.execute(
                    "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,'unpaid',?)",
                    (rm['id'], rm['owner_id'], fid, item_period, amt, _cycle_due_date(item_period, due_date), bn)
                )
                generated = dict(item)
                generated['bill_id'] = cur.lastrowid
                generated['bill_number'] = bn
                generated['owner_id'] = rm['owner_id']
                generated['area'] = rm['area']
                generated['calc_method'] = item.get('calc_method')
                generated_items.append(generated)
                g += 1
        db.commit()
        db.close()
        result_plan = dict(plan)
        result_plan['items'] = generated_items
        return self._render_bill_generation_result(period, g, result_plan, filters, backup_name)


    def _bill_generation_no_rooms(self):
        self._html(self._page('生成账单', '''
        <div class="card border-warning">
            <div class="card-header text-warning"><i class="bi bi-exclamation-triangle"></i> 生成账单前需要先导入房间资料</div>
            <div class="card-body">
                <p>系统没有找到可出账房间。请先准备楼栋、房号、楼层、面积、业主、合同日期等基础资料。</p>
                <div class="d-flex gap-2 flex-wrap">
                    <a class="btn btn-outline-primary" href="/import/template/basic.csv" download="basic_info_template.csv">下载基础资料模板</a>
                    <a class="btn btn-primary" href="/import">导入基础资料</a>
                    <a class="btn btn-outline-secondary" href="/rooms/create">手动添加房间</a>
                </div>
            </div>
        </div>
        ''', 'bills'))

    def _parse_bill_generation_filters(self, d):
        return {
            'building': qs(d, 'building').strip(),
            'category': qs(d, 'category').strip(),
            'room_from': qs(d, 'room_from').strip(),
            'room_to': qs(d, 'room_to').strip(),
            'unit': qs(d, 'unit').strip(),
            'mode_scope': qs(d, 'mode_scope').strip(),
        }

    def _parse_fee_type_ids(self, d):
        raw_ft = d.get('fee_type_ids', [])
        if isinstance(raw_ft, list):
            all_ids = []
            for item in raw_ft:
                all_ids.extend(x.strip() for x in item.split(',') if x.strip())
            return [int(x) for x in all_ids]
        return [int(x) for x in raw_ft.split(',') if x]

    def _build_bill_generation_plan(self, db, period, due_date, ft_ids, filters=None):
        filters = filters or {}
        rooms = [r for r in self._query_bill_generation_rooms(db, filters) if room_active_in_period(r, period)]
        fts_map = {f['id']: f for f in db.execute("SELECT * FROM fee_types WHERE is_active=1").fetchall()}
        owners_map = {o['id']: o['name'] for o in db.execute("SELECT id,name FROM owners").fetchall()}
        owners_map[None] = '未知'
        existing = {row[0] for row in db.execute(
            "SELECT DISTINCT room_id || ':' || fee_type_id || ':' || billing_period FROM bills"
        ).fetchall()}
        items = []
        skipped = 0
        for rm in rooms:
            rcat = rm['category'] or '居民'
            for fid in ft_ids:
                ft = fts_map.get(fid)
                if not ft or not fee_applies_to_room(ft['name'] or '', rm):
                    continue
                bill_months = _room_billing_months(rm)
                bill_period = _cycle_period_label(period, bill_months)
                key = f"{rm['id']}:{fid}:{bill_period}"
                if key in existing:
                    skipped += 1
                    continue
                calc = calculate_bill_amount(db, rm, ft, bill_period, bill_months)
                amt = calc['amount']
                formula = calc['formula']
                if amt <= 0:
                    continue
                items.append({
                    'room_id': rm['id'], 'fee_type_id': fid, 'amount': amt, 'formula': formula, 'billing_period': bill_period, 'months': bill_months,
                    'building': rm['building'], 'room_number': rm['room_number'],
                    'category': rcat, 'fee_name': ft['name'], 'calc_method': ft['calc_method'],
                })
        inactive = len(self._query_bill_generation_rooms(db, filters)) - len(rooms)
        return {'items': items, 'skipped': skipped, 'inactive': inactive, 'existing_keys': existing, 'owners_map': owners_map, 'rooms': rooms}

    def _query_bill_generation_rooms(self, db, filters):
        sql = "SELECT * FROM rooms"
        cond = []
        vals = []
        if filters.get('building'):
            cond.append("building=?")
            vals.append(filters['building'])
        if filters.get('category'):
            cond.append("category=?")
            vals.append(filters['category'])
        if filters.get('unit'):
            cond.append("unit=?")
            vals.append(filters['unit'])
        if filters.get('mode_scope') == 'commercial':
            cond.append("unit='商场'")
            cond.append("category IN ('商户','商业')")
        if filters.get('room_from'):
            cond.append("room_number>=?")
            vals.append(filters['room_from'])
        if filters.get('room_to'):
            cond.append("room_number<=?")
            vals.append(filters['room_to'])
        if cond:
            sql += " WHERE " + " AND ".join(cond)
        sql += " ORDER BY building,unit,room_number"
        return db.execute(sql, vals).fetchall()

    def _render_bill_generation_preview(self, period, due_day, ft_ids, plan, filters=None):
        filters = filters or {}
        fee_totals = {}
        category_totals = {}
        for item in plan['items']:
            fee_totals[item['fee_name']] = fee_totals.get(item['fee_name'], 0) + item['amount']
            category_totals[item['category']] = category_totals.get(item['category'], 0) + item['amount']
        fee_rows = ''.join(f'<tr><td>{h(k)}</td><td class="text-end">¥{m(v)}</td></tr>' for k, v in fee_totals.items())
        cat_rows = ''.join(f'<tr><td>{h(k)}</td><td class="text-end">¥{m(v)}</td></tr>' for k, v in category_totals.items())
        detail_rows = ''.join(
            f'<tr><td>{h(x["building"])}-{h(x["room_number"])}</td><td>{h(x["category"])}</td><td>{h(x["fee_name"])}</td><td>{h(x["formula"])}</td><td class="text-end">¥{m(x["amount"])}</td></tr>'
            for x in plan['items'][:50]
        )
        ids = ','.join(str(x) for x in ft_ids)
        filter_summary = self._bill_filter_summary(filters)
        hidden_filters = ''.join(
            f'<input type="hidden" name="{h(k)}" value="{h(v)}">'
            for k, v in filters.items() if v
        )
        self._html(self._page('生成账单预览', f'''
        <div class="alert alert-warning"><strong>生成账单预览</strong>：当前页面只预览，不写入账单。确认后才会生成。</div>
        <div class="alert alert-light border">生成范围：{filter_summary}</div>
        <div class="row text-center g-2 mb-3">
        <div class="col-md-4"><div class="border rounded p-3"><div class="text-muted small">将生成账单</div><strong>{len(plan['items'])}</strong></div></div>
        <div class="col-md-4"><div class="border rounded p-3"><div class="text-muted small">跳过重复</div><strong>{plan['skipped']}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">金额合计</div><strong>¥{m(sum(x['amount'] for x in plan['items']))}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">合同期外跳过</div><strong>{plan.get('inactive', 0)}</strong></div></div>
        </div>
        <div class="row g-3">
        <div class="col-md-6"><div class="card"><div class="card-header">按收费项目汇总</div><table class="table table-sm mb-0">{fee_rows}</table></div></div>
        <div class="col-md-6"><div class="card"><div class="card-header">按房间类别汇总</div><table class="table table-sm mb-0">{cat_rows}</table></div></div>
        </div>
        <div class="card mt-3"><div class="card-header">前 50 条账单明细</div><div class="table-responsive">
        <table class="table table-sm mb-0"><thead><tr><th>房间</th><th>类别</th><th>收费项目</th><th>公式</th><th class="text-end">金额</th></tr></thead><tbody>{detail_rows}</tbody></table></div></div>
        <form method="POST" action="/bills/generate" class="mt-3">
            <input type="hidden" name="mode" value="confirm">
            <input type="hidden" name="period" value="{h(period)}">
            <input type="hidden" name="due_day" value="{due_day}">
            <input type="hidden" name="fee_type_ids" value="{h(ids)}">
            {hidden_filters}
            <button class="btn btn-success btn-lg">确认生成账单</button>
            <a href="/bills/generate" class="btn btn-outline-secondary btn-lg">返回修改</a>
        </form>
        ''', 'bills'))


    def _render_bill_generation_result(self, period, generated_count, plan, filters=None, backup_name=''):
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
        self._html(self._page('账单生成结果', f"""
        <div class="alert alert-success"><strong>账单生成结果</strong>：本次生成完成，请核对明细后再进入收费。</div>
        {backup_html}
        <div class="alert alert-light border">生成范围：{self._bill_filter_summary(filters)}</div>
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
            <a class="btn btn-primary" href="/bills/review?period={h(period)}">去核对工作台</a>
            <a class="btn btn-outline-primary" href="/bills?period={h(period)}">查看账单列表</a>
            {export_html}
            {undo_html}
            <a class="btn btn-outline-secondary" href="/bills/generate">继续生成</a>
        </div>
        """, 'bills'))

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
