#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment reminder management."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs, date_to_period, period_to_date
from server.billing_periods import append_period_filter
from server.base import BaseHandler
from datetime import date, datetime, timedelta


class ReminderMixin(BaseHandler):

    def _reminders(self, q):
        """催缴管理：按紧急度分组（即将到期/已逾期），支持按费用类型分别设置提前天数"""
        update_overdue_bills()
        db=get_db();p=date_to_period(qs(q,'period',get_period()));bld=qs(q,'building');st=qs(q,'status')
        today=date.today()
        sql='''SELECT o.id oid,o.name oname,o.phone ophone,r.id rid,r.building,r.unit,r.room_number,
            r.area,r.category,b.id bid,b.fee_type_id,b.amount,b.billing_period,b.due_date,b.status,b.bill_number,
            f.name ft_name,f.reminder_advance_days,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b JOIN rooms r ON b.room_id=r.id
            LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.status IN('unpaid','overdue','partial') AND o.id IS NOT NULL'''
        sql, vals = append_period_filter(sql, [], p, 'b.billing_period')
        if bld:sql+=" AND r.building=?";vals.append(bld)
        if st:sql+=" AND b.status=?";vals.append(st)
        sql+=" ORDER BY b.due_date ASC,o.id,r.building,r.room_number,f.sort_order"
        rows=db.execute(sql,vals).fetchall()
        blds=db.execute("SELECT DISTINCT building FROM rooms ORDER BY building").fetchall()
        db.close()
        overdue_list=[];approaching_list=[]
        for r in rows:
            rem=r['amount']-r['paid']
            if rem<=0: continue
            due=None
            if r['due_date']:
                try: due=datetime.strptime(r['due_date'],'%Y-%m-%d').date()
                except: pass
            advance=r['reminder_advance_days'] or 30
            is_overdue=due and due<today and r['status'] in('unpaid','overdue')
            is_approaching=due and due>=today and due<=today+timedelta(days=advance) and r['status'] in('unpaid','partial')
            if is_overdue:
                overdue_list.append(r)
            elif is_approaching:
                approaching_list.append(r)
        groups=[]
        if overdue_list:
            groups.append(('overdue','已逾期','danger','bi-exclamation-triangle',overdue_list))
        if approaching_list:
            groups.append(('approaching','即将到期','warning text-dark','bi-clock',approaching_list))
        all_bills=overdue_list+approaching_list
        total_owners=len(set(r['oid'] for r in all_bills))
        total_amt=sum(r['amount']-r['paid'] for r in all_bills)
        total_late=sum(calc_bill_late_fee(r['bid']) for r in all_bills)
        bld_opts='<option value="">全部楼栋</option>'+''.join(f'<option value="{h(b["building"])}"{" selected" if bld==b["building"] else""}>{h(b["building"])}</option>' for b in blds)
        st_opts='<option value="">全部状态</option><option value="overdue"{" selected" if st=="overdue" else""}>已逾期</option><option value="approaching"{" selected" if st=="approaching" else""}>即将到期</option>'
        oh=''
        for gid,glabel,gcolor,gicon,bills in groups:
            oh+=f'<tr style="background:#eee"><td colspan="7"><strong><i class="bi {gicon}"></i> {glabel}</strong> <span class="badge bg-{gcolor.split()[0]}">{len(bills)}笔</span></td></tr>'
            gowners={}
            for r in bills:
                oid=r['oid']
                if oid not in gowners:
                    gowners[oid]={'name':r['oname']or'未知','phone':r['ophone']or'','rooms':{},'bills':[],'total':0,'late_fee':0}
                rkey=f"{r['building']}-{r['unit']}-{r['room_number']}"
                if r['rid'] not in gowners[oid]['rooms']:
                    gowners[oid]['rooms'][r['rid']]=rkey
                gowners[oid]['bills'].append(r)
                gowners[oid]['total']+=r['amount']-r['paid']
                gowners[oid]['late_fee']+=calc_bill_late_fee(r['bid'])
            for oid,o in sorted(gowners.items()):
                rooms_str='、'.join(o['rooms'].values())
                due_hint='<span class="badge bg-danger">逾期</span>' if gid=='overdue' else '<span class="badge bg-warning text-dark">即将到期</span>'
                oh+=f'<tr class="table-light" onclick="toggleRoom(\'remind'+str(gid)+''+str(oid)+'\')" style="cursor:pointer">'
                oh+=f'<td><i class="bi bi-chevron-right" id="icon_remind{gid}{oid}"></i> <strong>{h(o["name"])}</strong><br><small class="text-muted">{h(o["phone"])}</small></td>'
                oh+=f'<td><small>{rooms_str}</small></td><td class="text-end">{len(o["bills"])}</td>'
                oh+=f'<td class="text-end text-danger">¥{m(o["total"])}</td><td class="text-end text-warning">¥{m(o["late_fee"])}</td>'
                oh+=f'<td class="text-end"><strong>¥{m(o["total"]+o["late_fee"])}</strong></td>'
                oh+=f'<td>{due_hint} <a href="/reminders/print?owner_id={oid}&period={p}" class="btn btn-sm btn-outline-danger" target="_blank"><i class="bi bi-printer"></i></a></td></tr>'
                for r in o['bills']:
                    rem=r['amount']-r['paid']
                    lf=calc_bill_late_fee(r['bid'])
                    sn={'unpaid':'warning text-dark','overdue':'danger','partial':'info'}
                    ln={'unpaid':'未缴','overdue':'逾期','partial':'部分缴'}
                    oh+=f'<tr class="room-detail-remind{gid}{oid}" style="display:none;font-size:0.9em">'
                    oh+=f'<td></td><td style="padding-left:25px"><small>{h(r["building"])}-{h(r["unit"])}-{h(r["room_number"])}</small></td>'
                    oh+=f'<td><span class="badge bg-info">{h(r["ft_name"])}</span></td><td class="text-end"><small>{h(r["billing_period"])}</small></td>'
                    oh+=f'<td class="text-end text-danger">{m(rem)}</td><td class="text-end text-warning"><small>{m(lf)}</small></td>'
                    oh+=f'<td class="text-end"><strong>{m(rem+lf)}</strong></td>'
                    oh+=f'<td><span class="badge bg-{sn.get(r["status"],"secondary")}">{ln.get(r["status"],r["status"])}</span></td></tr>'
        if not oh:
            oh='<tr><td colspan="7" class="text-center text-muted py-4">本账期没有催缴记录</td></tr>'
        self._html(self._page('催缴管理',f'''
    <div class="alert alert-warning"><i class="bi bi-bell"></i> 按紧急度分组展示：<span class="badge bg-danger">已逾期</span> 和 <span class="badge bg-warning text-dark">即将到期</span>（各费用类型可单独设置催缴提前天数）。</div>
    <div class="d-flex flex-wrap justify-content-between mb-3 gap-2">
    <form class="row g-2" method=GET>
    <div class="col-auto"><input type="date" name="period" class="form-control form-control-sm" value="{period_to_date(p)}" onchange="this.form.submit()"></div>
    <div class="col-auto"><select name="building" class="form-select form-select-sm" onchange="this.form.submit()">{bld_opts}</select></div>
    <div class="col-auto"><select name="status" class="form-select form-select-sm" onchange="this.form.submit()">{st_opts}</select></div>
    <div class="col-auto"><button class="btn btn-sm btn-outline-primary"><i class="bi bi-search"></i></button>
    <a href="/reminders" class="btn btn-sm btn-outline-secondary"><i class="bi bi-x-circle"></i></a></div></form>
    <div class="d-flex gap-1">
    <a href="/reminders/print?period={p}&building={bld}" class="btn btn-sm btn-outline-danger" target="_blank"><i class="bi bi-printer"></i> 批量打印</a>
    <a href="/fee_types" class="btn btn-sm btn-outline-secondary"><i class="bi bi-gear"></i> 催缴天数设置</a>
    </div>
    </div>
    <div class="d-flex flex-wrap gap-2 mb-2">
    <span class="badge bg-light text-dark p-2"><i class="bi bi-people"></i> 催缴业主 {total_owners}户</span>
    <span class="badge bg-danger p-2">逾期 {len(overdue_list)}笔</span>
    <span class="badge bg-warning text-dark p-2">即将到期 {len(approaching_list)}笔</span>
    <span class="badge bg-light text-dark p-2">欠费 ¥{m(total_amt)}</span>
    <span class="badge bg-warning text-dark p-2">滞纳金 ¥{m(total_late)}</span>
    <span class="badge bg-dark p-2">合计 ¥{m(total_amt+total_late)}</span>
    </div>
    <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th style="min-width:120px">业主</th><th>房间</th><th class="text-end">笔数</th><th class="text-end">欠费</th><th class="text-end">滞纳金</th><th class="text-end">合计</th><th style="width:80px">操作</th></tr></thead>
    <tbody>{oh}</tbody></table></div>''','reminders'))

    def _reminder_print(self, q):
        update_overdue_bills()
        p=date_to_period(qs(q,'period',get_period()));oid=qs(q,'owner_id');bld=qs(q,'building');st=qs(q,'status')
        db=get_db()
        sql='''SELECT o.id oid,o.name oname,o.phone ophone,o.id_card oid_card,o.move_in_date,
            r.id rid,r.building,r.unit,r.room_number,r.area,r.category,
            b.id bid,b.fee_type_id,b.amount,b.billing_period,b.due_date,b.status,b.bill_number,
            f.name ft_name,f.unit_price,f.calc_method,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b JOIN rooms r ON b.room_id=r.id
            LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.status IN('unpaid','overdue','partial') AND o.id IS NOT NULL'''
        sql, vals = append_period_filter(sql, [], p, 'b.billing_period')
        if oid:sql+=" AND o.id=?";vals.append(oid)
        if bld:sql+=" AND r.building=?";vals.append(bld)
        if st:sql+=" AND b.status=?";vals.append(st)
        sql+=" ORDER BY o.id,r.building,r.room_number,f.sort_order"
        rows=db.execute(sql,vals).fetchall()
        db.close()
        owners={}
        for r in rows:
            oid=r['oid']
            if oid not in owners:
                owners[oid]={'name':r['oname']or'未知','phone':r['ophone']or'','id_card':r['oid_card']or'','rooms':{},'bills':[]}
            rid=r['rid']
            rkey=f"{r['building']}-{r['unit']}-{r['room_number']}"
            if rid not in owners[oid]['rooms']:
                owners[oid]['rooms'][rid]=rkey
            rem=r['amount']-r['paid']
            if rem>0:
                owners[oid]['bills'].append({**r,'rem':rem,'late_fee':calc_bill_late_fee(r['bid'])})
        if not owners:
            return self._html('<h1>当前账期没有欠费记录</h1>')
        pages=''
        for oid,o in owners.items():
            total_amt=sum(b['rem'] for b in o['bills'])
            total_lf=sum(b['late_fee'] for b in o['bills'])
            bill_rows=''.join(f'''<tr><td>{h(b['building'])}-{h(b['unit'])}-{h(b['room_number'])}</td>
    <td><span class="badge bg-info">{h(b['ft_name'])}</span></td>
    <td>{h(b['billing_period'])}</td>
    <td class="text-end">{m(b['rem'])}</td>
    <td class="text-end">{m(b['late_fee'])}</td>
    <td class="text-end"><strong>{m(b['rem']+b['late_fee'])}</strong></td></tr>''' for b in o['bills'])
            rooms_list='、'.join(o['rooms'].values())
            pages+=f'''<div class="page">
    <h2 style="text-align:center;margin-bottom:30px">催缴通知单</h2>
    <table style="width:100%;margin-bottom:20px"><tr><td style="width:50%"><strong>业主：</strong>{h(o['name'])}</td>
    <td><strong>电话：</strong>{h(o['phone'])}</td></tr>
    <tr><td><strong>身份证：</strong>{h(o['id_card'])}</td>
    <td><strong>房屋：</strong>{h(rooms_list)}</td></tr></table>
    <p><strong>尊敬的业主：</strong>经核查，您以下费用尚未缴纳，请于收到本通知后尽快办理。逾期将按每日千分之一计收滞纳金。</p>
    <table class="bill-table"><thead><tr><th>房号</th><th>费用项目</th><th>账期</th><th class="text-end">欠费(元)</th><th class="text-end">滞纳金(元)</th><th class="text-end">合计(元)</th></tr></thead>
    <tbody>{bill_rows}</tbody>
    <tfoot><tr><td colspan="3" style="text-align:right"><strong>合计</strong></td>
    <td class="text-end"><strong>{m(total_amt)}</strong></td>
    <td class="text-end"><strong>{m(total_lf)}</strong></td>
    <td class="text-end"><strong>{m(total_amt+total_lf)}</strong></td></tr></tfoot></table>
    <p style="margin-top:20px"><strong>合计欠费：¥{m(total_amt+total_lf)}</strong></p>
    <div class="signature"><table style="width:100%"><tr><td style="text-align:center">业主签收</td><td style="text-align:center">催缴人</td><td style="text-align:center">物业盖章</td></tr></table></div>
    <div class="footer">打印日期：{date.today().isoformat()} · 账期：{p}</div>
    </div>'''
        html='''<!DOCTYPE html><html><head><meta charset="utf-8"><title>催缴通知单</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
    body{font-family:"SimSun","STSong","PingFang SC",serif;padding:30px;max-width:900px;margin:auto}
    @media print{@page{margin:1.5cm}.page{page-break-after:always}.no-print{display:none!important}}
    h2{text-align:center;margin-bottom:25px;font-size:22px}
    .bill-table{width:100%;border-collapse:collapse;margin:15px 0}
    .bill-table th,.bill-table td{border:1px solid #333;padding:8px 10px;text-align:left}
    .bill-table th{background:#f0f0f0;font-weight:bold}
    .bill-table tfoot td{border-top:2px solid #333;font-weight:bold}
    .signature{margin-top:35px}.signature td{height:60px;vertical-align:bottom;text-align:center}
    .footer{text-align:center;margin-top:20px;color:#666;font-size:12px}
    </style></head><body>'''+pages+'''
    <div class="no-print text-center mt-3"><button class="btn btn-primary" onclick="window.print()"><i class="bi bi-printer"></i> 打印</button>
    <a href="/reminders?period='''+p+'''" class="btn btn-outline-secondary">返回</a></div>
    </body></html>'''
        self._html(html)
