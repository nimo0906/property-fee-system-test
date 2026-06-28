#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified meter ledger for recurring merchant utility readings."""

from datetime import date

from server.base import BaseHandler
from server.billing_engine import calculate_bill_amount
from server.db import get_db, get_period, h, m, qs, date_to_period, period_to_date, period_to_compact
from server.meter import _water_fee_mismatch_message


def _target_key(target_type, target_id):
    if target_type == 'commercial_space':
        return 'commercial_space_id', int(target_id or 0)
    return 'room_id', int(target_id or 0)


def _target_label(row):
    if row['target_type'] == 'commercial_space':
        return f"商场商铺-{h(row['space_no'] or '')} ({h(row['shop_name'] or row['merchant_name'] or '')})"
    return f"{h(row['building'] or '')}-{h(row['unit'] or '')}-{h(row['room_number'] or '')} ({h(row['tenant_name'] or row['owner_name'] or '')})"


def _ledger_targets(db):
    spaces = db.execute("""SELECT 'commercial_space' target_type,s.id target_id,NULL building,NULL unit,NULL room_number,NULL tenant_name,NULL owner_name,
                                 s.space_no,s.shop_name,s.merchant_name,s.water_rate_type
                          FROM commercial_spaces s WHERE s.status='active' ORDER BY s.space_no,s.id""").fetchall()
    rooms = db.execute("""SELECT 'room' target_type,r.id target_id,r.building,r.unit,r.room_number,r.tenant_name,o.name owner_name,
                               NULL space_no,NULL shop_name,NULL merchant_name,r.water_rate_type
                        FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
                        ORDER BY r.unit,r.building,r.room_number""").fetchall()
    return list(spaces) + list(rooms)


def _existing_reading(db, key_col, target_id, fee_id, period):
    return db.execute(
        f"SELECT * FROM meter_readings WHERE {key_col}=? AND fee_type_id=? AND period=? ORDER BY id DESC LIMIT 1",
        (target_id, fee_id, period),
    ).fetchone()


def _last_confirmed(db, key_col, target_id, fee_id):
    return db.execute(
        f"SELECT current_reading FROM meter_readings WHERE {key_col}=? AND fee_type_id=? AND status='confirmed' ORDER BY period DESC,id DESC LIMIT 1",
        (target_id, fee_id),
    ).fetchone()


def _target_for_calc(db, key_col, target_id):
    if key_col == 'commercial_space_id':
        return db.execute("""SELECT s.id commercial_space_id,NULL id,'商场' building,'商场' unit,s.space_no room_number,'商户' category,
                                  s.area,COALESCE(s.floor,1) floor,NULL owner_id,s.water_rate_type,0 custom_rate,'monthly' payment_cycle
                           FROM commercial_spaces s WHERE s.id=?""", (target_id,)).fetchone()
    return db.execute("SELECT * FROM rooms WHERE id=?", (target_id,)).fetchone()


def _sync_unpaid_bills(db, key_col, target_id, fee, period):
    target = _target_for_calc(db, key_col, target_id)
    if not target:
        return 0
    calc = calculate_bill_amount(db, target, fee, period)
    where = 'commercial_space_id=?' if key_col == 'commercial_space_id' else 'room_id=?'
    cur = db.execute(
        f"""UPDATE bills SET amount=? WHERE {where} AND fee_type_id=? AND billing_period=?
             AND status IN ('unpaid','overdue')""",
        (calc['amount'], target_id, fee['id'], f"{period[:4]}-{period[4:6]}"),
    )
    return cur.rowcount or 0


