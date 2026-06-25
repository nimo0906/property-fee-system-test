from server.merchant_contracts_shared import *
from server.special_rent import upsert_special_rent_rule
from server.pagination import business_area_order_sql, pagination_state, query_items, render_pagination

class MerchantContractMixinPart1Group1(BaseHandler):
    def _merchant_contracts(self, q):
        keyword = qs(q, 'keyword').strip()
        db = get_db()
        sql = """SELECT c.*,COALESCE(r.building,'商场') building,COALESCE(r.unit,'商场') unit,
                      COALESCE(s.space_no,r.room_number) room_number,COALESCE(NULLIF(c.contract_area,0),s.area,r.area,0) area,
                      COALESCE(s.shop_name,c.shop_name,r.shop_name) space_shop_name,
                      COALESCE(s.merchant_name,c.merchant_name) space_merchant_name,
                      COALESCE(s.business_type,'-') business_type,COALESCE(s.water_rate_type,'非居民') water_rate_type,
                      COALESCE(s.floor,r.floor) floor,o.name owner_name,
                      (SELECT COUNT(*) FROM bills b
                       WHERE b.source='merchant_contract' AND b.source_ref=CAST(c.id AS TEXT)) bill_count,
                      (SELECT COUNT(*) FROM bills b
                       WHERE b.source='merchant_contract' AND b.source_ref=CAST(c.id AS TEXT)
                         AND b.status IN('unpaid','overdue','partial')) unpaid_count,
                      (SELECT MIN(b.service_start) FROM bills b
                       WHERE b.source='merchant_contract' AND b.source_ref=CAST(c.id AS TEXT)) service_start_min,
                      (SELECT MAX(b.service_end) FROM bills b
                       WHERE b.source='merchant_contract' AND b.source_ref=CAST(c.id AS TEXT)) service_end_max
               FROM merchant_contracts c
               LEFT JOIN rooms r ON c.room_id=r.id
               LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
               LEFT JOIN owners o ON c.owner_id=o.id
               """
        vals = []
        if keyword:
            like = f'%{keyword}%'
            sql += """ WHERE (
                c.contract_no LIKE ? OR c.merchant_name LIKE ? OR c.shop_name LIKE ?
                OR s.space_no LIKE ? OR s.shop_name LIKE ? OR s.merchant_name LIKE ?
                OR s.business_type LIKE ? OR r.room_number LIKE ? OR r.building LIKE ? OR r.unit LIKE ?
                OR o.name LIKE ?
            )"""
            vals.extend([like] * 11)
        total_rows = db.execute("SELECT COUNT(*) FROM (" + sql + ")", vals).fetchone()[0]
        pg, per_page, total_pages = pagination_state(q, total_rows)
        area_order = business_area_order_sql("COALESCE(r.building,'商场')", "COALESCE(r.unit,'商场')")
        order_sql = f" ORDER BY {area_order}, CAST(COALESCE(s.floor,r.floor,0) AS REAL) ASC, COALESCE(s.space_no,r.room_number) ASC, c.end_date ASC, c.id DESC"
        rows = db.execute(sql + order_sql + " LIMIT ? OFFSET ?", vals + [per_page, (pg - 1) * per_page]).fetchall()
        db.close()

        def row_html(r):
            status_class = 'status-success' if r['status'] == 'active' else 'status-neutral'
            return f'''<tr>
            <td><strong>{h(r['room_number'])}</strong><div class="small text-muted">合同 {h(r['contract_no'])}</div></td>
            <td><strong>{h(r['space_shop_name'] or r['shop_name'] or '-')}</strong><div class="small text-muted">{h(r['space_merchant_name'] or r['merchant_name'] or r['owner_name'] or '-')} · {h(r['business_type'])}</div></td>
            <td>{h(str(r['floor']) + 'F' if r['floor'] is not None else r['unit'])}<div class="small text-muted">合同面积 {n(r['contract_area'] or r['area'])}㎡ · 建筑面积 {n(r['building_area'] or r['area'])}㎡ · 水费 {h(r['water_rate_type'])}</div></td>
            <td class="text-end">{n(_rent_unit_price(r['rent_amount'], r['area']))} 元/m²<div class="small text-muted">{h(CYCLE_LABELS.get(r['rent_cycle'], r['rent_cycle']))}</div></td>
            <td class="text-end">{n(r['property_rate'])} 元/m²<div class="small text-muted">{h(CYCLE_LABELS.get(r['property_cycle'], r['property_cycle']))}</div></td>
            <td class="text-end">{n(_deposit_unit_price(r['deposit_amount'], r['area']))} 元/m²</td>
            <td>{h(r['start_date'])} 至 {h(r['end_date'])}</td>
            <td>{_contract_billing_badges(r)}</td>
            <td>{_contract_service_period(r)}<div>{_contract_expiry_badge(r['end_date'])}</div></td>
            <td><span class="badge {status_class}">{h(contract_status_label(r['status']))}</span></td>
            <td class="text-end">
              <a class="btn btn-sm btn-outline-secondary" href="/merchant_contracts/{r['id']}">详情</a>
              <a class="btn btn-sm btn-outline-primary" href="/merchant_contracts/{r['id']}/edit">编辑</a>
              <a class="btn btn-sm btn-outline-warning" href="/merchant_contracts/{r['id']}/transfer">转租登记</a>
              <form method="POST" action="/merchant_contracts/{r['id']}/delete" class="d-inline" onsubmit="return confirm('确认删除该合同档案？已有合同账单的档案不能删除。');"><button class="btn btn-sm btn-outline-danger">删除</button></form>
            </td>
            </tr>'''

        b_rows = [r for r in rows if str(r['building'] or '').startswith('B') or str(r['unit'] or '').startswith('B')]
        commercial_rows = [r for r in rows if r not in b_rows]
        search_tip = f'搜索结果：{total_rows} 份合同档案' if keyword else '默认按楼层从低到高排序'
        headers = '<thead><tr><th>空间/合同</th><th>店铺/使用方</th><th>楼层/面积</th><th class="text-end">租金单价</th><th class="text-end">物业单价</th><th class="text-end">押金单价</th><th>合同期</th><th>出账状态</th><th>最近服务期/到期提醒</th><th>状态</th><th class="text-end">操作</th></tr></thead>'

        def group(title, icon, items, open_attr):
            body = ''.join(row_html(r) for r in items) or '<tr><td colspan="11" class="text-center text-muted py-4">暂无合同档案</td></tr>'
            return f'''<details class="contract-group" {open_attr}>
              <summary><span><i class="bi {icon}"></i> {title}</span><span class="badge status-info">{len(items)} 份</span></summary>
              <div class="table-responsive"><table class="table table-hover align-middle mb-0">{headers}<tbody>{body}</tbody></table></div>
            </details>'''

        self._html(self._page("空间合同档案", f'''
        <div class="alert alert-info"><i class="bi bi-file-earmark-text"></i>
        合同档案按 物业合同 / 商业合同 分组；作为行政档案/合同备查使用，不局限于商场；空间资料和合同资料在同一份档案中维护。日常收费仍从“物业收费”或“商业收费”生成账单。</div>
        <div class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span><i class="bi bi-file-earmark-text"></i> 空间合同档案</span>
            <div class="d-flex flex-wrap gap-2">
              <a class="btn btn-primary btn-sm" href="/merchant_contracts/create"><i class="bi bi-plus-lg"></i> 新增合同档案</a>
            </div>
          </div>
          <div class="card-body border-bottom">
            <form method="GET" action="/merchant_contracts" class="row g-2 align-items-end">
              <div class="col-md-8"><label class="form-label">搜索合同档案</label><input name="keyword" class="form-control" value="{h(keyword)}" placeholder="输入商户编号、合同编号、店铺/使用方、业态、楼层"></div>
              <div class="col-md-4 d-flex gap-2"><button class="btn btn-primary flex-fill"><i class="bi bi-search"></i> 搜索</button><a class="btn btn-outline-secondary" href="/merchant_contracts">重置</a></div>
              <div class="col-12 small text-muted">{h(search_tip)}</div>
            </form>
          </div>
          <div class="card-body contract-group-stack">
            {group('物业合同', 'bi-building', b_rows, 'open')}
            {group('商业合同', 'bi-shop', commercial_rows, 'open')}
          </div>
          {render_pagination('/merchant_contracts', query_items(q, ['keyword']), pg, total_pages, per_page, total_rows, '合同档案分页')}
        </div>
        ''', "merchant_contracts"))

    def _merchant_contract_form(self):
        db = get_db()
        rooms = db.execute(
            """SELECT r.id,r.building,r.unit,r.room_number,r.area,r.floor,r.owner_id,r.tenant_name,r.shop_name,o.name owner_name
               FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
               WHERE (r.unit='B座' OR r.building='B座' OR r.building='金莎国际')
                 AND r.category IN('商户','商业','居民')
               ORDER BY r.unit,r.room_number,r.id"""
        ).fetchall()
        db.close()
        room_options = ''.join(
            f"""<option value="{r['id']}" data-area="{h(r['area'] or '')}" data-floor="{h(r['floor'] or '')}" data-owner-id="{h(r['owner_id'] or '')}"
            data-merchant="{h(r['tenant_name'] or r['shop_name'] or r['owner_name'] or '')}" data-shop="{h(r['shop_name'] or r['tenant_name'] or '')}">
            {h(r['building'])}-{h(r['unit'])}-{h(r['room_number'])} / {h(r['tenant_name'] or r['shop_name'] or r['owner_name'] or '-')} / {n(r['area'])}m²</option>"""
            for r in rooms
        )
        self._html(self._page("新增空间合同档案", f"""
        <form method="POST" action="/merchant_contracts/create" class="card">
          <div class="card-header"><i class="bi bi-file-earmark-plus"></i> 新增空间合同档案（商户合同）</div>
          <div class="card-body row g-3">
            <div class="col-12"><h3 class="h6 text-muted border-bottom pb-2">合同对象</h3></div>
            <div class="col-md-4"><label>合同对象类型 *</label><select name="target_kind" id="targetKind" class="form-select" required>
              <option value="space" selected>商场铺位合同</option>
              <option value="room">B座房间合同</option>
            </select></div>
            <div class="col-md-8 target-room d-none"><label>选择 B座房间 *</label><select name="room_id" id="contractRoom" class="form-select">
              <option value="">请选择房间</option>{room_options}
            </select><div class="form-text">物业合同必须绑定房间；出账后账单进入房间账单、收据、催缴和报表体系。</div></div>
            <div class="col-12"><h3 class="h6 text-muted border-bottom pb-2">空间资料</h3></div>
            <div class="col-md-3 target-space"><label>商户编号 *</label><input name="space_no" id="spaceNo" class="form-control" placeholder="如 商场-(-2F)-01A" required></div>
            <div class="col-md-3"><label>店铺名称</label><input name="shop_name" id="shopName" class="form-control"></div>
            <div class="col-md-3"><label>使用方/商户 *</label><input name="merchant_name" id="merchantName" class="form-control" required></div>
            <div class="col-md-3"><label>业态</label><input name="business_type" class="form-control" placeholder="如 餐饮/零售/台球"></div>
            <div class="col-md-3"><label>楼层</label><input name="floor" id="floorInput" type="number" class="form-control" value="1"></div>
            <div class="col-md-3"><label>合同面积(m²) *</label><input name="area" id="areaInput" type="number" step="0.01" class="form-control" required></div>
            <div class="col-md-3"><label>建筑面积(m²)</label><input name="building_area" id="buildingAreaInput" type="number" step="0.01" class="form-control"></div>
            <div class="col-md-3"><label>水费标准</label><select name="water_rate_type" class="form-select"><option value="非居民">非居民</option><option value="特行">特行</option></select></div>
            <div class="col-md-3"><label>空间备注</label><input name="space_notes" class="form-control"></div>

            <div class="col-12 mt-2"><h3 class="h6 text-muted border-bottom pb-2">合同资料</h3></div>
            <div class="col-md-4"><label>合同编号 *</label><input name="contract_no" class="form-control" placeholder="如 HT-2026-001" required></div>
            <input type="hidden" name="owner_id" id="ownerId">
            <div class="col-md-4"><label>租金单价（元/m²·月）</label><input name="rent_amount" type="number" step="0.1" class="form-control" required></div>
            <div class="col-md-4"><label>租金周期</label><select name="rent_cycle" class="form-select" required>{_cycle_options()}</select></div>
            <div class="col-md-4"><label>特殊计租方式</label><select name="rent_mode" class="form-select">{_rent_mode_options()}</select></div>
            <div class="col-md-4"><label>销售额分成比例</label><input name="turnover_rate" type="number" step="0.0001" min="0" class="form-control" placeholder="如 0.1 表示10%"></div>
            <div class="col-md-4"><label>物业费单价（元/m²·月）</label><input name="property_rate" id="propertyRate" type="number" step="0.0001" class="form-control" required></div>
            <div class="col-md-4"><label>物业费周期</label><select name="property_cycle" class="form-select" required>{_cycle_options()}</select></div>
            <div class="col-md-4"><label>押金单价（元/m²）</label><input name="deposit_amount" type="number" step="0.1" class="form-control" required></div>
            <div class="col-md-4"><label>开始日期</label><input name="start_date" type="date" class="form-control" required></div>
            <div class="col-md-4"><label>结束日期</label><input name="end_date" type="date" class="form-control" required></div>
            <div class="col-md-4"><label>合同备注</label><input name="notes" class="form-control"></div>
            <div class="col-12"><button class="btn btn-primary">保存合同档案</button> <a href="/merchant_contracts" class="btn btn-outline-secondary">取消</a><div class="form-text mt-2">保存档案不会自动收费；日常财务出账请使用“商业收费”。如果商户编号已存在，会更新该空间资料并关联新合同。</div></div>
          </div>
        </form>
        <script>
        function syncShopName(){{
          var shop=document.getElementById('shopName');
          var merchant=document.getElementById('merchantName');
          if(shop && merchant && !shop.value) shop.value=merchant.value;
        }}
        function applyTargetKind(){{
          var kind=document.getElementById('targetKind').value;
          var isRoom=kind==='room';
          document.querySelectorAll('.target-room').forEach(function(el){{el.classList.toggle('d-none', !isRoom);}});
          document.querySelectorAll('.target-space').forEach(function(el){{el.classList.toggle('d-none', isRoom);}});
          document.getElementById('spaceNo').required=!isRoom;
          document.getElementById('contractRoom').required=isRoom;
          if(isRoom){{ syncRoomFields(); }}
        }}
        function syncRoomFields(){{
          var sel=document.getElementById('contractRoom');
          var opt=sel.options[sel.selectedIndex];
          if(!opt || !opt.value) return;
          var area=opt.getAttribute('data-area') || '';
          var floor=opt.getAttribute('data-floor') || '';
          var owner=opt.getAttribute('data-owner-id') || '';
          var merchant=opt.getAttribute('data-merchant') || '';
          var shop=opt.getAttribute('data-shop') || merchant;
          document.getElementById('areaInput').value=area;
          document.getElementById('buildingAreaInput').value=area;
          document.getElementById('floorInput').value=floor || '1';
          document.getElementById('ownerId').value=owner;
          if(merchant) document.getElementById('merchantName').value=merchant;
          if(shop) document.getElementById('shopName').value=shop;
        }}
        document.getElementById('merchantName').addEventListener('blur', syncShopName);
        document.getElementById('targetKind').addEventListener('change', applyTargetKind);
        document.getElementById('contractRoom').addEventListener('change', syncRoomFields);
        applyTargetKind();
        </script>
        """, "merchant_contracts"))

    def _merchant_contract_create(self, d):
        target_kind = qs(d, "target_kind")
        if not target_kind:
            target_kind = "room_legacy" if qs(d, "room_id") and not (qs(d, "space_no") or qs(d, "commercial_space_id")) else "space"
        room_id = qs(d, "room_id") if target_kind in ("room", "room_legacy") else ""
        space_id = None if target_kind in ("room", "room_legacy") else _space_id_from_contract_form(d)
        if target_kind in ("room", "room_legacy") and not room_id:
            return self._redirect("/merchant_contracts/create?flash=请选择B座房间")
        owner_id = qs(d, "owner_id") or None
        if target_kind in ("room", "room_legacy"):
            db_room = get_db()
            room = db_room.execute("SELECT owner_id,area FROM rooms WHERE id=?", (int(room_id),)).fetchone()
            db_room.close()
            if not room:
                return self._redirect("/merchant_contracts/create?flash=房间不存在")
            owner_id = owner_id or room["owner_id"]
        contract_id = create_merchant_contract({
            "commercial_space_id": space_id,
            "room_id": room_id if target_kind in ("room", "room_legacy") else None,
            "owner_id": owner_id,
            "contract_no": qs(d, "contract_no"),
            "merchant_name": qs(d, "merchant_name"),
            "shop_name": qs(d, "shop_name") or qs(d, "merchant_name"),
            "rent_amount": _rent_monthly_total_from_form(d),
            "rent_cycle": qs(d, "rent_cycle") or "monthly",
            "property_rate": qs(d, "property_rate"),
            "property_cycle": qs(d, "property_cycle") or "monthly",
            "deposit_amount": _deposit_total_from_form(d),
            "contract_area": qs(d, "area") or 0,
            "building_area": qs(d, "building_area") or qs(d, "area") or 0,
            "start_date": qs(d, "start_date"),
            "end_date": qs(d, "end_date"),
            "notes": qs(d, "notes"),
        })
        db = get_db()
        upsert_special_rent_rule(db, contract_id, qs(d, "rent_mode"), qs(d, "turnover_rate"),
                                 _rent_monthly_total_from_form(d), qs(d, "notes"))
        db.commit(); db.close()
        return self._redirect("/merchant_contracts?flash=商户合同已保存")
