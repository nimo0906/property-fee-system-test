#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Electronic invoice management."""

from server.db import get_db, get_period, h, m, qs, date_to_period, period_to_date
from server.billing_periods import append_period_filter
from server.invoice_requests import InvoiceRequestError, InvoiceRequestService
from server.base import BaseHandler
from datetime import date, datetime


def _rmb_upper(amount):
    nums = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
    int_units = ['', '拾', '佰', '仟', '万', '拾', '佰', '仟', '亿']
    try:
        cents = int(round(float(amount) * 100))
    except Exception:
        cents = 0
    if cents <= 0:
        return '零元整'
    yuan, cents = divmod(cents, 100)
    text = ''
    zero = False
    digits = str(yuan)
    for idx, ch in enumerate(digits):
        n = int(ch)
        unit = int_units[len(digits) - idx - 1]
        if n == 0:
            zero = True
            if unit in ('万', '亿') and not text.endswith(unit):
                text += unit
            continue
        if zero and text and not text.endswith(('万', '亿')):
            text += '零'
        text += nums[n] + unit
        zero = False
    text = text.rstrip('零') + '元'
    jiao, fen = divmod(cents, 10)
    if jiao:
        text += nums[jiao] + '角'
    if fen:
        text += nums[fen] + '分'
    return text if cents else text + '整'


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
        kw=qs(q,'keyword').strip()
        sql='''SELECT i.*,b.bill_number,b.billing_period,b.amount bill_amount,
            r.building,r.unit,r.room_number,o.name oname FROM invoices i
            LEFT JOIN bills b ON i.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id
            LEFT JOIN owners o ON b.owner_id=o.id
            WHERE 1=1'''
        sql, vals = append_period_filter(sql, [], p, 'b.billing_period')
        if kw:
            sql += ''' AND (i.invoice_number LIKE ? OR i.buyer_name LIKE ? OR i.buyer_tax_id LIKE ?
                OR o.name LIKE ? OR r.building LIKE ? OR r.unit LIKE ? OR r.room_number LIKE ?)'''
            vals.extend([f'%{kw}%'] * 7)
        rows=db.execute(sql + ' ORDER BY i.id DESC', vals).fetchall()
        total_sql, total_vals = append_period_filter(
            "SELECT COALESCE(SUM(i.amount),0) FROM invoices i JOIN bills b ON i.bill_id=b.id WHERE 1=1", [], p, 'b.billing_period'
        )
        total=db.execute(total_sql,total_vals).fetchone()[0]
        avail_sql='''SELECT b.id,b.bill_number,b.amount,b.billing_period,r.building,r.unit,r.room_number,o.name oname
            FROM bills b JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            WHERE b.status='paid' AND b.id NOT IN (SELECT bill_id FROM invoices)'''
        avail_sql, avail_vals = append_period_filter(avail_sql, [], p, 'b.billing_period')
        avail=db.execute(avail_sql + ' ORDER BY r.building,r.room_number', avail_vals).fetchall()
        db.close()
        rh=''
        for r in rows:
            rh+='<tr>'
            rh+='<td><small>'+h(r['invoice_number'] or '-')+'</small></td>'
            rh+='<td>'+h(r['building']or'')+'-'+h(r['unit']or'')+'-'+h(r['room_number']or'')+'</td>'
            buyer_hint = h(r['buyer_name'] or r['oname'] or '-')
            owner_hint = h(r['oname'] or '-')
            rh+='<td><strong>'+buyer_hint+'</strong><br><small class="text-muted">业主：'+owner_hint+'</small></td>'
            rh+='<td class="text-end">¥'+m(r['amount'])+'</td>'
            rh+='<td>'+h(r['issue_date']or'-')+'</td>'
            rh+='<td><span class="badge bg-success">已开具</span></td>'
            rh+='<td><a href="/invoices/'+str(r['id'])+'/print" class="btn btn-sm btn-outline-info"><i class="bi bi-printer"></i> 打印</a> '
            rh+='<form method=POST action="/invoices/'+str(r['id'])+'/delete" style=display:inline><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'
        av_opts = '<option value="">--选择--</option>'
        for a in avail:
            av_opts += f'<option value="{a["id"]}">{h(a["building"])}-{h(a["room_number"])} {h(a["oname"])} ¥{m(a["amount"])}</option>'
        # Available bills for invoice
        self._html(self._page("发票管理", f'''
    <div class="d-flex flex-wrap justify-content-between mb-3 gap-2">
    <form class="row g-2 align-items-end" method=GET>
    <div class="col-auto"><label class="form-label small text-muted mb-1">账期</label><input type="date" name="period" class="form-control form-control-sm" value="{period_to_date(p)}" onchange="this.form.submit()"></div>
    <div class="col-auto"><label class="form-label small text-muted mb-1">发票列表筛选</label><input name="keyword" class="form-control form-control-sm" value="{h(kw)}" placeholder="发票号/抬头/税号/房号"></div>
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
        room_label = h(i['building'])+'-'+h(i['unit']or'')+'-'+h(i['room_number'])
        buyer = h(i['buyer_name'] or i['oname'] or '')
        tax_id = h(i['buyer_tax_id'] or '-')
        amount = m(i['amount'])
        html='''<!DOCTYPE html><html><head><meta charset="utf-8"><title>发票 #'''+h(i['invoice_number'])+'''</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
    body{font-family:"SimSun","STSong",serif;background:#ecebea;color:#6b1f16;padding:20px}
    @media print{@page{size:A4 landscape;margin:8mm}body{background:#fff;padding:0}.no-print{display:none!important}.invoice-shell{box-shadow:none;margin:0 auto}}
    .invoice-shell{position:relative;max-width:1120px;margin:auto;background:#fff;border:1px solid #9d2a22;padding:18px 20px 20px;box-shadow:0 10px 30px rgba(0,0,0,.08)}
    .invoice-top{display:grid;grid-template-columns:130px 1fr 260px;align-items:start;gap:18px;margin-bottom:8px}
    .invoice-qr{width:96px;height:96px;border:2px solid #111;background:
      linear-gradient(90deg,#111 10px,transparent 10px 18px,#111 18px 26px,transparent 26px 34px,#111 34px 42px,transparent 42px 50px,#111 50px 58px,transparent 58px 66px,#111 66px 74px,transparent 74px),
      linear-gradient(#111 10px,transparent 10px 18px,#111 18px 26px,transparent 26px 34px,#111 34px 42px,transparent 42px 50px,#111 50px 58px,transparent 58px 66px,#111 66px 74px,transparent 74px);
      background-size:24px 24px;opacity:.92}
    .title-wrap{text-align:center;position:relative;padding-top:4px}
    .invoice-title{color:#9d2a22;letter-spacing:10px;font-size:30px;font-weight:700;border-bottom:3px double #9d2a22;display:inline-block;padding:0 34px 7px}
    .invoice-sub{color:#9d2a22;font-size:15px;margin-top:4px}
    .fiscal-mark{position:absolute;left:50%;top:-5px;transform:translateX(-50%) rotate(-8deg);width:104px;height:64px;border:4px solid #d71920;border-radius:50%;color:#d71920;font-size:13px;line-height:1.2;display:flex;align-items:center;justify-content:center;opacity:.72}
    .number-box{font-size:13px;line-height:2;text-align:right;color:#6b1f16}
    .invoice-code-line{display:flex;justify-content:space-between;gap:18px;border-top:1px dashed #c46b62;border-bottom:1px dashed #c46b62;padding:6px 4px;margin:4px 0 8px;font-size:12px;color:#7a2a22}
    .invoice-password-zone{border:1px solid #9d2a22;margin:0 0 8px;padding:6px 8px;display:grid;grid-template-columns:90px 1fr;color:#6b1f16;font-size:12px;letter-spacing:1px}
    .invoice-password-zone .label{color:#9d2a22;font-weight:700;border-right:1px solid #9d2a22;margin-right:8px}
    .notice{font-size:12px;color:#7b5d55;text-align:center;margin:4px 0 8px}
    .invoice-body{position:relative;border:2px solid #9d2a22;overflow:hidden}
    .invoice-watermark{position:absolute;left:50%;top:52%;transform:translate(-50%,-50%) rotate(-18deg);font-size:72px;font-weight:700;color:rgba(157,42,34,.055);letter-spacing:14px;white-space:nowrap;pointer-events:none;z-index:0}
    .invoice-body>*:not(.invoice-watermark){position:relative;z-index:1}
    .invoice-copy-label{position:absolute;right:-22px;top:8px;writing-mode:vertical-rl;letter-spacing:4px;font-size:12px;color:#9d2a22}
    .parties{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #9d2a22}
    .party{display:grid;grid-template-columns:30px 1fr;min-height:82px;border-right:1px solid #9d2a22}.party:last-child{border-right:0}
    .party-title{writing-mode:vertical-rl;text-align:center;letter-spacing:4px;border-right:1px solid #9d2a22;color:#9d2a22;font-weight:700;padding:6px 3px}
    .party-body{display:grid;grid-template-columns:120px 1fr;gap:2px 8px;padding:8px 10px;font-size:13px;align-content:start}
    .invoice-table{width:100%;border-collapse:collapse;color:#6b1f16;table-layout:fixed}.invoice-table th,.invoice-table td{border-right:1px solid #9d2a22;padding:6px 7px;text-align:center;font-size:13px;vertical-align:top}
    .invoice-table th{border-bottom:1px solid #9d2a22;color:#9d2a22;font-weight:700}.invoice-table td{height:132px}.invoice-table th:last-child,.invoice-table td:last-child{border-right:0}.invoice-table td.left{text-align:left}
    .invoice-table .amount-line td{height:auto;border-top:1px solid #9d2a22;font-weight:700}
    .total-row{display:grid;grid-template-columns:170px 1fr 180px 170px;border-top:1px solid #9d2a22}
    .total-row div{padding:8px 10px;border-right:1px solid #9d2a22;font-size:14px}.total-row div:last-child{border-right:0;text-align:right;font-weight:700}
    .remark{display:grid;grid-template-columns:30px 1fr;min-height:74px;border-top:1px solid #9d2a22;font-size:13px}.remark-label{writing-mode:vertical-rl;text-align:center;letter-spacing:5px;border-right:1px solid #9d2a22;color:#9d2a22;font-weight:700;padding:6px 3px}.remark-body{padding:9px 10px;color:#6b1f16}
    .sign-row{display:grid;grid-template-columns:1fr 1fr 1fr;margin-top:16px;color:#6b1f16;font-size:13px}
    </style></head><body>
    <div class="invoice-shell">
      <div class="invoice-top"><div><div class="invoice-qr" aria-label="内部票据二维码占位"></div></div>
      <div class="title-wrap"><div class="invoice-title">电子发票</div><div class="invoice-sub">电子发票（普通发票）</div><div class="fiscal-mark">内部留存<br>打印样式</div></div>
      <div class="number-box"><div>发票号码：'''+h(i['invoice_number'])+'''</div><div>开票日期：'''+h(i['issue_date'] or '')+'''</div><div>打印日期：'''+datetime.now().strftime('%Y-%m-%d')+'''</div><div>共1页&nbsp;&nbsp;第1页</div></div></div>
      <div class="invoice-code-line"><span>机器编号：PF-LOCAL-001</span><span>发票代码：'''+h(i['invoice_number'])+'''</span><span>开票校验码：'''+h(str(i['id']).zfill(6))+'''-'''+h(str(i['bill_id']).zfill(6))+'''</span></div>
      <div class="notice">本系统打印样式，仅用于内部留存；数电票据样式参考，仅用于内部留存；真实税务发票请以税务平台开具文件为准。</div>
      <div class="invoice-password-zone"><div class="label">密码区</div><div>本地内部票据无税控密码；如需正式税务发票，请以税务平台生成的 OFD/PDF 文件为准。</div></div>
      <div class="invoice-body"><div class="invoice-watermark">内部留存</div><div class="invoice-copy-label">发票联</div>
      <div class="parties">
        <div class="party"><div class="party-title">购买方信息</div><div class="party-body"><div>名称：</div><div>'''+buyer+'''</div><div>纳税人识别号：</div><div>'''+tax_id+'''</div><div>地址、电话：</div><div>'''+h(i['ophone'] or '-')+'''</div><div>开户行及账号：</div><div>-</div></div></div>
        <div class="party"><div class="party-title">销售方信息</div><div class="party-body"><div>名称：</div><div>物业管理收费系统</div><div>纳税人识别号：</div><div>-</div><div>地址、电话：</div><div>-</div><div>开户行及账号：</div><div>-</div></div></div>
      </div>
      <table class="invoice-table"><thead><tr><th style="width:28%">项目名称</th><th>规格型号</th><th>单位</th><th>数量</th><th>单价</th><th>金额</th><th>税率/征收率</th><th>税额</th></tr></thead>
      <tbody><tr><td class="left">*物业服务*物业管理费<br><small>房号：'''+room_label+'''；账期：'''+h(i['billing_period'])+'''</small></td><td>-</td><td>项</td><td>1</td><td>'''+amount+'''</td><td>'''+amount+'''</td><td>免税</td><td>0.00</td></tr>
      <tr class="amount-line"><td>合计</td><td colspan="4"></td><td>¥'''+amount+'''</td><td></td><td>¥0.00</td></tr></tbody></table>
      <div class="total-row"><div>价税合计（大写）</div><div>'''+_rmb_upper(float(i['amount'] or 0))+'''</div><div>价税合计（小写）</div><div>¥'''+amount+'''</div></div>
      <div class="remark"><div class="remark-label">备注</div><div class="remark-body">账单号 '''+h(i['bill_number'] or '-')+'''；房号 '''+room_label+'''；账期 '''+h(i['billing_period'])+'''</div></div>
      </div>
      <div class="sign-row"><div>收款人：管理员</div><div>复核人：管理员</div><div>开票人：管理员</div></div>
    </div>
    <div class="no-print text-center mt-3"><div class="alert alert-light border d-inline-block text-start small mb-2"><strong>保存为PDF：</strong>点击打印后，在打印对话框中选择“保存为 PDF”。</div><br><button class="btn btn-primary" onclick="window.print()"><i class="bi bi-printer"></i> 打印</button> <a href="/invoices" class="btn btn-outline-secondary">返回</a></div>
    </body></html>'''
        self._html(html)

    def _invoice_delete(self, iid):
        db=get_db();db.execute("DELETE FROM invoices WHERE id=?",(iid,));db.commit();db.close()
        self._redirect('/invoices?flash=已删除')
