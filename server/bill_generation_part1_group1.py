from server.bill_generation_shared import *
from server.bill_snapshots import room_snapshot, apply_snapshot
from server.data_health import cleanup_invalid_payments

class BillGenerationMixinPart1Group1(BaseHandler):
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
        default_start, default_end, _, _ = _resolve_generation_period(q)
        default_unit = ''
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
        选择起始日期、截止日期、房间范围和费用类型，系统按财务自然日期范围生成账单。
        商业模式纳入房间类型为商户/商业的对象，不限定楼栋或单元/分区；请先核对面积、物业费单价和缴费周期。</div>
        <form method=POST action="/bills/generate" class="row g-3">
        <input type="hidden" name="mode_scope" value="{h(mode)}">
        <input type="hidden" name="unit" value="{h(default_unit)}">
        <div class="col-md-3"><label>起始日期 *</label>
        <input type="date" name="period_start" class="form-control" value="{h(default_start)}" required><small class="text-muted">财务做账起始日</small></div>
        <div class="col-md-3"><label>截止日期 *</label>
        <input type="date" name="period_end" class="form-control" value="{h(default_end)}" required><small class="text-muted">财务做账截止日，同时作为默认缴费截止日</small></div>
        <div class="col-md-3"><label>楼栋范围</label><select name="building" class="form-select">{building_opts}</select></div>
        <div class="col-md-3"><label>房间类别</label><select name="category" class="form-select">{category_opts}</select></div>
        <div class="col-md-3"><label>起始房号</label><input name="room_from" class="form-control" value="{h(selected_room_from)}" placeholder="如 701，可留空"></div>
        <div class="col-md-3"><label>结束房号</label><input name="room_to" class="form-control" value="{h(selected_room_to)}" placeholder="如 2608，可留空"></div>
        <div class="col-md-6 d-flex align-items-end text-muted small">不填筛选条件时仍按全部房间处理；建议先预览，再确认生成。</div>
        <div class="col-12">{group_html}</div>
        <div class="col-12"><hr>
        <button name="mode" value="preview" class="btn btn-primary btn-lg"><i class="bi bi-eye"></i> 预览生成结果</button>
        <button name="mode" value="confirm_review" class="btn btn-success btn-lg"><i class="bi bi-shield-check"></i> 生成前核对</button>
        <a href="/bills" class="btn btn-outline-secondary">返回</a></div></form>''', 'bills'))

    def _bill_generate(self, d):
        legacy_period_input = bool(qs(d, 'period', '').strip() and not qs(d, 'period_start', '').strip() and not qs(d, 'period_end', '').strip())
        period_start, period_end, period, month_count = _resolve_generation_period(d)
        if is_period_closed(period):
            return self._redirect('/bills/generate?flash=' + period + '已结账，无法生成新账单')
        db = get_db()
        due_day = int(qs(d, 'due_day', '28') or '28')
        if due_day < 1 or due_day > 28:
            due_day = 28
        due_date = f"{period[:4]}-{period[5:7]}-{due_day:02d}" if legacy_period_input and '~' not in period else period_end
        ft_ids = self._parse_fee_type_ids(d)
        if not ft_ids:
            db.close()
            return self._redirect('/bills/generate?flash=请选择费用类型')
        filters = self._parse_bill_generation_filters(d)
        rooms = self._query_bill_generation_rooms(db, filters)
        if not rooms:
            db.close()
            return self._bill_generation_no_rooms()
        plan = self._build_bill_generation_plan(db, period, due_date, ft_ids, filters, period_start, period_end, month_count)
        mode = qs(d, 'mode')
        if mode == 'preview':
            db.close()
            return self._render_bill_generation_preview(period, due_day, ft_ids, plan, filters, period_start, period_end)
        if mode == 'confirm_review':
            db.close()
            return self._render_bill_generation_preview(period, due_day, ft_ids, plan, filters, period_start, period_end, precheck=True)
        backup_name = create_db_backup('auto_before_bill_generation')
        cleanup_invalid_payments(db)
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
                    "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end) VALUES(?,?,?,?,?,?,'unpaid',?,?,?)",
                    (rm['id'], rm['owner_id'], fid, item_period, amt, item.get('due_date', due_date), bn, item.get('service_start', period_start), item.get('service_end', period_end))
                )
                apply_snapshot(db, cur.lastrowid, room_snapshot(db, rm['id'], rm['owner_id']))
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
        return self._render_bill_generation_result(period, g, result_plan, filters, backup_name, period_start, period_end, not legacy_period_input)

    def _bill_generation_no_rooms(self):
        self._html(self._page('生成账单', '''
        <div class="card border-warning">
            <div class="card-header text-warning"><i class="bi bi-exclamation-triangle"></i> 生成账单前需要先导入收费对象资料</div>
            <div class="card-body">
                <p>系统没有找到可出账收费对象。请先准备项目、楼栋/区域、单元/分区、房号/铺位号、楼层、面积、客户、合同日期等基础资料。</p>
                <div class="d-flex gap-2 flex-wrap">
                    <a class="btn btn-outline-primary" href="/import/template/basic.xlsx" download="basic_info_template.xlsx">下载基础资料模板</a>
                    <a class="btn btn-primary" href="/import">导入基础资料</a>
                    <a class="btn btn-outline-secondary" href="/rooms/create">手动添加收费对象</a>
                </div>
            </div>
        </div>
        ''', 'bills'))
