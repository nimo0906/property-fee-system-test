#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Meter readings management."""

from server.db import get_db, get_period, h, m, qs, date_to_period, period_to_date, period_to_compact
from server.base import BaseHandler
from server.billing_engine import fee_applies_to_room
from datetime import date


def _water_fee_mismatch_message(db, room_id, fee_type_id):
    row = db.execute(
        """SELECT r.*,f.name fee_name FROM rooms r
           JOIN fee_types f ON f.id=? WHERE r.id=?""",
        (fee_type_id, room_id),
    ).fetchone()
    if not row:
        return ''
    fee_name = row['fee_name'] or ''
    if '水费(' not in fee_name:
        return ''
    if fee_applies_to_room(fee_name, row):
        return ''
    expected = row['water_rate_type'] or '非居民'
    return f'水费标准与收费项目不一致：房间水费标准为{expected}，当前选择{fee_name}。请在房间管理调整水费标准，或选择水费({expected})抄表。'


class MeterMixin(BaseHandler):

    # ── 抄表管理 ──────────────────────────────────────────────
    def _meter_list(self, q):
        try:
            db=get_db();s=qs(q,'status');p=date_to_period(qs(q,'period',''));cp=period_to_compact(p) if p else ''
            sql='''SELECT m.*,r.building,r.unit,r.room_number,f.name ft FROM meter_readings m
                LEFT JOIN rooms r ON m.room_id=r.id LEFT JOIN fee_types f ON m.fee_type_id=f.id WHERE 1=1'''
            vals=[]
            if cp:sql+=" AND m.period=?";vals.append(cp)
            if s:sql+=" AND m.status=?";vals.append(s)
            sql+=" ORDER BY m.reading_date DESC"
            rows=db.execute(sql,vals).fetchall()
            db.close()
            rh = ""
            for r in rows:
                room_str = h(r["building"]or"") + "-" + h(r["unit"]or"") + "-" + h(r["room_number"]or"")
                ft_name = h(r["ft"])
                prev = m(r["previous_reading"])
                curr = m(r["current_reading"])
                cons = m(r["consumption"])
                rd = h(r["reading_date"] or "")
                status_badge = '<span class="badge bg-success">已确认</span>' if r["status"]=="confirmed" else '<span class="badge bg-warning text-dark">草稿</span>'
                confirm_btn = '<form method=POST action="/meter_readings/' + str(r["id"]) + '/confirm" style=display:inline><button class="btn btn-sm btn-outline-success"><i class="bi bi-check-lg"></i></button></form>' if r["status"]=="draft" else ""
                del_btn = '<form method=POST action="/meter_readings/' + str(r["id"]) + '/delete" style=display:inline><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>'
                rh += "<tr>"
                rh += "<td>" + room_str + "</td>"
                rh += '<td><span class="badge bg-info">' + ft_name + "</span></td>"
                rh += "<td>" + str(r["period"]) + "</td>"
                rh += '<td class="text-end">' + prev + "</td>"
                rh += '<td class="text-end">' + curr + "</td>"
                rh += '<td class="text-end"><strong>' + cons + "</strong></td>"
                rh += "<td>" + status_badge + "</td>"
                rh += "<td>" + rd + "</td>"
                rh += "<td>" + confirm_btn + del_btn + "</td></tr>"
            draft_sel=' selected' if s=='draft' else ''
            confirmed_sel=' selected' if s=='confirmed' else ''
            tpl=self._load_template('meter_list.html')
            tpl=tpl.replace('{PERIOD}',period_to_date(p)).replace('{DRAFT_SEL}',draft_sel).replace('{CONFIRMED_SEL}',confirmed_sel)
            tpl=tpl.replace('{ROWS}',rh or '<tr><td colspan="9" class="text-center text-muted py-4">暂无抄表记录</td></tr>')
            self._html(self._page('抄表管理',tpl,'meter'))
        except Exception as e:
            self._html(f'<div class="alert alert-danger">抄表管理加载失败: {str(e)}</div><a href="/" class="btn btn-outline-primary">返回首页</a>')

    def _meter_form(self):
        db=get_db()
        fts=db.execute("SELECT * FROM fee_types WHERE calc_method='meter' AND is_active=1 ORDER BY sort_order").fetchall()
        rooms=db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.building,r.room_number").fetchall()
        db.close()
        ft_opts='<option value="">--选择--</option>'+''.join(f'<option value="{f["id"]}">{h(f["name"])}</option>' for f in fts)
        rm_opts='<option value="">--选择--</option>'+''.join(
            f'<option value="{r["id"]}" data-water="{h(r["water_rate_type"] or "非居民")}">'
            f'{h(r["building"])}-{h(r["room_number"])} ({h(r["oname"]or"")})</option>'
            for r in rooms
        )
        self._html(self._page('录入抄表',f'''
<form method=POST action="/meter_readings/create" class="row g-3">
<div class="col-md-6"><label>房间 *</label><select name="room_id" class="form-select" id="mRoom" required>{rm_opts}</select></div>
<div class="col-md-6"><label>费用类型 *</label><select name="fee_type_id" class="form-select" id="mFt" required>{ft_opts}</select>
<small class="text-muted d-block mt-1" id="waterFeeHint">房间管理水费类型提示：选择房间后，会显示该房间在房间管理中录入的水费标准，便于选择水费(非居民)或水费(特行)。例如水费类型为“特行”时，建议选择：水费(特行)。</small></div>
<div class="col-md-4"><label>账期日期</label><input type="date" name="period" class="form-control" value="{period_to_date(get_period())}"><small class="text-muted">系统按所选日期所在月份作为账期</small></div>
<div class="col-md-4"><label>抄表日期</label><input type="date" name="reading_date" class="form-control" value="{date.today().isoformat()}"></div>
<div class="col-md-4"><label>状态</label><select name="status" class="form-select"><option value="draft">草稿</option><option value="confirmed">已确认</option></select></div>
<div class="col-md-6"><label>上次读数</label><input class="form-control" id="mPrev" value="0" readonly disabled><small class="text-muted">自动获取</small></div>
<div class="col-md-6"><label>本次读数 *</label><input name="current_reading" type="number" class="form-control" step="0.01" required></div>
<div class="col-12"><label>备注</label><input name="notes" class="form-control"></div>
<div class="col-12"><hr><button class="btn btn-primary"><i class="bi bi-check-lg"></i> 保存</button> <a href="/meter_readings" class="btn btn-outline-secondary">取消</a></div></form>
<script>
function updateWaterFeeHint(){{
    var sel=document.getElementById('mRoom');
    var opt=sel.options[sel.selectedIndex];
    var water=(opt&&opt.dataset&&opt.dataset.water)||'';
    var hint=document.getElementById('waterFeeHint');
    if(!hint) return;
    if(water){{
        hint.textContent='房间管理水费类型提示：该房间水费类型为 '+water+'，建议选择：水费('+water+')。';
    }}else{{
        hint.textContent='房间管理水费类型提示：选择房间后，会显示该房间在房间管理中录入的水费标准，便于选择水费(非居民)或水费(特行)。例如水费类型为“特行”时，建议选择：水费(特行)。';
    }}
}}
document.getElementById('mRoom').addEventListener('change',function(){{updateWaterFeeHint();loadMeter();}});document.getElementById('mFt').addEventListener('change',loadMeter);
function loadMeter(){{var r=document.getElementById('mRoom').value;var f=document.getElementById('mFt').value;if(r&&f)fetch('/api/rooms/'+r+'/meter/'+f).then(x=>x.json()).then(d=>document.getElementById('mPrev').value=d.previous_reading).catch(()=>{{}});}}
updateWaterFeeHint();
</script>''','meter'))

    def _meter_create(self, d):
        db=get_db();rid=int(qs(d,'room_id'));fid=int(qs(d,'fee_type_id'))
        mismatch = _water_fee_mismatch_message(db, rid, fid)
        if mismatch:
            db.close(); return self._redirect('/meter_readings/create?flash=' + mismatch)
        cur=float(qs(d,'current_reading',0));prd=period_to_compact(qs(d,'period',get_period()))
        last=db.execute("SELECT current_reading FROM meter_readings WHERE room_id=? AND fee_type_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1",(rid,fid)).fetchone()
        prev=last[0] if last else 0
        cons=round(cur-prev,2)
        if cons<0:db.close();return self._redirect('/meter_readings/create?flash=读数不能小于上次')
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,previous_reading,current_reading,consumption,reading_date,status,notes) VALUES(?,?,?,?,?,?,?,?,?)",
                   (rid,fid,prd,prev,cur,cons,qs(d,'reading_date',date.today().isoformat()),qs(d,'status','draft'),qs(d,'notes')))
        db.commit();db.close()
        self._redirect('/meter_readings?flash=抄表录入成功')

    def _meter_confirm(self, mid):
        db=get_db()
        row = db.execute("SELECT room_id,fee_type_id FROM meter_readings WHERE id=?", (mid,)).fetchone()
        if row:
            mismatch = _water_fee_mismatch_message(db, row['room_id'], row['fee_type_id'])
            if mismatch:
                db.close(); return self._redirect('/meter_readings?flash=' + mismatch)
        db.execute("UPDATE meter_readings SET status='confirmed' WHERE id=?",(mid,));db.commit();db.close()
        self._redirect('/meter_readings?flash=已确认')

    def _meter_delete(self, mid):
        db=get_db();db.execute("DELETE FROM meter_readings WHERE id=?",(mid,));db.commit();db.close()
        self._redirect('/meter_readings?flash=已删除')

    # ── API ──────────────────────────────────────────────────
    def _api_meter(self, rid, fid):
        db=get_db()
        last=db.execute("SELECT current_reading,reading_date FROM meter_readings WHERE room_id=? AND fee_type_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1",(rid,fid)).fetchone()
        db.close()
        self._json({'previous_reading':last[0] if last else 0,'last_reading_date':last[1] if last else None})
