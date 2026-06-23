#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill printing (selected + batch)."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs
from server.base import BaseHandler
from server.print_helper import print_page, print_header_row
from server.bill_receipt_shared import _receipt_period_label
from datetime import datetime, date
import urllib.parse, csv, io

def _service_period_text(bill):
    if bill['source'] == 'auto_contract' and bill['service_start'] and bill['service_end']:
        return f'<br><small>自动出账服务期 {h(bill["service_start"])} 至 {h(bill["service_end"])}</small>'
    return ''

def _combined_bill_print_html(rows):
    status_names = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
    first = rows[0]
    room_names = sorted({
        f'{r["building"] or ""}-{r["unit"] or ""}-{r["room_number"] or ""}' for r in rows
    })
    owner_names = sorted({r['oname'] or '-' for r in rows})
    periods = sorted({_receipt_period_label(r) or '-' for r in rows})
    total = sum(float(r['amount'] or 0) for r in rows)

    info = ''.join(print_header_row(k, v) for k, v in [
        ('房间', h('、'.join(room_names))),
        ('业主', h('、'.join(owner_names))),
        ('电话', h(first['ophone'] or '-')),
        ('账期', h('、'.join(periods))),
        ('账单数量', f'{len(rows)} 笔'),
        ('打印方式', '选中账单合并打印'),
    ])

    detail_rows = []
    for index, bill in enumerate(rows, 1):
        room_name = f'{bill["building"] or ""}-{bill["unit"] or ""}-{bill["room_number"] or ""}'
        detail_rows.append(f'''
            <tr>
                <td>{index}</td>
                <td>{h(bill['bill_number'] or '-')}</td>
                <td>{h(room_name)}</td>
                <td>{h(bill['ft'] or '-')}</td>
                <td>{h(_receipt_period_label(bill) or '-')}{_service_period_text(bill)}</td>
                <td class="amt">¥{m(bill['amount'])}</td>
                <td>{status_names.get(bill['status'], h(bill['status'] or '-'))}</td>
            </tr>
        ''')

    return f'''
        <h1>物业管理缴费单</h1>
        <h2>选中账单合并打印</h2>
        <table class="header-info">{info}</table>
        <table class="detail">
            <thead>
                <tr>
                    <th>序号</th><th>票据号</th><th>房间</th><th>费用项目</th>
                    <th>账期</th><th>金额</th><th>状态</th>
                </tr>
            </thead>
            <tbody>
                {''.join(detail_rows)}
                <tr class="total-row">
                    <td colspan="5">合计应缴</td>
                    <td class="amt">¥{m(total)}</td>
                    <td></td>
                </tr>
            </tbody>
        </table>
        <div class="amount-box">
            <div class="label">合计应缴</div>
            <div class="number">¥{m(total)}</div>
        </div>
        <table class="signature"><tr><td>业主签字</td><td>收费员签字</td><td>物业盖章</td></tr></table>
    '''


class BillPrintMixin(BaseHandler):

        def _print_selected(self, d):
            """打印选中账单"""
            back_url = qs(d or {}, 'back', '/bills')
            if not back_url.startswith('/bills'):
                back_url = '/bills'
            raw = d.get('bill_ids', [])
            if isinstance(raw, str):
                raw = [raw]
            ids = [x for x in raw if x.strip()]
            if not ids:
                return self._redirect(back_url, '请勾选要打印的账单')
            placeholders = ','.join('?' * len(ids))
            db = get_db()
            rows = db.execute(f'''SELECT b.*,r.building,r.unit,r.room_number,r.area,o.name oname,o.phone ophone,f.name ft
                FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
                LEFT JOIN owners o ON b.owner_id=o.id
                LEFT JOIN fee_types f ON b.fee_type_id=f.id
                WHERE b.id IN ({placeholders})
                ORDER BY o.name,r.building,r.room_number,f.sort_order''', ids).fetchall()
            db.close()
            if not rows:
                return self._redirect(back_url, '未找到账单')
            self._html(print_page('缴费单-选中', _combined_bill_print_html(rows), back_url=back_url))
    
        def _bill_print_batch(self, q):
            """批量打印账单"""
            period = qs(q, 'period', get_period())
            s = qs(q, 'status', '')
            db = get_db()
            sql = '''SELECT b.*,r.building,r.unit,r.room_number,r.area,o.name oname,o.phone ophone,f.name ft
                FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
                LEFT JOIN owners o ON b.owner_id=o.id
                LEFT JOIN fee_types f ON b.fee_type_id=f.id
                WHERE b.billing_period=?'''
            vals = [period]
            if s:
                sql += ' AND b.status=?'
                vals.append(s)
            sql += ' ORDER BY o.name,r.building,r.room_number,f.sort_order'
            rows = db.execute(sql, vals).fetchall()
            db.close()
            if not rows:
                return self._redirect(f'/bills?period={period}&flash=该账期没有账单')
            pages = ''
            sn = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
            for i, b in enumerate(rows):
                period = f'{h(_receipt_period_label(b))}{_service_period_text(b)}'
                info = ''.join(print_header_row(k, v) for k, v in [
                    ('房号', f'{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}'),
                    ('业主', h(b["oname"] or '-')),
                    ('电话', h(b["ophone"] or '-')),
                    ('费用项目', h(b["ft"])),
                    ('账期', period),
                    ('面积', f'{b["area"] or "-"} m2'),
                    ('票据号', h(b["bill_number"] or '-')),
                    ('截止日', h(b["due_date"] or '-')),
                ])
                pages += f'''
                <div class="page-break"></div>
                <h1>物业管理缴费单</h1>
                <table class="header-info">{info}</table>
                <div class="amount-box">
                    <div class="label">应缴金额</div>
                    <div class="number">¥{m(b["amount"])}</div>
                    <div style="margin-top:6pt;font-size:10pt;color:#666">
                        状态：{sn.get(b["status"], b["status"])}
                    </div>
                </div>
                <table class="signature"><tr><td>业主签字</td><td>收费员签字</td><td>物业盖章</td></tr></table>
                '''
                if i == 0:
                    pages = pages.replace('<div class="page-break"></div>', '')
            self._html(print_page(f'缴费单-{period}', pages, back_url=f'/bills?period={period}'))
    
