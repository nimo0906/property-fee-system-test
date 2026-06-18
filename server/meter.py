#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Meter readings management."""

from datetime import date

from server.base import BaseHandler
from server.billing_engine import fee_applies_to_room, calculate_bill_amount
from server.db import get_db, get_period, h, m, qs, date_to_period, period_to_date, period_to_compact
from server.pagination import pagination_state, query_items, render_pagination


def _water_fee_mismatch_message(db, room_id, fee_type_id, commercial_space_id=None):
    fee = db.execute("SELECT name FROM fee_types WHERE id=?", (fee_type_id,)).fetchone()
    fee_name = (fee["name"] if fee else "") or ""
    if "水费(" not in fee_name:
        return ""
    if commercial_space_id:
        row = db.execute("SELECT water_rate_type FROM commercial_spaces WHERE id=?", (commercial_space_id,)).fetchone()
        expected = (row["water_rate_type"] if row else "") or "非居民"
        if fee_name == f"水费({expected})":
            return ""
        return f"水费标准与收费项目不一致：商铺水费标准为{expected}，当前选择{fee_name}。请在空间合同档案中调整水费标准，或选择水费({expected})抄表。"
    row = db.execute(
        """SELECT r.*,f.name fee_name FROM rooms r
           JOIN fee_types f ON f.id=? WHERE r.id=?""",
        (fee_type_id, room_id),
    ).fetchone()
    if not row or fee_applies_to_room(fee_name, row):
        return ""
    expected = row["water_rate_type"] or "非居民"
    return f"水费标准与收费项目不一致：房间水费标准为{expected}，当前选择{fee_name}。请在收费对象管理调整水费标准，或选择水费({expected})抄表。"


def _target_key(target_type, room_id=None, commercial_space_id=None):
    if target_type == 'commercial_space':
        return 'commercial_space_id', int(commercial_space_id or 0)
    return 'room_id', int(room_id or 0)


def _target_label(row):
    if row['target_type'] == 'commercial_space':
        return f"商业空间-{h(row['space_no'] or '')} ({h(row['shop_name'] or row['merchant_name'] or '')})"
    return f"{h(row['building'] or '')}-{h(row['unit'] or '')}-{h(row['room_number'] or '')} ({h(row['tenant_name'] or row['owner_name'] or '')})"


def _ledger_targets(db):
    room_rows = db.execute("""SELECT 'room' target_type,r.id target_id,r.building,r.unit,r.room_number,r.tenant_name,o.name owner_name,
                                    NULL space_no,NULL shop_name,NULL merchant_name,r.water_rate_type
                             FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
                             ORDER BY r.unit,r.building,r.room_number""").fetchall()
    space_rows = db.execute("""SELECT 'commercial_space' target_type,s.id target_id,NULL building,NULL unit,NULL room_number,NULL tenant_name,NULL owner_name,
                                     s.space_no,s.shop_name,s.merchant_name,s.water_rate_type
                              FROM commercial_spaces s WHERE s.status='active' ORDER BY s.space_no,s.id""").fetchall()
    return list(space_rows) + list(room_rows)


def _ledger_meter_fees(db):
    return db.execute("SELECT * FROM fee_types WHERE calc_method='meter' AND is_active=1 ORDER BY sort_order,name").fetchall()


def _last_confirmed_reading(db, key_col, target_id, fee_id):
    return db.execute(
        f"SELECT current_reading FROM meter_readings WHERE {key_col}=? AND fee_type_id=? AND status='confirmed' ORDER BY period DESC,id DESC LIMIT 1",
        (target_id, fee_id),
    ).fetchone()


def _existing_period_reading(db, key_col, target_id, fee_id, period):
    return db.execute(
        f"SELECT * FROM meter_readings WHERE {key_col}=? AND fee_type_id=? AND period=? ORDER BY id DESC LIMIT 1",
        (target_id, fee_id, period),
    ).fetchone()


