#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill export (CSV)."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs
from server.base import BaseHandler
from server.print_helper import print_page, print_header_row
from server.billing_periods import append_period_filter
from datetime import datetime, date
import urllib.parse, csv, io
from server.print_helper import print_page, print_header_row


class BillExportMixin(BaseHandler):

        def _bill_export(self):
            """导出账单明细为CSV文件（Excel可直接打开）"""
            db=get_db()
            p=self.path
            q=urllib.parse.parse_qs(urllib.parse.urlparse(p).query)
            period=qs(q,'period',get_period());s=qs(q,'status');fid=qs(q,'fee_type_id')
            bld=qs(q,'building');cat=qs(q,'category')
            sql='''SELECT b.*,r.building,r.unit,r.room_number,r.category,f.name ft,o.name owner_name,o.phone owner_phone,
                   COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                   FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
                   LEFT JOIN fee_types f ON b.fee_type_id=f.id
                   LEFT JOIN owners o ON b.owner_id=o.id WHERE 1=1'''
            vals=[]
            if period:
                sql, vals = append_period_filter(sql, vals, period, 'b.billing_period')
            if s:sql+=" AND b.status=?";vals.append(s)
            if fid:sql+=" AND b.fee_type_id=?";vals.append(fid)
            if bld:sql+=" AND r.building=?";vals.append(bld)
            if cat:sql+=" AND r.category=?";vals.append(cat)
            sql+=" ORDER BY r.building,r.room_number,b.fee_type_id"
            rows=db.execute(sql,vals).fetchall()
            db.close()
            buf=io.StringIO()
            w=csv.writer(buf)
            w.writerow(['票据编号','楼栋','房号','业主','电话','类别','费用类型','账期','金额','已缴','欠费','状态','截止日'])
            sn={'paid':'已缴','unpaid':'未缴','overdue':'逾期','partial':'部分缴'}
            for r in rows:
                rem=r['amount']-r['paid']
                w.writerow([
                    r['bill_number'] or '', f"{r['building'] or ''}-{r['unit'] or ''}", r['room_number'] or '',
                    r['owner_name'] or '', r['owner_phone'] or '', r['category'] or '',
                    r['ft'] or '', r['billing_period'], r['amount'], r['paid'],
                    round(rem,2), sn.get(r['status'],r['status']), r['due_date'] or ''
                ])
            csv_data=buf.getvalue()
            self.send_response(200)
            self.send_header('Content-Type','text/csv; charset=utf-8-sig')
            self.send_header('Content-Disposition',f'attachment; filename="bill_{period}.csv"')
            self.send_header('Content-Length',str(len(csv_data.encode('utf-8-sig'))))
            self.end_headers()
            self.wfile.write(csv_data.encode('utf-8-sig'))
    

        def _bill_export_generated(self, q):
            ids_raw = qs(q, 'ids', '')
            ids = [x for x in ids_raw.split(',') if x.strip().isdigit()]
            if not ids:
                return self._redirect('/bills?flash=缺少导出账单')
            placeholders = ','.join('?' * len(ids))
            db = get_db()
            sql = f'''SELECT b.*,r.building,r.unit,r.room_number,r.category,f.name ft,o.name owner_name,o.phone owner_phone,
                COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
                LEFT JOIN fee_types f ON b.fee_type_id=f.id
                LEFT JOIN owners o ON b.owner_id=o.id
                WHERE b.id IN ({placeholders}) ORDER BY r.building,r.room_number'''
            rows = db.execute(sql, ids).fetchall()
            db.close()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(['票据编号','楼栋','房号','业主','电话','类别','费用类型','账期','金额','已缴','欠费','状态','截止日'])
            sn = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
            for r in rows:
                rem = r['amount'] - r['paid']
                w.writerow([
                    r['bill_number'] or '', f"{r['building'] or ''}-{r['unit'] or ''}", r['room_number'] or '',
                    r['owner_name'] or '', r['owner_phone'] or '', r['category'] or '',
                    r['ft'] or '', r['billing_period'], r['amount'], r['paid'],
                    round(rem, 2), sn.get(r['status'], r['status']), r['due_date'] or ''
                ])
            csv_data = buf.getvalue()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8-sig')
            self.send_header('Content-Disposition', f'attachment; filename="bill_generated_{ts}.csv"')
            self.send_header('Content-Length', str(len(csv_data.encode('utf-8-sig'))))
            self.end_headers()
            self.wfile.write(csv_data.encode('utf-8-sig'))

        def _export_selected(self, d):
            """导出选中的账单"""
            raw = d.get('bill_ids', [])
            if isinstance(raw, str):
                raw = [raw]
            ids = [x for x in raw if x.strip()]
            if not ids:
                return self._redirect('/bills?flash=请勾选要导出的账单')
            placeholders = ','.join('?' * len(ids))
            db = get_db()
            sql = f'''SELECT b.*,r.building,r.unit,r.room_number,r.category,f.name ft,o.name owner_name,o.phone owner_phone,
                COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
                LEFT JOIN fee_types f ON b.fee_type_id=f.id
                LEFT JOIN owners o ON b.owner_id=o.id
                WHERE b.id IN ({placeholders}) ORDER BY r.building,r.room_number'''
            rows = db.execute(sql, ids).fetchall()
            db.close()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(['票据编号','楼栋','房号','业主','电话','类别','费用类型','账期','金额','已缴','欠费','状态','截止日'])
            sn = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
            for r in rows:
                rem = r['amount'] - r['paid']
                w.writerow([
                    r['bill_number'] or '', f"{r['building'] or ''}-{r['unit'] or ''}", r['room_number'] or '',
                    r['owner_name'] or '', r['owner_phone'] or '', r['category'] or '',
                    r['ft'] or '', r['billing_period'], r['amount'], r['paid'],
                    round(rem, 2), sn.get(r['status'], r['status']), r['due_date'] or ''
                ])
            csv_data = buf.getvalue()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8-sig')
            self.send_header('Content-Disposition', f'attachment; filename="bill_selected_{ts}.csv"')
            self.send_header('Content-Length', str(len(csv_data.encode('utf-8-sig'))))
            self.end_headers()
            self.wfile.write(csv_data.encode('utf-8-sig'))
    
        def _export_receipt(self, q):
            """导出多模块收据为CSV（支持多账期）"""
            room_id = qs(q, 'room_id', '')
            periods_raw = q.get('periods', [])
            all_periods = qs(q, 'all_periods', '')
            if isinstance(periods_raw, str):
                periods_raw = [periods_raw]
            if not room_id:
                return self._redirect('/bills?flash=请指定房间')
            db = get_db()
            rm = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
            if not rm:
                db.close()
                return self._error(404)
            if all_periods or not periods_raw:
                rows = db.execute("SELECT DISTINCT billing_period FROM bills WHERE room_id=? ORDER BY billing_period", (room_id,)).fetchall()
                periods_raw = [r['billing_period'] for r in rows]
            if not periods_raw:
                db.close()
                return self._redirect('/bills?flash=该房间无账单')
            placeholders = ','.join('?' * len(periods_raw))
            bills = db.execute(f'''SELECT b.*,f.name ft,f.calc_method,
                COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
                WHERE b.room_id=? AND b.billing_period IN ({placeholders})
                ORDER BY f.sort_order''', (room_id, *periods_raw)).fetchall()
            db.close()
    
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(['收费项目', '费用区间', '单价', '应收', '已缴', '欠费', '状态'])
            total_amt = 0
            total_paid = 0
            for b in bills:
                rem = b['amount'] - b['paid']
                sn = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
                w.writerow([b['ft'], b['billing_period'], b['unit_price'], b['amount'], b['paid'], round(rem, 2), sn.get(b['status'], b['status'])])
                total_amt += b['amount']
                total_paid += b['paid']
            w.writerow(['合计', '', '', round(total_amt, 2), round(total_paid, 2), round(total_amt - total_paid, 2), ''])
            csv_data = buf.getvalue()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            label = '-'.join(periods_raw) if len(periods_raw) <= 3 else f'{periods_raw[0]}-{periods_raw[-1]}'
            safe_label = label.replace('~', '-')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8-sig')
            self.send_header('Content-Disposition', f'attachment; filename="receipt_{room_id}_{safe_label}_{ts}.csv"')
            self.send_header('Content-Length', str(len(csv_data.encode('utf-8-sig'))))
            self.end_headers()
            self.wfile.write(csv_data.encode('utf-8-sig'))
