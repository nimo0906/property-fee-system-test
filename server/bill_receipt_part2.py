from server.bill_receipt_shared import *
from server.brand_config import RECEIPT_COMPANY_NAME, RECEIPT_SERIAL_PREFIX

class BillReceiptMixinPart2(BaseHandler):
        def _bill_receipt(self, q):
            """多模块收款收据：一个房间所选账期的所有费用汇总展示"""
            room_id = qs(q, 'room_id', '')
            periods_raw = q.get('periods', [])
            all_periods = qs(q, 'all_periods', '')
            single_period = qs(q, 'period', '')  # 兼容单账期参数
            period_start, period_end = _receipt_date_range(q)
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
            if not periods_raw and not all_periods and not (period_start and period_end):
                db.close()
                return self._redirect('/bills/receipt_setup?flash=请选择起始日期和截止日期')
            if period_start and period_end and not periods_raw and not all_periods:
                sql = '''SELECT b.*,f.name ft,f.calc_method,f.unit_price,
                    COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                    FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
                    WHERE b.room_id=?'''
                params = [room_id]
                sql, params = append_natural_date_range_filter(sql, params, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
                sql += ' ORDER BY f.sort_order, b.billing_period'
                bills = db.execute(sql, params).fetchall()
            elif all_periods or not periods_raw:
                rows = db.execute('''SELECT DISTINCT billing_period FROM bills WHERE room_id=? ORDER BY billing_period''', (room_id,)).fetchall()
                periods_raw = [r['billing_period'] for r in rows]
                placeholders = ','.join('?' * len(periods_raw))
                bills = db.execute(f'''SELECT b.*,f.name ft,f.calc_method,f.unit_price,
                    COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                    FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
                    WHERE b.room_id=? AND b.billing_period IN ({placeholders})
                    ORDER BY f.sort_order, b.billing_period''', (room_id, *periods_raw)).fetchall()
            else:
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
            operator_text = '-'
            method_text = '-'
            pay_date_text = '-'
    
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
            <h1>{h(RECEIPT_COMPANY_NAME)}</h1>
            <h2 style="margin-top:0">收款收据</h2>
            <table class="header-info">
                <tr><td style="width:50%"><strong>套户编号：</strong>{room_str}</td>
                    <td><strong>客户名称：</strong>{h(owner_name)}</td></tr>
                <tr><td><strong>流水号：</strong>{h(RECEIPT_SERIAL_PREFIX)}{datetime.now().strftime('%Y%m%d%H%M%S')}</td>
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
            self._html(print_page(f'收款收据-{room_str}', content, back_url=f'/bills?period={period_label}', body_class='receipt-print'))
