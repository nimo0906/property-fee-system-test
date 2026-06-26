#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified billing pages: property billing and commercial billing."""

from server.db import get_db, get_period, update_overdue_bills, h, m, qs
from server.base import BaseHandler
from datetime import date
import json

from server.billing_rules import fee_in_scope


def _tenant_group_key(room):
    """Return a stable tenant grouping key; never fall back to owner_id."""
    for field in ('tenant_id_card', 'tenant_phone', 'tenant_name', 'shop_name'):
        try:
            value = (room[field] or '').strip()
        except Exception:
            value = ''
        if value:
            return f'{field}:{value.lower()}'
    return ''


class BillingUiMixin(BaseHandler):

    def _billing(self):
        """物业收费：只显示金莎物业收费项目 (sort_order < 30)"""
        return self._render_billing(mode='property', active_tab='billing',
                                    title='物业收费', exclude_commercial=True)

    def _commercial_billing(self):
        """商业收费：商户/商业对象日常财务出账入口。"""
        return self._render_billing(mode='commercial', active_tab='commercial_billing',
                                    title='商业收费', exclude_commercial=False)

    def _render_billing(self, mode, active_tab, title, exclude_commercial):
        """渲染收费页面，按 mode 过滤费用类型."""
        del exclude_commercial
        update_overdue_bills()
        db = get_db()
        room_sql = "SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id"
        if mode == 'commercial':
            room_sql += " WHERE r.unit='商场'"
        else:
            room_sql += " WHERE (r.unit='B座' OR r.building='B座')"
        rooms = db.execute(room_sql + " ORDER BY r.building,r.unit,r.room_number").fetchall()
        all_fts = db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order").fetchall()
        elevator_rows = db.execute("SELECT * FROM elevator_fee_tiers ORDER BY floor_from").fetchall()
        elevator_list = [{'floor_from': e['floor_from'], 'floor_to': e['floor_to'], 'rate': e['rate']}
                         for e in elevator_rows]
        tenant_rooms = {}
        for r in rooms:
            tenant_key = _tenant_group_key(r)
            if not tenant_key:
                continue
            if tenant_key not in tenant_rooms:
                tenant_rooms[tenant_key] = []
            tenant_rooms[tenant_key].append({
                'id': r['id'],
                'meterTarget': f"room:{r['id']}",
                'name': f"{r['building'] or ''}-{r['unit'] or ''}-{r['room_number'] or ''}",
                'cat': r['category'] or '',
                'area': r['area'],
                'floor': r['floor'] or '1',
                'water': r['water_rate_type'] or '非居民',
                'rate': r['custom_rate'] or '',
                'cycle': r['payment_cycle'] or 'monthly'
            })
        room_ids = [r['id'] for r in rooms]
        meter_map = {}
        meter_detail_map = {}
        if room_ids:
            placeholders = ','.join('?' for _ in room_ids)
            meter_rows = db.execute(
                f"""SELECT m.room_id,m.fee_type_id,m.period,COALESCE(SUM(m.consumption),0) consumption,
                           f.name fee_name
                    FROM meter_readings m
                    LEFT JOIN fee_types f ON m.fee_type_id=f.id
                    WHERE m.status='confirmed' AND m.room_id IN ({placeholders})
                    GROUP BY m.room_id,m.fee_type_id,m.period,f.name""",
                room_ids,
            ).fetchall()
            for mr in meter_rows:
                consumption = float(mr['consumption'] or 0)
                for key in (f"{mr['room_id']}:{mr['fee_type_id']}:{mr['period']}", f"room:{mr['room_id']}:{mr['fee_type_id']}:{mr['period']}"):
                    meter_map[key] = consumption
                detail = {
                    'fee_id': mr['fee_type_id'],
                    'fee_name': mr['fee_name'] or '',
                    'consumption': consumption,
                }
                for detail_key in (f"{mr['room_id']}:{mr['period']}", f"room:{mr['room_id']}:{mr['period']}"):
                    meter_detail_map.setdefault(detail_key, []).append(detail)
        contract_where = (
            "c.status='active' AND (c.commercial_space_id IS NOT NULL OR r.unit='商场' OR r.building='商场')"
            if mode == 'commercial'
            else "c.status='active' AND (r.unit='B座' OR r.building='B座')"
        )
        contracts = db.execute(
            f"""SELECT c.id,c.room_id,c.commercial_space_id,c.contract_no,c.merchant_name,c.shop_name,c.property_rate,c.property_cycle,
                          COALESCE(s.space_no,r.room_number,'') object_no,
                          COALESCE(NULLIF(c.building_area,0),NULLIF(c.contract_area,0),s.area,r.area,0) area,
                          COALESCE(s.floor,r.floor,1) floor,
                          COALESCE(s.water_rate_type,r.water_rate_type,'非居民') water_rate_type,
                          COALESCE(r.category,'商户') category
                   FROM merchant_contracts c
                   LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
                   LEFT JOIN rooms r ON c.room_id=r.id
                   WHERE {contract_where} ORDER BY c.start_date DESC,c.id DESC"""
        ).fetchall()
        space_ids = [c['commercial_space_id'] for c in contracts if c['commercial_space_id']]
        if space_ids:
            placeholders = ','.join('?' for _ in space_ids)
            space_meter_rows = db.execute(
                f"""SELECT m.commercial_space_id,m.fee_type_id,m.period,COALESCE(SUM(m.consumption),0) consumption,
                           f.name fee_name
                    FROM meter_readings m
                    LEFT JOIN fee_types f ON m.fee_type_id=f.id
                    WHERE m.status='confirmed' AND m.commercial_space_id IN ({placeholders})
                    GROUP BY m.commercial_space_id,m.fee_type_id,m.period,f.name""",
                space_ids,
            ).fetchall()
            for mr in space_meter_rows:
                consumption = float(mr['consumption'] or 0)
                meter_map[f"space:{mr['commercial_space_id']}:{mr['fee_type_id']}:{mr['period']}"] = consumption
                meter_detail_map.setdefault(f"space:{mr['commercial_space_id']}:{mr['period']}", []).append({
                    'fee_id': mr['fee_type_id'],
                    'fee_name': mr['fee_name'] or '',
                    'consumption': consumption,
                })
        db.close()

        elevator_json = json.dumps(elevator_list, ensure_ascii=False)
        owner_json = json.dumps(tenant_rooms, ensure_ascii=False)
        meter_json = json.dumps(meter_map, ensure_ascii=False)
        meter_detail_json = json.dumps(meter_detail_map, ensure_ascii=False)

        # 房间下拉选项：按房间管理里的“单元/区域”字段分组，适配住宅、商业、写字楼等通用项目。
        groups = []
        by_unit = {}
        for r in rooms:
            unit_key = r["unit"] or "未分单元"
            if unit_key not in by_unit:
                by_unit[unit_key] = []
                groups.append(unit_key)
            by_unit[unit_key].append(r)

        opt_parts = []
        for unit_key in groups:
            group_label = f"兼容房间 · {unit_key}" if mode == 'commercial' else unit_key
            opt_parts.append(f'<optgroup label="{h(group_label)}">')
            for r in by_unit[unit_key]:
                opt_parts.append(
                    '<option value="{}" data-meter-target="room:{}" data-cat="{}" data-water="{}" data-area="{}" data-floor="{}" data-owner="{}" data-tenant-key="{}" data-rate="{}" data-cycle="{}">'
                    '{}-{}-{}{} ({})</option>'.format(
                        r["id"], r["id"], h(r["category"] or ""), h(r["water_rate_type"] or "非居民"), r["area"], r["floor"] or 1, r["owner_id"] or "",
                        h(_tenant_group_key(r)), r["custom_rate"] or "", h(r["payment_cycle"] or "monthly"),
                        h(r["building"]), h(r["unit"]), h(r["room_number"]), (" / " + h(r["shop_name"])) if r["shop_name"] else "", h(r["oname"] or "")
                    )
                )
            opt_parts.append('</optgroup>')
        opts = ''.join(opt_parts)
        if contracts:
            contract_label = '商业合同' if mode == 'commercial' else '物业合同'
            contract_opts = [f'<optgroup label="{contract_label}">']
            for c in contracts:
                target_kind = 'space' if c['commercial_space_id'] else 'room'
                target_id = c['commercial_space_id'] or c['room_id'] or ''
                contract_opts.append(
                    '<option value="contract:{}" data-contract-id="{}" data-room-id="{}" data-space-id="{}" data-meter-target="{}:{}" data-cat="{}" data-water="{}" data-area="{}" data-floor="{}" data-owner="" data-tenant-key="" data-rate="{}" data-cycle="{}">'
                    '{} {} / {} / {} ({})</option>'.format(
                        c['id'], c['id'], c['room_id'] or '', c['commercial_space_id'] or '', target_kind, target_id,
                        h(c['category'] or '商户'), h(c['water_rate_type'] or '非居民'), c['area'] or 0, c['floor'] or 1, c['property_rate'] or 0, h(c['property_cycle'] or 'monthly'),
                        contract_label,
                        h(c['contract_no']), h(c['object_no'] or ''), h(c['shop_name'] or c['merchant_name'] or ''), h(c['merchant_name'] or '')
                    )
                )
            contract_opts.append('</optgroup>')
            opts = ''.join(contract_opts) + opts

        # 过滤费用类型
        fts = [f for f in all_fts if fee_in_scope(f, mode)]

        fee_html = ''
        if fts:
            rows = ''.join(
                f'''<tr class="fee-row" data-ft="{f["id"]}" data-method="{f["calc_method"]}"
                        data-cycle="{h(f["billing_cycle"] or "monthly")}" data-price="{f["unit_price"]}" data-name="{h(f["name"])}">
                    <td style="width:40px"><input type="checkbox" class="fee-check" name="fee_types"
                        value="{f["id"]}" checked></td>
                    <td><span class="badge status-info">{h(f["name"])}</span></td>
                    <td class="text-muted small">{h(f["notes"] or "")}</td>
                    <td class="text-muted small" id="formula_{f["id"]}">-</td>
                    <td style="width:140px" class="text-end">
                        <input type="number" class="form-control form-control-sm text-end fee-amount money-cell"
                            name="custom_amount_{f["id"]}" id="feeAmt_{f["id"]}"
                            step="0.1" min="0" placeholder="auto"
                            style="width:120px;display:inline-block">
                    </td>
                </tr>'''
                for f in fts
            )
            fee_html = f'''
            <div class="card mb-2">
                <div class="card-header py-2">{title}项目</div>
                <table class="table table-hover mb-0"><tbody>{rows}</tbody></table>
            </div>'''

        today = date.today()
        default_start = today.replace(day=1).isoformat()
        # 默认截止日 = 3个月后
        if today.month + 3 > 12:
            end_m = today.month + 3 - 12
            end_y = today.year + 1
        else:
            end_m = today.month + 3
            end_y = today.year
        default_end = date(end_y, end_m, min(today.day, 28)).isoformat()

        tpl = self._load_template('billing.html')
        mode_note = '商业收费显示房间管理中单元/区域为商场的收费对象，并显示合同档案中的商业合同。' if mode == 'commercial' else '物业收费显示房间管理中 B座 的全部收费对象，并显示合同档案中的物业合同。'
        tpl = tpl.replace('{MODE_NOTE}', mode_note)
        tpl = tpl.replace('{OPTS}', opts)
        tpl = tpl.replace('{FEE_HTML}', fee_html or '<div class="text-center text-muted py-4">暂无费用类型</div>')
        tpl = tpl.replace('{ELEVATOR_DATA}', elevator_json)
        tpl = tpl.replace('{OWNER_DATA}', owner_json)
        tpl = tpl.replace('{METER_DATA}', meter_json)
        tpl = tpl.replace('{METER_DETAIL_DATA}', meter_detail_json)
        tpl = tpl.replace('{BILLING_MODE}', mode)
        tpl = tpl.replace('{PERIOD_START}', default_start)
        tpl = tpl.replace('{PERIOD_END}', default_end)
        self._html(self._page(title, tpl, active_tab))
