#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill printing (selected + batch)."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs
from server.base import BaseHandler
from server.print_helper import print_page, print_header_row
from datetime import datetime, date
import urllib.parse, csv, io

from server.print_helper import print_page, print_header_row


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
            pages = ''
            sn = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
            for i, b in enumerate(rows):
                info = ''.join(print_header_row(k, v) for k, v in [
                    ('房号', f'{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}'),
                    ('业主', h(b["oname"] or '-')),
                    ('费用项目', h(b["ft"])),
                    ('账期', h(b["billing_period"])),
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
            self._html(print_page('缴费单-选中', pages, back_url=back_url))
    
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
                info = ''.join(print_header_row(k, v) for k, v in [
                    ('房号', f'{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}'),
                    ('业主', h(b["oname"] or '-')),
                    ('电话', h(b["ophone"] or '-')),
                    ('费用项目', h(b["ft"])),
                    ('账期', h(b["billing_period"])),
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
    
