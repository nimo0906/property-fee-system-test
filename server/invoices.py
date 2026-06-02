#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Electronic invoice management."""

from server.db import get_db, get_period, h, m, qs, date_to_period, period_to_date
from server.invoice_requests import InvoiceRequestError, InvoiceRequestService
from server.base import BaseHandler
from datetime import date, datetime


class InvoiceMixin(BaseHandler):

    def _invoice_requests(self, q):
        status_filter = qs(q, 'status', '')
        filters = {'status': status_filter} if status_filter else {}
        requests = InvoiceRequestService().list_requests(filters)['items']
        status_options = '<option value="">全部状态</option>' + ''.join(
            f'<option value="{s}"{" selected" if status_filter == s else ""}>{s}</option>'
            for s in ['pending', 'submitted', 'issued', 'failed']
        )
        rows = ''
        for r in requests:
            rows += f'''<tr><td><small>{h(r["request_no"])}</small></td><td>{h(r["buyer_name"] or "-")}</td>
            <td class="text-end">¥{h(r["amount"])}</td><td><span class="badge bg-secondary">{h(r["status"])}</span></td>
            <td>{h(r["external_invoice_id"] or "-")}</td><td><form method="POST" action="/invoice_requests/{h(r["request_no"])}/status" class="d-flex gap-1">
            <select name="status" class="form-select form-select-sm"><option value="submitted">submitted</option><option value="issued">issued</option><option value="failed">failed</option></select>
            <input name="external_invoice_id" class="form-control form-control-sm" placeholder="外部票据号">
            <button class="btn btn-sm btn-primary">更新</button></form></td></tr>'''
        self._html(self._page('电子票据请求', f'''
        <div class="d-flex justify-content-between mb-3"><form method="GET" class="d-flex gap-2">
        <select name="status" class="form-select form-select-sm" onchange="this.form.submit()">{status_options}</select>
        <a href="/invoice_requests" class="btn btn-sm btn-outline-secondary">重置</a></form></div>
        <div class="card"><div class="card-header">电子票据请求</div><div class="table-responsive"><table class="table table-hover mb-0">
        <thead><tr><th>请求号</th><th>抬头</th><th class="text-end">金额</th><th>状态</th><th>外部票据号</th><th style="min-width:360px">操作</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="6" class="text-center text-muted py-3">暂无电子票据请求</td></tr>'}</tbody></table></div></div>
        ''', 'invoices'))

    def _invoice_request_status_post(self, request_no, d):
        try:
            InvoiceRequestService().update_status(request_no, {
                'status': qs(d, 'status'),
                'external_invoice_id': qs(d, 'external_invoice_id'),
                'failure_reason': qs(d, 'failure_reason'),
            })
            return self._redirect('/invoice_requests?flash=电子票据状态已更新')
        except InvoiceRequestError as exc:
            return self._redirect('/invoice_requests?flash=' + str(exc))

    def _invoices(self, q):
        db=get_db();p=date_to_period(qs(q,'period',get_period()))
        sql='''SELECT i.*,b.bill_number,b.billing_period,b.amount bill_amount,
            r.building,r.unit,r.room_number,o.name oname FROM invoices i
            LEFT JOIN bills b ON i.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id
            LEFT JOIN owners o ON b.owner_id=o.id
            WHERE b.billing_period=? ORDER BY i.id DESC'''
        rows=db.execute(sql,(p,)).fetchall()
        total=db.execute("SELECT COALESCE(SUM(i.amount),0) FROM invoices i JOIN bills b ON i.bill_id=b.id WHERE b.billing_period=?",(p,)).fetchone()[0]
        avail=db.execute('''SELECT b.id,b.bill_number,b.amount,b.billing_period,r.building,r.unit,r.room_number,o.name oname
            FROM bills b JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            WHERE b.billing_period=? AND b.status='paid' AND b.id NOT IN (SELECT bill_id FROM invoices)
            ORDER BY r.building,r.room_number''',(p,)).fetchall()
        db.close()
        rh=''
        for r in rows:
            rh+='<tr>'
            rh+='<td><small>'+h(r['invoice_number'] or '-')+'</small></td>'
            rh+='<td>'+h(r['building']or'')+'-'+h(r['unit']or'')+'-'+h(r['room_number']or'')+'</td>'
            rh+='<td>'+h(r['oname']or'-')+'</td>'
            rh+='<td class="text-end">¥'+m(r['amount'])+'</td>'
            rh+='<td>'+h(r['issue_date']or'-')+'</td>'
            rh+='<td><span class="badge bg-success">已开具</span></td>'
            rh+='<td><a href="/invoices/'+str(r['id'])+'/print" class="btn btn-sm btn-outline-info" target="_blank"><i class="bi bi-printer"></i></a> '
            rh+='<form method=POST action="/invoices/'+str(r['id'])+'/delete" style=display:inline><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'
        av_opts = '<option value="">--选择--</option>'
        for a in avail:
            av_opts += f'<option value="{a["id"]}">{h(a["building"])}-{h(a["room_number"])} {h(a["oname"])} ¥{m(a["amount"])}</option>'
        # Available bills for invoice
        self._html(self._page("发票管理", f'''
    <div class="d-flex flex-wrap justify-content-between mb-3 gap-2">
    <form class="row g-2" method=GET>
    <div class="col-auto"><input type="date" name="period" class="form-control form-control-sm" value="{period_to_date(p)}" onchange="this.form.submit()"></div>
    <div class="col-auto"><button class="btn btn-sm btn-outline-primary"><i class="bi bi-search"></i></button><a href="/invoices" class="btn btn-sm btn-outline-secondary"><i class="bi bi-x-circle"></i></a></div></form>
    </div>
    <div class="row g-4">
    <div class="col-md-8"><div class="card"><div class="card-header">发票列表 <small class="text-muted">({p})</small></div>
    <div class="card-body p-0"><table class="table table-hover mb-0"><thead><tr><th>发票号</th><th>房间</th><th>业主</th><th class="text-end">金额</th><th>开票日期</th><th>状态</th><th style="width:100px">操作</th></tr></thead>
    <tbody>{rh or '<tr><td colspan="7" class="text-center text-muted py-3">暂无发票</td></tr>'}</tbody></table></div></div></div>
    <div class="col-md-4"><div class="card"><div class="card-header">开具发票</div>
    <div class="card-body"><form method=POST action="/invoices/create" class="row g-3">
    <div class="col-12"><label>选择已缴费账单</label><select name="bill_id" class="form-select" required>{av_opts}</select></div>
    <div class="col-12"><label>开票日期</label><input name="issue_date" type="date" class="form-control" value="{date.today().isoformat()}"></div>
    <div class="col-12"><label>购买方名称</label><input name="buyer_name" class="form-control" placeholder="单位名称或个人姓名"></div>
    <div class="col-12"><label>纳税人识别号</label><input name="buyer_tax_id" class="form-control" placeholder="税号（选填）"></div>
    <div class="col-12"><hr><button class="btn btn-success"><i class="bi bi-receipt"></i> 开具发票</button></div>
    </form></div></div></div></div>''', "invoices"))

    def _invoice_create(self, d):
        db=get_db()
        bid=qs(d,'bill_id')
        if not bid: db.close(); return self._redirect('/invoices?flash=请选择账单')
        bill=db.execute("SELECT * FROM bills WHERE id=? AND status='paid'",(int(bid),)).fetchone()
        if not bill: db.close(); return self._redirect('/invoices?flash=账单未找到或未缴费')
        exist=db.execute("SELECT id FROM invoices WHERE bill_id=?",(int(bid),)).fetchone()
        if exist: db.close(); return self._redirect('/invoices?flash=该账单已开过发票')
        # Generate invoice number
        cnt=db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]+1
        inv_no=f"INV-{date.today().strftime('%Y%m%d')}-{cnt:04d}"
        db.execute("INSERT INTO invoices(bill_id,invoice_number,amount,issue_date,buyer_name,buyer_tax_id) VALUES(?,?,?,?,?,?)",
                   (int(bid),inv_no,bill['amount'],qs(d,'issue_date',date.today().isoformat()),qs(d,'buyer_name'),qs(d,'buyer_tax_id')))
        db.commit();db.close()
        self._redirect('/invoices?flash=发票开具成功: '+inv_no)

    def _invoice_print(self, iid):
        db=get_db()
        i=db.execute('''SELECT i.*,b.bill_number,b.billing_period,b.amount,b.due_date,
            r.building,r.unit,r.room_number,r.area,o.name oname,o.phone ophone,o.id_card oid_card
            FROM invoices i JOIN bills b ON i.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id WHERE i.id=?''',(iid,)).fetchone()
        db.close()
        if not i: return self._error(404)
        tot_cn=str(i['amount'])
        html='''<!DOCTYPE html><html><head><meta charset="utf-8"><title>发票 #'''+str(i['invoice_number'])+'''</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
    body{font-family:"SimSun","STSong",serif;padding:30px;max-width:800px;margin:auto}
    @media print{@page{margin:1.5cm}.no-print{display:none!important}}
    .invoice-box{border:2px solid #333;padding:30px}
    .header{text-align:center;margin-bottom:25px}
    .header h2{font-size:24px;margin-bottom:5px}
    .header p{color:#666;font-size:12px}
    table.detail{width:100%;border-collapse:collapse;margin:15px 0}
    table.detail th,table.detail td{border:1px solid #333;padding:8px 10px;text-align:center}
    table.detail th{background:#f0f0f0}
    .total{text-align:right;font-size:18px;font-weight:bold;margin:15px 0}
    .footer{text-align:center;margin-top:30px;font-size:12px;color:#666}
    .signature{width:100%;margin-top:25px}
    .signature td{text-align:center;padding-top:30px}
    </style></head><body>
    <div class="invoice-box">
    <div class="header"><h2>电子发票</h2><p>发票代码：'''+str(i['invoice_number'])+'''</p></div>
    <table style="width:100%;margin-bottom:15px">
    <tr><td style="width:50%"><strong>购买方：</strong>'''+h(i['buyer_name'] or i['oname'] or '')+'''</td>
    <td><strong>纳税人识别号：</strong>'''+h(i['buyer_tax_id'] or '-')+'''</td></tr>
    <tr><td><strong>房号：</strong>'''+h(i['building'])+'-'+h(i['unit']or'')+'-'+h(i['room_number'])+'''</td>
    <td><strong>开票日期：</strong>'''+h(i['issue_date'] or '')+'''</td></tr>
    </table>
    <table class="detail"><thead><tr><th>项目名称</th><th>账期</th><th>金额（元）</th></tr></thead>
    <tbody><tr><td>物业管理费</td><td>'''+h(i['billing_period'])+'''</td><td>'''+m(i['amount'])+'''</td></tr></tbody></table>
    <div class="total">合计金额：¥'''+m(i['amount'])+'''</div>
    <div class="footer">开票人：管理员 · 打印日期：'''+datetime.now().strftime('%Y-%m-%d')+'''</div>
    <div class="signature"><table><tr><td>开票人</td><td>复核人</td><td>收款人</td></tr></table></div>
    </div>
    <div class="no-print text-center mt-3"><button class="btn btn-primary" onclick="window.print()"><i class="bi bi-printer"></i> 打印</button> <a href="/invoices" class="btn btn-outline-secondary">返回</a></div>
    </body></html>'''
        self._html(html)

    def _invoice_delete(self, iid):
        db=get_db();db.execute("DELETE FROM invoices WHERE id=?",(iid,));db.commit();db.close()
        self._redirect('/invoices?flash=已删除')
