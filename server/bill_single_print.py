#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single bill print page."""

from server.db import get_db, h, m
from server.print_helper import print_page, print_header_row
from server.bill_receipt_shared import _receipt_period_label


class BillSinglePrintMixin:
    def _bill_print(self, bid):
        db = get_db()
        b = db.execute('''SELECT b.*,r.building,r.unit,r.room_number,r.area,r.floor,r.category,o.name oname,o.phone ophone,f.name ft,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE b.id=?''', (bid,)).fetchone()
        pays = db.execute("SELECT * FROM payments WHERE bill_id=? ORDER BY payment_date", (bid,)).fetchall()
        db.close()
        if not b:
            return self._error(404)
        rem = b['amount'] - b['paid']
        sn = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
        pay_rows = ''.join(
            f'<tr><td>{h((p["payment_date"] or "")[:10])}</td><td class="amt">¥{m(p["amount_paid"])}</td>'
            f'<td>{h(p["payment_method"])}</td><td>{h(p["operator"] or "-")}</td></tr>'
            for p in pays)
        info = ''.join(print_header_row(k, v) for k, v in [
            ('房号', f'{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}'),
            ('业主', h(b["oname"] or '-')),
            ('电话', h(b["ophone"] or '-')),
            ('费用项目', h(b["ft"])),
            ('账期', h(_receipt_period_label(b))),
            ('面积', f'{b["area"] or "-"} m2'),
            ('票据号', h(b["bill_number"] or '-')),
            ('截止日', h(b["due_date"] or '-')),
        ])
        pay_section = ''
        if pay_rows:
            pay_section = f'''
            <h3 style="margin-top:14pt;font-size:12pt">缴费记录</h3>
            <table class="detail"><thead><tr><th>日期</th><th class="amt">金额</th><th>方式</th><th>经手人</th></tr></thead>
            <tbody>{pay_rows}</tbody></table>'''
        content = f'''
        <h1>物业管理缴费单</h1>
        <table class="header-info">{info}</table>
        <div class="amount-box">
            <div class="label">应缴金额</div>
            <div class="number">¥{m(b["amount"])}</div>
            <div style="margin-top:6pt;font-size:10pt;color:#666">
                已缴：¥{m(b["paid"])} | 欠费：<strong>¥{m(rem)}</strong> | 状态：{sn.get(b["status"], b["status"])}
            </div>
        </div>
        {pay_section}
        <table class="signature"><tr><td>业主签字</td><td>收费员签字</td><td>物业盖章</td></tr></table>
        '''
        self._html(print_page(f'缴费单 #{b["id"]}', content, back_url=f'/bills/{bid}'))

