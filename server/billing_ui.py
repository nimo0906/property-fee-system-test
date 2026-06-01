#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified billing pages: property billing and commercial billing."""

from server.db import get_db, get_period, update_overdue_bills, h, m, qs
from server.base import BaseHandler
from datetime import date
import json

PROPERTY_FEE_NAMES = {
    '物业费(居民)', '物业费(商户)', '电梯费', '二次供水运行费',
    '水费(非居民)', '水费(特行)', '公摊能耗费', '生活垃圾费',
}
COMMERCIAL_FEE_NAMES = {
    '物业费(商业)', '电费(商业)', '水费(商业)', '垃圾清运费',
    '装修管理费', '装修押金', '泄水费', '空调能源费', '空调费(商业)',
}
WATER_FEE_NAMES = {'水费(非居民)', '水费(特行)'}


def _is_property_fee(fee):
    name = fee['name'] or ''
    return name in PROPERTY_FEE_NAMES or ((fee['sort_order'] or 0) < 30 and name not in COMMERCIAL_FEE_NAMES)


def _is_commercial_fee(fee):
    name = fee['name'] or ''
    return name in COMMERCIAL_FEE_NAMES or name in WATER_FEE_NAMES or ((fee['sort_order'] or 0) >= 30 and name not in PROPERTY_FEE_NAMES)


class BillingUiMixin(BaseHandler):

    def _billing(self):
        """物业收费：只显示金莎物业收费项目 (sort_order < 30)"""
        return self._render_billing(mode='property', active_tab='billing',
                                    title='物业收费', exclude_commercial=True)

    def _commercial_billing(self):
        """商业收费：显示商业项目，并纳入所有商户需要的水费档位。"""
        return self._render_billing(mode='commercial', active_tab='commercial_billing',
                                    title='商业收费', exclude_commercial=False)

    def _render_billing(self, mode, active_tab, title, exclude_commercial):
        """渲染收费页面，按 mode 过滤费用类型."""
        update_overdue_bills()
        db = get_db()
        room_sql = "SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id"
        if mode == 'commercial':
            room_sql += " WHERE r.unit='商场' AND r.category IN ('商户','商业')"
        rooms = db.execute(room_sql + " ORDER BY r.building,r.unit,r.room_number").fetchall()
        all_fts = db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order").fetchall()
        elevator_rows = db.execute("SELECT * FROM elevator_fee_tiers ORDER BY floor_from").fetchall()
        elevator_list = [{'floor_from': e['floor_from'], 'floor_to': e['floor_to'], 'rate': e['rate']}
                         for e in elevator_rows]
        owner_rooms = {}
        for r in rooms:
            oid = r['owner_id']
            if oid:
                sok = str(oid)
                if sok not in owner_rooms:
                    owner_rooms[sok] = []
                if mode != 'commercial' or (r['category'] or '') in ('商户','商业'):
                    owner_rooms[sok].append({
                        'id': r['id'],
                        'name': f"{r['building']}-{r['unit']}-{r['room_number']}",
                        'cat': r['category'] or '',
                        'area': r['area'],
                        'floor': r['floor'] or '1',
                        'water': r['water_rate_type'] or '非居民',
                        'rate': r['custom_rate'] or '',
                        'cycle': r['payment_cycle'] or 'monthly'
                    })
        db.close()

        elevator_json = json.dumps(elevator_list, ensure_ascii=False)
        owner_json = json.dumps(owner_rooms, ensure_ascii=False)

        # 房间下拉选项：按房间管理里的“单元”字段分组，便于区分 A座/B座/商场等。
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
            opt_parts.append(f'<optgroup label="{h(unit_key)}">')
            for r in by_unit[unit_key]:
                opt_parts.append(
                    '<option value="{}" data-cat="{}" data-water="{}" data-area="{}" data-floor="{}" data-owner="{}" data-rate="{}" data-cycle="{}">'
                    '{}-{}-{}{} ({})</option>'.format(
                        r["id"], h(r["category"] or ""), h(r["water_rate_type"] or "非居民"), r["area"], r["floor"] or 1, r["owner_id"] or "",
                        r["custom_rate"] or "", h(r["payment_cycle"] or "monthly"),
                        h(r["building"]), h(r["unit"]), h(r["room_number"]), (" / " + h(r["shop_name"])) if r["shop_name"] else "", h(r["oname"] or "")
                    )
                )
            opt_parts.append('</optgroup>')
        opts = ''.join(opt_parts)

        # 过滤费用类型
        if exclude_commercial:
            fts = [f for f in all_fts if _is_property_fee(f)]
        else:
            fts = [f for f in all_fts if _is_commercial_fee(f)]

        fee_html = ''
        if fts:
            rows = ''.join(
                f'''<tr class="fee-row" data-ft="{f["id"]}" data-method="{f["calc_method"]}"
                        data-price="{f["unit_price"]}" data-name="{h(f["name"])}">
                    <td style="width:40px"><input type="checkbox" class="fee-check" name="fee_types"
                        value="{f["id"]}" checked></td>
                    <td><span class="badge status-info">{h(f["name"])}</span></td>
                    <td class="text-muted small">{h(f["notes"] or "")}</td>
                    <td class="text-muted small" id="formula_{f["id"]}">-</td>
                    <td style="width:140px" class="text-end">
                        <input type="number" class="form-control form-control-sm text-end fee-amount money-cell"
                            name="custom_amount_{f["id"]}" id="feeAmt_{f["id"]}"
                            step="0.01" min="0" placeholder="auto"
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
        mode_note = '仅显示单元/区域为商场且房间类型为商户/商业的收费对象；A座独立运行不纳入，B座住宅不纳入。非居民/特行只是水费档位。' if mode == 'commercial' else '物业收费用于居民及物业基础收费。'
        tpl = tpl.replace('{MODE_NOTE}', mode_note)
        tpl = tpl.replace('{OPTS}', opts)
        tpl = tpl.replace('{FEE_HTML}', fee_html or '<div class="text-center text-muted py-4">暂无费用类型</div>')
        tpl = tpl.replace('{ELEVATOR_DATA}', elevator_json)
        tpl = tpl.replace('{OWNER_DATA}', owner_json)
        tpl = tpl.replace('{PERIOD_START}', default_start)
        tpl = tpl.replace('{PERIOD_END}', default_end)
        self._html(self._page(title, tpl, active_tab))