def _sync_unpaid_meter_bills(db, key_col, target_id, fee, period):
    if key_col == 'commercial_space_id':
        target = db.execute("""SELECT s.id commercial_space_id,NULL id,'商场' building,'商场' unit,s.space_no room_number,'商户' category,
                                     s.area,COALESCE(s.floor,1) floor,NULL owner_id,s.water_rate_type,0 custom_rate,'monthly' payment_cycle
                              FROM commercial_spaces s WHERE s.id=?""", (target_id,)).fetchone()
        where = "commercial_space_id=?"
    else:
        target = db.execute("SELECT * FROM rooms WHERE id=?", (target_id,)).fetchone()
        where = "room_id=?"
    if not target:
        return 0
    calc = calculate_bill_amount(db, target, fee, period)
    cur = db.execute(
        f"""UPDATE bills SET amount=? WHERE {where} AND fee_type_id=? AND billing_period=?
             AND status IN ('unpaid','overdue')""",
        (calc['amount'], target_id, fee['id'], period[:4] + '-' + period[4:6]),
    )
    return cur.rowcount or 0


class MeterMixin(BaseHandler):
    def _meter_list(self, q):
        try:
            db = get_db()
            status = qs(q, "status")
            raw_period = qs(q, "period", "").strip()
            period = date_to_period(raw_period) if raw_period else ""
            compact_period = period_to_compact(period) if period else ""
            keyword = qs(q, "keyword").strip()
            fee_id = qs(q, "fee_type_id").strip()
            sql = """SELECT m.*,r.building,r.unit,r.room_number,r.tenant_name,o.name owner_name,
                            s.space_no,s.shop_name,s.merchant_name,f.name ft
                     FROM meter_readings m
                     LEFT JOIN rooms r ON m.room_id=r.id
                     LEFT JOIN owners o ON r.owner_id=o.id
                     LEFT JOIN commercial_spaces s ON m.commercial_space_id=s.id
                     LEFT JOIN fee_types f ON m.fee_type_id=f.id WHERE 1=1"""
            vals = []
            if compact_period:
                sql += " AND m.period=?"; vals.append(compact_period)
            if status:
                sql += " AND m.status=?"; vals.append(status)
            if fee_id:
                sql += " AND m.fee_type_id=?"; vals.append(int(fee_id))
            if keyword:
                like = f"%{keyword}%"
                sql += """ AND (r.building LIKE ? OR r.unit LIKE ? OR r.room_number LIKE ? OR r.tenant_name LIKE ?
                           OR o.name LIKE ? OR s.space_no LIKE ? OR s.shop_name LIKE ? OR s.merchant_name LIKE ? OR f.name LIKE ?)"""
                vals.extend([like] * 9)
            total_rows = db.execute("SELECT COUNT(*) FROM (" + sql + ")", vals).fetchone()[0]
            pg, per_page, total_pages = pagination_state(q, total_rows)
            sql += " ORDER BY m.reading_date DESC,m.id DESC"
            rows = db.execute(sql + " LIMIT ? OFFSET ?", vals + [per_page, (pg - 1) * per_page]).fetchall()
            fts = db.execute("SELECT id,name FROM fee_types WHERE calc_method='meter' AND is_active=1 ORDER BY sort_order,name").fetchall()
            db.close()
            body = ""
            for r in rows:
                if r["commercial_space_id"]:
                    target = f"商业空间-{h(r['space_no'] or '')} ({h(r['shop_name'] or r['merchant_name'] or '')})"
                else:
                    target = f"{h(r['building'] or '')}-{h(r['unit'] or '')}-{h(r['room_number'] or '')} ({h(r['tenant_name'] or r['owner_name'] or '')})"
                badge = '<span class="badge bg-success">已确认</span>' if r["status"] == "confirmed" else '<span class="badge bg-warning text-dark">草稿</span>'
                confirm = f'<form method=POST action="/meter_readings/{r["id"]}/confirm" style=display:inline><button class="btn btn-sm btn-outline-success"><i class="bi bi-check-lg"></i></button></form>' if r["status"] == "draft" else ""
                delete = f'<form method=POST action="/meter_readings/{r["id"]}/delete" style=display:inline><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>'
                body += f"""<tr><td>{target}</td><td><span class="badge bg-info">{h(r['ft'])}</span></td><td>{h(r['period'])}</td>
                <td class="text-end">{m(r['previous_reading'])}</td><td class="text-end">{m(r['current_reading'])}</td>
                <td class="text-end"><strong>{m(r['consumption'])}</strong></td><td>{badge}</td><td>{h(r['reading_date'] or '')}</td><td>{confirm}{delete}</td></tr>"""
            ft_opts = '<option value="">全部费用类型</option>' + ''.join(f'<option value="{f["id"]}"{" selected" if fee_id == str(f["id"]) else ""}>{h(f["name"])}</option>' for f in fts)
            tpl = self._load_template("meter_list.html")
            tpl = tpl.replace("{PERIOD}", period_to_date(period) if period else "").replace("{KEYWORD}", h(keyword))
            tpl = tpl.replace("{DRAFT_SEL}", " selected" if status == "draft" else "").replace("{CONFIRMED_SEL}", " selected" if status == "confirmed" else "")
            tpl = tpl.replace("{BUILDING_OPTIONS}", '<option value="">全部对象</option>').replace("{UNIT_OPTIONS}", '<option value="">全部区域</option>')
            tpl = tpl.replace("{FEE_OPTIONS}", ft_opts)
            tpl = tpl.replace("{ROWS}", body or '<tr><td colspan="9" class="text-center text-muted py-4">暂无抄表记录</td></tr>')
            page_links = render_pagination(
                '/meter_readings',
                query_items(q, ['period', 'status', 'fee_type_id', 'keyword']),
                pg,
                total_pages,
                per_page,
                total_rows,
                '抄表分页',
            )
            tpl = tpl.replace("{PAGE_LINKS}", page_links)
            self._html(self._page("抄表管理", tpl, "meter"))
        except Exception as e:
            self._html(f'<div class="alert alert-danger">抄表管理加载失败: {h(str(e))}</div><a href="/" class="btn btn-outline-primary">返回首页</a>')

    def _meter_form(self):
        db = get_db()
        fts = db.execute("SELECT * FROM fee_types WHERE calc_method='meter' AND is_active=1 ORDER BY sort_order").fetchall()
        rooms = db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.unit,r.building,r.room_number").fetchall()
        spaces = db.execute("SELECT * FROM commercial_spaces WHERE status='active' ORDER BY space_no,id").fetchall()
        units = db.execute("SELECT DISTINCT unit FROM rooms WHERE unit IS NOT NULL AND unit<>'' ORDER BY unit").fetchall()
        db.close()
        ft_opts = '<option value="">--选择--</option>' + ''.join(f'<option value="{f["id"]}">{h(f["name"])}</option>' for f in fts)
        unit_opts = '<option value="">--先选择单元/分区--</option>' + ''.join(f'<option value="{h(r["unit"])}">{h(r["unit"])}</option>' for r in units)
        room_opts = '<option value="">选择单元/分区后再选择收费对象</option>' + ''.join(
            f'<option value="{r["id"]}" data-unit="{h(r["unit"] or "")}" data-water="{h(r["water_rate_type"] or "非居民")}" data-label="{h(r["building"])}-{h(r["unit"] or "")}-{h(r["room_number"])} {h(r["tenant_name"] or r["oname"] or "")}">{h(r["building"])}-{h(r["unit"] or "")}-{h(r["room_number"])} ({h(r["tenant_name"] or r["oname"] or "")})</option>'
            for r in rooms
        )
        space_opts = '<option value="">--选择商业空间--</option>' + ''.join(
            f'<option value="{s["id"]}" data-water="{h(s["water_rate_type"] or "非居民")}">{h(s["space_no"])} ({h(s["shop_name"] or s["merchant_name"] or "")})</option>'
            for s in spaces
        )
        self._html(self._page("录入抄表", f'''
<form method="POST" action="/meter_readings/create" class="row g-3">
<div class="col-md-4"><label>抄表对象 *</label><select name="target_type" class="form-select" id="targetType"><option value="room">收费对象/商户</option><option value="commercial_space">商铺档案(兼容)</option></select><small class="text-muted">住户、商户和商业对象优先按收费对象管理抄表；商铺档案抄表仅作兼容。</small></div>
<div class="col-md-4 target-room"><label>单元/分区 *</label><select class="form-select" id="mUnit">{unit_opts}</select></div>
<div class="col-md-4 target-room"><label>收费对象</label><select name="room_id" class="form-select" id="mRoom" disabled>{room_opts}</select></div>
<div class="col-md-8 target-space" style="display:none"><label>商铺档案(兼容)</label><select name="commercial_space_id" class="form-select" id="mSpace">{space_opts}</select></div>
<div class="col-md-6"><label>费用类型 *</label><select name="fee_type_id" class="form-select" id="mFt" required>{ft_opts}</select><small class="text-muted d-block mt-1" id="waterFeeHint">收费对象管理水费类型提示：选择对象后，会显示水费标准。例如水费类型为“特行”时，建议选择：水费(特行)。</small></div>
<div class="col-md-3"><label>账期日期</label><input type="date" name="period" class="form-control" value="{period_to_date(get_period())}"></div>
<div class="col-md-3"><label>抄表日期</label><input type="date" name="reading_date" class="form-control" value="{date.today().isoformat()}"></div>
<div class="col-md-4"><label>状态</label><select name="status" class="form-select"><option value="draft">草稿</option><option value="confirmed">已确认</option></select></div>
<div class="col-md-4"><label>上次读数</label><input class="form-control" id="mPrev" value="0" readonly disabled></div>
<div class="col-md-4"><label>本次读数 *</label><input name="current_reading" type="number" class="form-control" step="0.01" required></div>
<div class="col-12"><label>备注</label><input name="notes" class="form-control"></div>
<div class="col-12"><hr><button class="btn btn-primary">保存</button> <a href="/meter_readings" class="btn btn-outline-secondary">取消</a></div></form>
<script>
function mode(){{return document.getElementById('targetType').value;}}
function activeSelect(){{return mode()==='commercial_space'?document.getElementById('mSpace'):document.getElementById('mRoom');}}
function refreshMode(){{var sp=mode()==='commercial_space';document.querySelectorAll('.target-room').forEach(x=>x.style.display=sp?'none':'');document.querySelectorAll('.target-space').forEach(x=>x.style.display=sp?'':'none');document.getElementById('mRoom').required=!sp;document.getElementById('mSpace').required=sp;updateWaterFeeHint();loadMeter();}}
function updateRoomOptions(){{var unit=document.getElementById('mUnit').value;var room=document.getElementById('mRoom');room.value='';for(var i=1;i<room.options.length;i++){{var opt=room.options[i];var ok=unit&&opt.dataset.unit===unit;opt.hidden=!ok;opt.disabled=!ok;}}room.disabled=!unit;updateWaterFeeHint();}}
function updateWaterFeeHint(){{var sel=activeSelect();var opt=sel.options[sel.selectedIndex];var water=(opt&&opt.dataset&&opt.dataset.water)||'';document.getElementById('waterFeeHint').textContent=water?'当前对象水费标准为 '+water+'，建议选择：水费('+water+')。':'收费对象管理水费类型提示：选择对象后，会显示水费标准。例如水费类型为“特行”时，建议选择：水费(特行)。';}}
function loadMeter(){{var f=document.getElementById('mFt').value;var sel=activeSelect();var id=sel.value;if(!id||!f)return;var url=mode()==='commercial_space'?('/api/commercial_spaces/'+id+'/meter/'+f):('/api/rooms/'+id+'/meter/'+f);fetch(url).then(x=>x.json()).then(d=>document.getElementById('mPrev').value=d.previous_reading).catch(()=>{{}});}}
document.getElementById('targetType').addEventListener('change',refreshMode);document.getElementById('mUnit').addEventListener('change',updateRoomOptions);document.getElementById('mRoom').addEventListener('change',function(){{updateWaterFeeHint();loadMeter();}});document.getElementById('mSpace').addEventListener('change',function(){{updateWaterFeeHint();loadMeter();}});document.getElementById('mFt').addEventListener('change',loadMeter);refreshMode();updateRoomOptions();
</script>''', "meter"))

    def _meter_create(self, d):
        db = get_db()
        fid = int(qs(d, "fee_type_id"))
        target_type = qs(d, "target_type", "room")
        rid = int(qs(d, "room_id") or 0) if target_type != "commercial_space" else None
        sid = int(qs(d, "commercial_space_id") or 0) if target_type == "commercial_space" else None
        if not rid and not sid:
            db.close(); return self._redirect("/meter_readings/create?flash=请选择抄表对象")
        mismatch = _water_fee_mismatch_message(db, rid, fid, sid)
        if mismatch:
            db.close(); return self._redirect("/meter_readings/create?flash=" + mismatch)
        current = float(qs(d, "current_reading", 0))
        period = period_to_compact(qs(d, "period", get_period()))
        if sid:
            last = db.execute("SELECT current_reading FROM meter_readings WHERE commercial_space_id=? AND fee_type_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1", (sid, fid)).fetchone()
        else:
            last = db.execute("SELECT current_reading FROM meter_readings WHERE room_id=? AND fee_type_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1", (rid, fid)).fetchone()
        previous = last[0] if last else 0
        consumption = round(current - previous, 2)
        if consumption < 0:
            db.close(); return self._redirect("/meter_readings/create?flash=读数不能小于上次")
        db.execute("""INSERT INTO meter_readings(room_id,commercial_space_id,fee_type_id,period,previous_reading,current_reading,consumption,reading_date,status,notes)
                      VALUES(?,?,?,?,?,?,?,?,?,?)""", (rid, sid, fid, period, previous, current, consumption, qs(d, "reading_date", date.today().isoformat()), qs(d, "status", "draft"), qs(d, "notes")))
        db.commit(); db.close()
        self._redirect("/meter_readings?flash=抄表录入成功")

    def _meter_confirm(self, mid):
        db = get_db()
        row = db.execute("SELECT room_id,commercial_space_id,fee_type_id FROM meter_readings WHERE id=?", (mid,)).fetchone()
        if row:
            mismatch = _water_fee_mismatch_message(db, row["room_id"], row["fee_type_id"], row["commercial_space_id"])
            if mismatch:
                db.close(); return self._redirect("/meter_readings?flash=" + mismatch)
        db.execute("UPDATE meter_readings SET status='confirmed' WHERE id=?", (mid,)); db.commit(); db.close()
        self._redirect("/meter_readings?flash=已确认")

    def _meter_delete(self, mid):
        db = get_db(); db.execute("DELETE FROM meter_readings WHERE id=?", (mid,)); db.commit(); db.close()
        self._redirect("/meter_readings?flash=已删除")

    def _api_meter(self, rid, fid):
        db = get_db()
        last = db.execute("SELECT current_reading,reading_date FROM meter_readings WHERE room_id=? AND fee_type_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1", (rid, fid)).fetchone()
        db.close()
        self._json({"previous_reading": last[0] if last else 0, "last_reading_date": last[1] if last else None})

    def _api_space_meter(self, sid, fid):
        db = get_db()
        last = db.execute("SELECT current_reading,reading_date FROM meter_readings WHERE commercial_space_id=? AND fee_type_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1", (sid, fid)).fetchone()
        db.close()
        self._json({"previous_reading": last[0] if last else 0, "last_reading_date": last[1] if last else None})
