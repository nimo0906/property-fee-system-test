#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-module receipt (print + CSV)."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs
from server.base import BaseHandler
from server.print_helper import print_page, print_header_row
from datetime import datetime, date
import urllib.parse, csv, io

from server.print_helper import print_page, print_header_row

def _receipt_service_period(bill):
    if bill['source'] == 'auto_contract' and bill['service_start'] and bill['service_end']:
        return f'<br><small>自动出账服务期 {h(bill["service_start"])} 至 {h(bill["service_end"])}</small>'
    return ''


class BillReceiptMixin(BaseHandler):

        def _receipt_by_ids(self, d):
            """根据勾选的 bill_ids 生成多模块收据"""
            back_url = qs(d or {}, 'back', '/bills')
            if not (back_url.startswith('/bills') or back_url.startswith('/payments')):
                back_url = '/bills'
            raw = d.get('bill_ids', [])
            if isinstance(raw, str):
                raw = [raw]
            expanded = []
            for item in raw:
                expanded.extend(str(item).split(','))
            ids = []
            for x in expanded:
                cleaned = str(x).strip().strip('[]').strip().strip("'\"")
                if cleaned.isdigit():
                    ids.append(cleaned)
            if not ids:
                return self._redirect(back_url, '请勾选要生成收据的账单')
            placeholders = ','.join('?' * len(ids))
            db = get_db()
            bills = db.execute(f'''SELECT b.*,f.name ft,f.calc_method,f.unit_price,
                r.building,r.unit,r.room_number,r.area,r.owner_id,
                COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid,
                (SELECT payment_method FROM payments WHERE bill_id=b.id ORDER BY payment_date DESC,id DESC LIMIT 1) latest_method,
                (SELECT operator FROM payments WHERE bill_id=b.id ORDER BY payment_date DESC,id DESC LIMIT 1) latest_operator,
                (SELECT payment_date FROM payments WHERE bill_id=b.id ORDER BY payment_date DESC,id DESC LIMIT 1) latest_payment_date
                FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
                JOIN rooms r ON b.room_id=r.id
                WHERE b.id IN ({placeholders})
                ORDER BY f.sort_order''', ids).fetchall()
            if not bills:
                db.close()
                return self._redirect(back_url, '未找到账单')
            rm = bills[0]  # 取第一个房间的信息
            on = db.execute("SELECT name,phone FROM owners WHERE id=?", (rm['owner_id'],)).fetchone()
            db.close()
            owner_name = on['name'] if on else ''
            owner_phone = on['phone'] if on else ''
    
            period_set = sorted(set(b['billing_period'] for b in bills))
            period_label = f"{period_set[0]}~{period_set[-1]}" if len(period_set) > 1 else period_set[0]
            num_periods = len(period_set)
            operators = sorted({b['latest_operator'] for b in bills if b['latest_operator']})
            methods = sorted({b['latest_method'] for b in bills if b['latest_method']})
            pay_dates = sorted({b['latest_payment_date'] for b in bills if b['latest_payment_date']})
            operator_text = '、'.join(operators) if operators else '-'
            method_text = '、'.join(methods) if methods else '-'
            pay_date_text = f'{pay_dates[0]} ~ {pay_dates[-1]}' if len(pay_dates) > 1 else (pay_dates[0] if pay_dates else '-')
    
            rows_html = ''
            total_应收 = 0
            total_缴费 = 0
            total_欠费 = 0
            for b in bills:
                rem = b['amount'] - b['paid']
                area = b['area'] or 0
                cm = b['calc_method']
                if cm == 'area':
                    usage_str = f'{area}x{num_periods}' if num_periods > 1 else str(area)
                elif cm == 'floor':
                    usage_str = f'{area}x{num_periods}' if num_periods > 1 else str(area)
                elif cm == 'meter':
                    usage_str = '按抄表'
                elif cm == 'household':
                    usage_str = f'1x{num_periods}' if num_periods > 1 else '1'
                elif cm == 'fixed':
                    usage_str = '1'
                else:
                    usage_str = ''
                up = str(b['unit_price']) if b['unit_price'] else ''
                row_room = f'{b["building"]}-{b["unit"]}-{b["room_number"]}'
                rows_html += f'''<tr>
                    <td>{h(row_room)}</td>
                    <td>{h(b['ft'])}</td>
                    <td>{h(b['billing_period'])}{_receipt_service_period(b)}</td>
                    <td>{usage_str}</td>
                    <td>1</td>
                    <td class="amt">{up}</td>
                    <td class="amt">{m(b['amount'])}</td>
                    <td class="amt">{m(b['paid'])}</td>
                    <td class="amt">{m(rem)}</td>
                </tr>'''
                total_应收 += b['amount']
                total_缴费 += b['paid']
                total_欠费 += rem
    
            room_str = f"{h(rm['building'])}\\{h(rm['unit'])}\\{h(rm['room_number'])}"
            area_str = f"{rm['area']}m2"
            today_str = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
            content = f'''
            <h1>陕西金莎国际物业管理有限公司</h1>
            <h2 style="margin-top:0">收款收据</h2>
            <table class="header-info">
                <tr><td style="width:50%"><strong>套户编号：</strong>{room_str}</td>
                    <td><strong>客户名称：</strong>{h(owner_name)}</td></tr>
                <tr><td><strong>流水号：</strong>JS{datetime.now().strftime('%Y%m%d%H%M%S')}</td>
                    <td><strong>建筑面积：</strong>{area_str}</td></tr>
            </table>
            <table class="detail">
                <thead><tr>
                    <th style="width:16%">房间</th><th style="width:14%">收费项目</th><th style="width:14%">费用区间</th>
                    <th style="width:12%">使用量</th><th style="width:7%">系数</th>
                    <th style="width:9%">单价</th><th class="amt" style="width:10%">应收</th>
                    <th class="amt" style="width:10%">缴费</th><th class="amt" style="width:8%">欠费</th>
                </tr></thead>
                <tbody>
                    {rows_html}
                    <tr class="total-row">
                        <td colspan="6" style="text-align:right"><strong>缴费合计</strong></td>
                        <td class="amt"><strong>{m(total_应收)}</strong></td>
                        <td class="amt"><strong>{m(total_缴费)}</strong></td>
                        <td class="amt"><strong>{m(total_欠费)}</strong></td>
                    </tr>
                </tbody>
            </table>
            <table class="header-info" style="margin-top:10pt">
                <tr><td colspan="2"><strong>收据核对信息</strong></td></tr>
                <tr><td style="width:50%"><strong>收费员：</strong>{h(operator_text)}</td><td><strong>支付方式：</strong>{h(method_text)}</td></tr>
                <tr><td><strong>收款时间：</strong>{h(pay_date_text)}</td><td><strong>备注：</strong>请核对应收、缴费、欠费金额后再交付业主。</td></tr>
            </table>
            <table class="signature"><tr><td>收费员</td><td>财务审核</td><td>交款人签字</td></tr></table>
            <div style="text-align:center;margin-top:10pt;font-size:9pt;color:#666">打印日期：{today_str}</div>
            '''
            self._html(print_page(f'收款收据-{room_str}', content, back_url=back_url))
    
        def _receipt_setup(self, q):
            """收据设置页：选择房间和账期"""
            db = get_db()
            rooms = db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.building,r.room_number").fetchall()
            periods = db.execute("SELECT DISTINCT billing_period FROM bills ORDER BY billing_period DESC").fetchall()
            db.close()
            rm_opts = '<option value="">--选择房间--</option>' + ''.join(
                f'<option value="{r["id"]}">{h(r["building"])}-{h(r["room_number"])} ({h(r["oname"] or "")})</option>'
                for r in rooms
            )
            period_checks = ''.join(
                f'<div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" name="periods" value="{h(p["billing_period"])}" id="p{p["billing_period"]}"><label class="form-check-label" for="p{p["billing_period"]}">{h(p["billing_period"])}</label></div>'
                for p in periods
            ) if periods else '<p class="text-muted">暂无账单</p>'
            self._html(self._page('生成收据', f'''
            <div class="alert alert-info"><i class="bi bi-info-circle"></i> 选择房间和需要打印的账期，系统汇总后生成多模块收款收据。</div>
            <div class="row g-4">
            <div class="col-md-5">
            <div class="card">
            <div class="card-header">选择房间</div>
            <div class="card-body">
            <form id="receiptForm" target="_blank">
            <div class="mb-3"><label class="form-label">房间</label>
            <select class="form-select form-select-lg" id="receiptRoom" name="room_id" required onchange="loadPeriods(this.value)">{rm_opts}</select></div>
            <div id="periodSection" class="mb-3" style="display:none">
            <label class="form-label d-block">选择账期（可多选）</label>
            <div class="d-flex flex-wrap gap-1" id="periodChecks">{period_checks}</div>
            <small class="text-muted">勾选需要汇总的账期，留空则默认全部</small>
            </div>
            <hr>
            <div class="d-flex gap-2">
            <button type="button" class="btn btn-primary btn-lg" onclick="generateReceipt()"><i class="bi bi-printer"></i> 打印收据</button>
            <button type="button" class="btn btn-success btn-lg" onclick="exportReceipt()"><i class="bi bi-download"></i> 导出CSV</button>
            </div>
            </form>
            </div></div></div>
            <div class="col-md-7">
            <div class="card"><div class="card-header">收据预览说明</div>
            <div class="card-body">
            <p>多模块收款收据将所选账期的所有费用按收费项目汇总，格式如下：</p>
            <ul class="small">
            <li>同一收费项目跨多月时自动合并为一行</li>
            <li>使用量显示为：面积×月数（如 100×6）</li>
            <li>各费用类型独立分行展示，底部显示合计</li>
            <li>套户编号、客户名称、建筑面积自动填充</li>
            </ul>
            </div></div></div>
            </div>
            <script>
            function loadPeriods(roomId){{
                var ps = document.getElementById("periodSection");
                if(roomId) ps.style.display = "block";
                else ps.style.display = "none";
            }}
            function generateReceipt(){{
                var f = document.getElementById("receiptForm");
                var rid = f.room_id.value;
                if(!rid){{ alert("请选择房间"); return; }}
                var checks = f.querySelectorAll("input[name=periods]:checked");
                var params = "room_id=" + rid;
                checks.forEach(function(c){{ params += "&periods=" + c.value; }});
                if(checks.length === 0){{ params += "&all_periods=1"; }}
                window.open("/bills/receipt?" + params, "_blank");
            }}
            function exportReceipt(){{
                var f = document.getElementById("receiptForm");
                var rid = f.room_id.value;
                if(!rid){{ alert("请选择房间"); return; }}
                var checks = f.querySelectorAll("input[name=periods]:checked");
                var params = "room_id=" + rid;
                checks.forEach(function(c){{ params += "&periods=" + c.value; }});
                if(checks.length === 0){{ params += "&all_periods=1"; }}
                window.open("/bills/export_receipt?" + params, "_blank");
            }}
            </script>
            ''', 'bills'))
    
        def _bill_receipt(self, q):
            """多模块收款收据：一个房间所选账期的所有费用汇总展示"""
            room_id = qs(q, 'room_id', '')
            periods_raw = q.get('periods', [])
            all_periods = qs(q, 'all_periods', '')
            single_period = qs(q, 'period', '')  # 兼容单账期参数
            if isinstance(periods_raw, str):
                periods_raw = [periods_raw]
            if single_period and not periods_raw:
                periods_raw = [single_period]
            if not room_id:
                return self._redirect('/bills?flash=请指定房间')
            db = get_db()
            rm = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
            if not rm:
                db.close()
                return self._error(404)
            # 如果未指定账期，取该房间所有账期
            if not periods_raw and not all_periods:
                db.close()
                return self._redirect('/bills/receipt_setup?flash=请选择账期')
            if all_periods or not periods_raw:
                rows = db.execute('''SELECT DISTINCT billing_period FROM bills WHERE room_id=? ORDER BY billing_period''', (room_id,)).fetchall()
                periods_raw = [r['billing_period'] for r in rows]
            # 查该房间所有选中账期的账单，按费用类型汇总
            placeholders = ','.join('?' * len(periods_raw))
            bills = db.execute(f'''SELECT b.*,f.name ft,f.calc_method,f.unit_price,
                COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
                WHERE b.room_id=? AND b.billing_period IN ({placeholders})
                ORDER BY f.sort_order, b.billing_period''', (room_id, *periods_raw)).fetchall()
            on = db.execute("SELECT name,phone FROM owners WHERE id=?", (rm['owner_id'],)).fetchone()
            db.close()
            owner_name = on['name'] if on else ''
            owner_phone = on['phone'] if on else ''
    
            # 按收费项目分组汇总
            from collections import OrderedDict
            fee_groups = OrderedDict()
            period_set = set()
            for b in bills:
                period_set.add(b['billing_period'])
                key = b['ft']
                if key not in fee_groups:
                    fee_groups[key] = {'name': key, 'total': 0, 'paid': 0, 'unit_price': b['unit_price'], 'calc_method': b['calc_method'], 'count': 0}
                fee_groups[key]['total'] += b['amount']
                fee_groups[key]['paid'] += b['paid']
                fee_groups[key]['count'] += 1
            num_periods = len(period_set)
            period_label = f"{min(period_set)}~{max(period_set)}" if num_periods > 1 else (list(period_set)[0] if period_set else '')
    
            rows_html = ''
            total_应收 = 0
            total_缴费 = 0
            total_欠费 = 0
            for key, g in fee_groups.items():
                rem = g['total'] - g['paid']
                cm = g['calc_method']
                area = rm['area'] or 0
                if cm == 'area':
                    usage_str = f'{area}x{num_periods}' if num_periods > 1 else f'{area}'
                    coeff_display = '1'
                elif cm == 'floor':
                    usage_str = f'{area}x{num_periods}' if num_periods > 1 else f'{area}'
                    coeff_display = '1'
                elif cm == 'meter':
                    usage_str = '按抄表'
                    coeff_display = '-'
                elif cm == 'household':
                    usage_str = f'1x{num_periods}' if num_periods > 1 else '1'
                    coeff_display = '1'
                elif cm == 'fixed':
                    usage_str = str(g['count'])
                    coeff_display = '1'
                else:
                    usage_str = ''
                    coeff_display = '1'
                up_display = str(g['unit_price']) if g['unit_price'] else ''
                rows_html += f'''<tr>
                    <td>{h(key)}</td>
                    <td>{h(period_label)}</td>
                    <td>{usage_str}</td>
                    <td>{coeff_display}</td>
                    <td class="amt">{up_display}</td>
                    <td class="amt">{m(g['total'])}</td>
                    <td class="amt">{m(g['paid'])}</td>
                    <td class="amt">{m(rem)}</td>
                </tr>'''
                total_应收 += g['total']
                total_缴费 += g['paid']
                total_欠费 += rem
    
            room_str = f"{h(rm['building'])}\\{h(rm['unit'])}\\{h(rm['room_number'])}"
            area_str = f"{rm['area']}m2"
            today_str = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
    
            content = f'''
            <h1>陕西金莎国际物业管理有限公司</h1>
            <h2 style="margin-top:0">收款收据</h2>
            <table class="header-info">
                <tr><td style="width:50%"><strong>套户编号：</strong>{room_str}</td>
                    <td><strong>客户名称：</strong>{h(owner_name)}</td></tr>
                <tr><td><strong>流水号：</strong>JS{datetime.now().strftime('%Y%m%d%H%M%S')}</td>
                    <td><strong>建筑面积：</strong>{area_str}</td></tr>
            </table>
            <table class="detail">
                <thead><tr>
                    <th style="width:16%">收费项目</th>
                    <th style="width:16%">费用区间</th>
                    <th style="width:14%">使用量</th>
                    <th style="width:8%">系数</th>
                    <th style="width:10%">单价</th>
                    <th class="amt" style="width:12%">应收</th>
                    <th class="amt" style="width:12%">缴费</th>
                    <th class="amt" style="width:12%">欠费</th>
                </tr></thead>
                <tbody>
                    {rows_html}
                    <tr class="total-row">
                        <td colspan="6" style="text-align:right"><strong>缴费合计</strong></td>
                        <td class="amt"><strong>{m(total_应收)}</strong></td>
                        <td class="amt"><strong>{m(total_缴费)}</strong></td>
                        <td class="amt"><strong>{m(total_欠费)}</strong></td>
                    </tr>
                </tbody>
            </table>
            <table class="header-info" style="margin-top:10pt">
                <tr><td colspan="2"><strong>收据核对信息</strong></td></tr>
                <tr><td style="width:50%"><strong>收费员：</strong>{h(operator_text)}</td><td><strong>支付方式：</strong>{h(method_text)}</td></tr>
                <tr><td><strong>收款时间：</strong>{h(pay_date_text)}</td><td><strong>备注：</strong>请核对应收、缴费、欠费金额后再交付业主。</td></tr>
            </table>
            <table class="signature">
                <tr><td>收费员</td><td>财务审核</td><td>交款人签字</td></tr>
            </table>
            <div style="text-align:center;margin-top:10pt;font-size:9pt;color:#666">
                打印日期：{today_str}
            </div>
            '''
            self._html(print_page(f'收款收据-{room_str}', content, back_url=f'/bills?period={period_label}'))
    