class MeterLedgerMixin(BaseHandler):
    def _meter_ledger(self, q):
        db = get_db()
        raw_period = qs(q, 'period', '').strip()
        period = date_to_period(raw_period) if raw_period else get_period()
        compact = period_to_compact(period)
        raw_target = qs(q, 'target', '')
        targets = _ledger_targets(db)
        if raw_target and ':' in raw_target:
            target_type, target_id_text = raw_target.split(':', 1)
            target_id = int(target_id_text or 0)
        elif targets:
            target_type = targets[0]['target_type']
            target_id = int(targets[0]['target_id'])
        else:
            target_type, target_id = 'commercial_space', 0
        key_col, target_id = _target_key(target_type, target_id)
        fees = db.execute("SELECT * FROM fee_types WHERE calc_method='meter' AND is_active=1 ORDER BY sort_order,name").fetchall()
        opts = ''.join(
            f'<option value="{r["target_type"]}:{r["target_id"]}" {"selected" if r["target_type"]==target_type and int(r["target_id"])==target_id else ""}>{_target_label(r)}</option>'
            for r in targets
        )
        rows = ''
        for fee in fees:
            existing = _existing_reading(db, key_col, target_id, fee['id'], compact) if target_id else None
            last = _last_confirmed(db, key_col, target_id, fee['id']) if target_id else None
            prev = existing['previous_reading'] if existing else (last['current_reading'] if last else 0)
            current = existing['current_reading'] if existing else ''
            checked = 'checked' if existing or fee['name'] in ('水费(非居民)', '水费(特行)', '电费(商业)', '水费(商业)') else ''
            rows += f'''<tr><td><input type="checkbox" name="enabled_{fee['id']}" {checked}></td>
            <td><span class="badge bg-info">{h(fee['name'])}</span><input type="hidden" name="fee_ids" value="{fee['id']}"></td>
            <td class="text-end">{m(prev)}</td><td><input name="current_reading_{fee['id']}" type="number" step="0.01" class="form-control form-control-sm text-end" value="{h(str(current))}"></td>
            <td class="text-muted small">{h(fee['unit'] or '')} · {h(fee['notes'] or '')}</td></tr>'''
        db.close()
        self._html(self._page('统一抄表台账', f'''
<div class="alert alert-info py-2">房间管理和合同档案都可在同一商户下一次录入水、电；同一对象同一账期重复保存会覆盖草稿/原记录，确认后同步对应未缴账单。</div>
<form method="POST" action="/meter_readings/ledger/save" class="card"><div class="card-body">
<div class="row g-3 mb-3"><div class="col-md-5"><label>抄表对象</label><input type="search" id="ledgerTargetSearch" class="form-control form-control-sm mb-2" placeholder="搜索铺位号/房号/店名/商户..." oninput="window.filterSearchableSelect&&window.filterSearchableSelect('ledgerTarget','ledgerTargetSearch')"><select name="target" id="ledgerTarget" class="form-select searchable-select" data-search-input="ledgerTargetSearch" onchange="location.href='/meter_readings/ledger?period='+document.getElementById('ledgerPeriod').value+'&target='+this.value">{opts}</select></div>
<div class="col-md-3"><label>账期</label><input id="ledgerPeriod" type="date" name="period" class="form-control" value="{period_to_date(period)}"></div>
<div class="col-md-2"><label>抄表日期</label><input type="date" name="reading_date" class="form-control" value="{date.today().isoformat()}"></div>
<div class="col-md-2"><label>状态</label><select name="status" class="form-select"><option value="draft">草稿</option><option value="confirmed">已确认</option></select></div></div>
<input type="hidden" name="target_type" value="{h(target_type)}"><input type="hidden" name="target_id" value="{target_id}">
<div class="table-responsive"><table class="table table-hover align-middle"><thead><tr><th style="width:50px">选择</th><th>费用</th><th class="text-end">上次</th><th>本次读数</th><th>说明</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="d-flex gap-2"><button class="btn btn-primary"><i class="bi bi-save"></i> 保存台账</button><a class="btn btn-outline-secondary" href="/meter_readings">返回抄表列表</a></div>
</div></form><script src="/static/searchable_select.js?v=20260615"></script>''', 'meter'))

    def _meter_ledger_save(self, d):
        raw_target = qs(d, 'target', '')
        target_type = qs(d, 'target_type', 'commercial_space')
        target_id = int(qs(d, 'target_id', 0) or 0)
        if raw_target and ':' in raw_target:
            target_type, target_text = raw_target.split(':', 1)
            target_id = int(target_text or 0)
        if not target_id:
            if target_type == 'commercial_space':
                target_id = int(qs(d, 'commercial_space_id', 0) or 0)
            else:
                target_id = int(qs(d, 'room_id', 0) or 0)
        key_col, target_id = _target_key(target_type, target_id)
        if not target_id:
            return self._redirect('/meter_readings/ledger?flash=请选择抄表对象')
        db = get_db()
        period = period_to_compact(qs(d, 'period', get_period()))
        status = qs(d, 'status', 'draft')
        fee_ids = d.get('fee_ids', [])
        if isinstance(fee_ids, str):
            fee_ids = [fee_ids]
        if not fee_ids:
            fee_ids = [k.removeprefix('enabled_') for k in d.keys() if k.startswith('enabled_')]
        saved = 0
        synced = 0
        for fid_text in fee_ids:
            if d.get(f'enabled_{fid_text}') is None:
                continue
            current_text = qs(d, f'current_reading_{fid_text}', '').strip()
            if current_text == '':
                continue
            fid = int(fid_text)
            mismatch = _water_fee_mismatch_message(db, target_id if key_col == 'room_id' else None, fid, target_id if key_col == 'commercial_space_id' else None)
            if mismatch:
                db.close()
                return self._redirect('/meter_readings/ledger?flash=' + mismatch)
            fee = db.execute('SELECT * FROM fee_types WHERE id=?', (fid,)).fetchone()
            existing = _existing_reading(db, key_col, target_id, fid, period)
            previous = existing['previous_reading'] if existing else ((_last_confirmed(db, key_col, target_id, fid) or {'current_reading': 0})['current_reading'])
            current = float(current_text)
            consumption = round(current - float(previous or 0), 2)
            if consumption < 0:
                db.close()
                return self._redirect('/meter_readings/ledger?flash=读数不能小于上次')
            if existing:
                db.execute('UPDATE meter_readings SET previous_reading=?,current_reading=?,consumption=?,reading_date=?,status=?,notes=? WHERE id=?',
                           (previous, current, consumption, qs(d, 'reading_date', date.today().isoformat()), status, '统一抄表台账保存', existing['id']))
            else:
                rid = target_id if key_col == 'room_id' else None
                sid = target_id if key_col == 'commercial_space_id' else None
                db.execute('''INSERT INTO meter_readings(room_id,commercial_space_id,fee_type_id,period,previous_reading,current_reading,consumption,reading_date,status,notes)
                              VALUES(?,?,?,?,?,?,?,?,?,?)''', (rid, sid, fid, period, previous, current, consumption, qs(d, 'reading_date', date.today().isoformat()), status, '统一抄表台账保存'))
            saved += 1
            if status == 'confirmed' and fee:
                synced += _sync_unpaid_bills(db, key_col, target_id, fee, period)
        db.commit(); db.close()
        self._redirect(f'/meter_readings/ledger?target={target_type}:{target_id}&period={period_to_date(period)}&flash=已保存{saved}项抄表，同步{synced}笔未缴账单')
