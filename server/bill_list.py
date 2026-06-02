#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill list with filtering, grouping, and pagination."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs, date_to_period, period_to_date
from server.billing_periods import append_period_filter
from server.base import BaseHandler
from datetime import datetime, date
import urllib.parse


class BillListMixin(BaseHandler):

    def _bills_review(self, q):
        update_overdue_bills()
        period = date_to_period(qs(q, 'period', get_period()))
        scope = qs(q, 'scope', 'all')
        building = qs(q, 'building')
        db = get_db()
        sql = '''SELECT b.*,r.building,r.unit,r.room_number,r.category,f.name ft,o.name owner_name,
               COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid,
               a.old_amount adj_old,a.new_amount adj_new,a.reason adj_reason,a.created_at adj_time
               FROM bills b
               LEFT JOIN rooms r ON b.room_id=r.id
               LEFT JOIN fee_types f ON b.fee_type_id=f.id
               LEFT JOIN owners o ON b.owner_id=o.id
               LEFT JOIN bill_adjustments a ON a.id=(SELECT id FROM bill_adjustments WHERE bill_id=b.id ORDER BY created_at DESC,id DESC LIMIT 1)
               WHERE 1=1'''
        vals = []
        if period:
            sql, vals = append_period_filter(sql, vals, period, 'b.billing_period')
        if building:
            sql += ' AND r.building=?'; vals.append(building)
        if scope == 'adjusted':
            sql += ' AND a.id IS NOT NULL'
        elif scope == 'unpaid':
            sql += " AND b.status IN ('unpaid','overdue','partial')"
        sql += ' ORDER BY CASE WHEN a.id IS NOT NULL THEN 0 ELSE 1 END,r.building,r.unit,r.room_number,b.fee_type_id LIMIT 200'
        rows = db.execute(sql, vals).fetchall()
        total_adj = sum(1 for r in rows if r['adj_new'] is not None)
        amount_total = sum(float(r['amount'] or 0) for r in rows)
        blds = db.execute("SELECT DISTINCT building FROM rooms ORDER BY building").fetchall()
        db.close()
        scope_opts = ''.join([
            f'<option value="all"{" selected" if scope=="all" else ""}>全部待核对</option>',
            f'<option value="adjusted"{" selected" if scope=="adjusted" else ""}>人工修正</option>',
            f'<option value="unpaid"{" selected" if scope=="unpaid" else ""}>未缴/部分缴</option>',
        ])
        bld_opts = '<option value="">全部楼栋</option>' + ''.join(
            f'<option value="{h(b["building"])}"{" selected" if building==b["building"] else ""}>{h(b["building"])}</option>' for b in blds
        )
        body = ''
        for r in rows:
            room = f'{r["building"] or ""}-{r["unit"] or ""}-{r["room_number"] or ""}'
            review_tag = '<span class="badge status-warning">人工修正</span>' if r['adj_new'] is not None else '<span class="badge status-info">待收费核对</span>'
            old_amt = f'<span class="money-muted">¥{m(r["adj_old"])}</span>' if r['adj_old'] is not None else '-'
            new_amt = f'<span class="money">¥{m(r["adj_new"])}</span>' if r['adj_new'] is not None else f'<span class="money">¥{m(r["amount"])}</span>'
            body += (
                f'<tr><td>{review_tag}</td><td><a href="/bills/{r["id"]}">{h(r["bill_number"] or r["id"])}</a></td>'
                f'<td>{h(room)}</td><td>{h(r["owner_name"] or "-")}</td><td>{h(r["ft"] or "-")}</td>'
                f'<td class="text-end">{old_amt}</td><td class="text-end">{new_amt}</td><td>{h(r["due_date"] or "-")}</td>'
                f'<td>{h(r["adj_reason"] or "-")}</td><td><a class="btn btn-sm btn-outline-warning" href="/bills/{r["id"]}/edit">修正</a></td></tr>'
            )
        if not body:
            body = '<tr><td colspan="10" class="text-center text-muted py-4">当前筛选条件下暂无需要核对的账单</td></tr>'
        self._html(self._page('账单核对工作台', f'''
        <div class="alert alert-info"><strong>账单核对工作台</strong>：用于出账后、批量修正后集中核对金额、截止日和修正记录。</div>
        <form method="GET" action="/bills/review" class="filter-bar row g-2">
        <div class="col-md-3"><label>账期</label><input type="date" name="period" value="{period_to_date(period)}" class="form-control"><small class="text-muted">按所选日期所在月份筛选</small></div>
        <div class="col-md-3"><label>楼栋</label><select name="building" class="form-select">{bld_opts}</select></div>
        <div class="col-md-3"><label>核对范围</label><select name="scope" class="form-select">{scope_opts}</select></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-primary me-2">筛选</button><a class="btn btn-outline-secondary" href="/bills">返回账单</a></div>
        </form>
        <div class="row text-center g-2 mb-3">
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">显示账单</div><strong>{len(rows)}</strong></div></div>
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">人工修正</div><strong>{total_adj}</strong></div></div>
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">金额合计</div><strong class="money">¥{m(amount_total)}</strong></div></div>
        </div>
        <div class="card"><div class="card-header">核对明细</div><div class="table-responsive">
        <table class="table table-sm mb-0"><thead><tr><th>类型</th><th>编号</th><th>房间</th><th>业主</th><th>收费项目</th><th class="text-end">原金额</th><th class="text-end">新金额</th><th>截止日</th><th>原因</th><th>操作</th></tr></thead><tbody>{body}</tbody></table>
        </div></div>
        ''', 'bills'))

    def _bills(self, q):
        update_overdue_bills()
        db=get_db();s=qs(q,'status');fid=qs(q,'fee_type_id');raw_period=qs(q,'period',get_period());p=raw_period.strip() if '~' in raw_period else date_to_period(raw_period)
        kw=qs(q,'keyword');bld=qs(q,'building');cat=qs(q,'category')
        current_query = urllib.parse.urlencode([
            (k, v)
            for k, vals in q.items()
            for v in vals
            if v != ''
        ])
        current_path = '/bills' + (f'?{current_query}' if current_query else '')
        detail_back = urllib.parse.urlencode({'back': current_path})
        sql='''SELECT b.*,r.building,r.unit,r.room_number,r.floor,r.category,r.tenant_name,f.name ft,o.name owner_name,
               COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
               FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id LEFT JOIN owners o ON b.owner_id=o.id WHERE 1=1'''
        vals=[]
        if p:
            sql, vals = append_period_filter(sql, vals, p, 'b.billing_period')
        if s:sql+=" AND b.status=?";vals.append(s)
        if fid and fid!='0':sql+=" AND b.fee_type_id=?";vals.append(fid)
        if bld:sql+=" AND r.building=?";vals.append(bld)
        if cat:sql+=" AND r.category=?";vals.append(cat)
        if kw:sql+=" AND (r.building LIKE ? OR r.room_number LIKE ? OR r.unit LIKE ?)";vals.extend([f'%{kw}%',f'%{kw}%',f'%{kw}%'])
        sql+=" ORDER BY r.building,r.unit,r.room_number,b.fee_type_id"
        pg=int(qs(q,'page','1'))
        per_page=50
        total_rows=db.execute("SELECT COUNT(*) FROM ("+sql+")",vals).fetchone()[0]
        sql+=" LIMIT ? OFFSET ?"
        vals.extend([per_page, (pg-1)*per_page])
        rows=db.execute(sql,vals).fetchall()
        total_pages=max(1,(total_rows+per_page-1)//per_page)
        fts=db.execute("SELECT * FROM fee_types ORDER BY sort_order").fetchall()
        blds=db.execute("SELECT DISTINCT building FROM rooms ORDER BY building").fetchall()
        ta=sum(r['amount'] for r in rows);tp=sum(r['paid'] for r in rows)
        t_unpaid=sum(1 for r in rows if r['status'] in ('unpaid','overdue'))
        t_paid=sum(1 for r in rows if r['status']=='paid')
        t_rooms=len(set(r['room_id'] for r in rows))
        db.close()
        sn={'paid':'status-paid','unpaid':'status-unpaid','overdue':'status-overdue','partial':'status-partial'}
        ln={'paid':'已缴','unpaid':'未缴','overdue':'逾期','partial':'部分缴'}
        owner_groups={}
        for r in rows:
            on=h(r['tenant_name'] or r['owner_name'] or '未知')
            if on not in owner_groups: owner_groups[on]={'rooms':{}}
            rid=r['room_id']
            rn=h(r['building']or'')+'-'+h(r['unit']or'')+'-'+h(r['room_number']or'')
            if rid not in owner_groups[on]['rooms']: owner_groups[on]['rooms'][rid]={'name':rn,'bills':[]}
            owner_groups[on]['rooms'][rid]['bills'].append(r)
        rh=''
        oidx=0
        for oname, og in owner_groups.items():
            oidx+=1
            owner_group = f'o{oidx}'
            o_total=sum(b['amount'] for rl in og['rooms'].values() for b in rl['bills'])
            o_paid=sum(b['paid'] for rl in og['rooms'].values() for b in rl['bills'])
            o_rem=o_total-o_paid
            o_rem_html = f'<strong class="money money-due">¥{m(o_rem)}</strong>' if o_rem>0 else '<span class="money money-paid">¥0.00</span>'
            owner_chk = f'<input type="checkbox" class="owner-group-chk" data-owner-group="{owner_group}" title="选择该租户下全部账单" onclick="event.stopPropagation();toggleBillGroup(\'owner\',\'{owner_group}\',this.checked)">'
            rh+=f'<tr class="table-secondary" onclick="toggleRoom(\'{owner_group}\')" style="cursor:pointer">'
            rh+=f'<td>{owner_chk}</td><td><i class="bi bi-chevron-right" id="icon_{owner_group}"></i> <strong>{oname}</strong> <span class="badge bg-light text-dark ms-1">{len(og["rooms"])}间</span></td>'
            rh+=f'<td></td><td></td><td class="text-end"><span class="money">¥{m(o_total)}</span></td><td class="text-end"><span class="money money-paid">¥{m(o_paid)}</span></td>'
            rh+=f'<td class="text-end">{o_rem_html}</td>'
            rh+=f'<td></td><td></td><td></td></tr>'
            for ridx, (rid, rl) in enumerate(og['rooms'].items(), 1):
                room_group = f'{owner_group}r{ridx}'
                r_total=sum(b['amount'] for b in rl['bills'])
                r_paid=sum(b['paid'] for b in rl['bills'])
                r_rem=r_total-r_paid
                r_rem_html = f'<strong class="money money-due">¥{m(r_rem)}</strong>' if r_rem>0 else '<span class="money money-paid">¥0.00</span>'
                room_chk = f'<input type="checkbox" class="room-group-chk" data-owner-group="{owner_group}" data-room-group="{room_group}" title="选择该房间下全部账单" onclick="toggleBillGroup(\'room\',\'{room_group}\',this.checked)">'
                rh+=f'<tr class="room-detail-{owner_group}" style="display:none;background:#f8f9fa">'
                rh+=f'<td>{room_chk}</td><td style="padding-left:25px"><strong>{rl["name"]}</strong></td>'
                rh+=f'<td></td><td></td><td class="text-end"><span class="money">¥{m(r_total)}</span></td><td class="text-end"><span class="money money-paid">¥{m(r_paid)}</span></td>'
                rh+=f'<td class="text-end">{r_rem_html}</td>'
                rh+=f'<td></td><td></td><td></td></tr>'
                for b in rl['bills']:
                    rem=b['amount']-b['paid']
                    rem_html = f'<strong class="money money-due">¥{m(rem)}</strong>' if rem>0 else '<span class="money money-paid">¥0.00</span>'
                    chk=f'<input type=checkbox name=bill_ids value="{b["id"]}" class=bill-chk form="billActionForm" data-owner-group="{owner_group}" data-room-group="{room_group}">'
                    rh+=f'<tr class="room-detail-{owner_group}" style="display:none">'
                    rh+=f'<td>{chk}</td>'
                    rh+=f'<td><small>{h(b["bill_number"]or"-")}</small></td>'
                    rh+=f'<td><span class="badge status-info">{h(b["ft"])}</span></td>'
                    rh+=f'<td>{h(b["billing_period"])}</td>'
                    rh+=f'<td class="text-end"><span class="money">¥{m(b["amount"])}</span></td><td class="text-end"><span class="money money-paid">¥{m(b["paid"])}</span></td>'
                    rh+=f'<td class="text-end">{rem_html}</td>'
                    rh+=f'<td class="text-end"><small class="money money-due">¥{m(calc_bill_late_fee(b["id"]))}</small></td>'
                    rh+=f'<td><span class="badge {sn.get(b["status"],"status-neutral")}">{ln.get(b["status"],b["status"])}</span></td>'
                    rh+=f'<td><a href="/bills/{b["id"]}?{detail_back}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye"></i></a>'
                    rh+=f'<a href="/bills/{b["id"]}/edit" class="btn btn-sm btn-outline-warning"><i class="bi bi-pencil"></i></a>'
                    if b['status']!='paid': rh+=f'<a href="/bills/{b["id"]}/pay" class="btn btn-sm btn-outline-primary"><i class="bi bi-credit-card"></i></a>'
                    rh+=f'<form method=POST action="/bills/{b["id"]}/delete" style=display:inline onsubmit="return confirm(\'确定删除？已有缴费记录的账单无法删除！\')"><input type="hidden" name="back" value="{h(current_path)}"><button type="submit" class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'
        ft_opts='<option value="">全部类型</option>'+''.join(f'<option value="{f["id"]}"{" selected" if fid==str(f["id"]) else""}>{h(f["name"])}</option>' for f in fts)
        bld_opts='<option value="">全部楼栋</option>'+''.join(f'<option value="{h(b["building"])}"{" selected" if bld==b["building"] else""}>{h(b["building"])}</option>' for b in blds)
        tpl=self._load_template('bills.html')
        tpl=tpl.replace('{PERIOD}',period_to_date(p)).replace('{FT_OPTS}',ft_opts).replace('{BLD_OPTS}',bld_opts)
        tpl=tpl.replace('{KW}',h(kw))
        tpl=tpl.replace('<form method=POST id="billActionForm"></form>',
                        f'<form method=POST id="billActionForm"><input type="hidden" name="back" value="{h(current_path)}"></form>')
        tpl=tpl.replace('{SUN}',' selected' if s=='unpaid' else '').replace('{SPA}',' selected' if s=='paid' else '')
        tpl=tpl.replace('{SOV}',' selected' if s=='overdue' else '')
        tpl=tpl.replace('{ROOMS}',str(t_rooms)).replace('{COUNT}',str(len(rows)))
        tpl=tpl.replace('{TOTAL_ROWS}',str(total_rows)).replace('{PAGE}',str(pg)).replace('{TOTAL_PAGES}',str(total_pages))
        tpl=tpl.replace('{TOTAL_AMT}',m(ta)).replace('{TOTAL_PAID}',m(tp))
        tpl=tpl.replace('{UNPAID_CNT}',str(t_unpaid))
        has_unpaid=any(r['status']!='paid' for r in rows)
        paid_btn='' if not has_unpaid else '<button class="btn btn-sm btn-primary" type=submit form="billActionForm" onclick="this.form.action=\'/bills/batch_pay\';this.form.target=\'_self\'"><i class="bi bi-credit-card"></i> 缴费</button>'
        btn=f'''
        <div class="batch-bar">
        <a class="btn btn-sm btn-outline-primary" href="/bills/review?period={h(p)}"><i class="bi bi-clipboard-check"></i> 核对工作台</a>
        <small class="text-muted me-1"><i class="bi bi-info-circle"></i> 勾选后操作：</small>
        {paid_btn}
        <span class="export-actions">
        <button class="btn btn-sm btn-outline-secondary" type=submit form="billActionForm" onclick="this.form.action=\'/bills/print_selected\';this.form.target=\'_blank\'"><i class="bi bi-printer"></i> 打印</button>
        <button class="btn btn-sm btn-outline-secondary" type=submit form="billActionForm" onclick="this.form.action=\'/bills/receipt_by_ids\';this.form.target=\'_blank\'"><i class="bi bi-receipt"></i> 收据</button>
        <button class="btn btn-sm btn-outline-secondary" type=submit form="billActionForm" onclick="this.form.action=\'/bills/export_selected\';this.form.target=\'_self\'"><i class="bi bi-download"></i> 导出</button>
        </span>
        <button class="btn btn-sm btn-outline-warning" type=submit form="billActionForm" onclick="this.form.action=\'/bills/batch_edit\';this.form.target=\'_self\'"><i class="bi bi-pencil-square"></i> 批量修正</button>
        </div>'''
        tpl=tpl.replace('{BTN_TOP}',btn).replace('{BTN_BOTTOM}',btn)
        tpl=tpl.replace('{SUN}',' selected' if s=='unpaid' else '').replace('{SPA}',' selected' if s=='paid' else '')
        tpl=tpl.replace('{SOV}',' selected' if s=='overdue' else '').replace('{SPT}',' selected' if s=='partial' else '')
        page_links=''
        if total_pages>1:
            page_links='<nav class="mt-2"><ul class="pagination pagination-sm justify-content-center">'
            for i in range(1,total_pages+1):
                active=' active' if i==pg else ''
                url='/bills?' + urllib.parse.urlencode([('page',i),('period',p),('status',s),('fee_type_id',fid),('building',bld),('category',cat),('keyword',kw)])
                page_links+=f'<li class="page-item{active}"><a class="page-link" href="{url}">{i}</a></li>'
            page_links+='</ul></nav>'
        tpl=tpl.replace('{PAGE_LINKS}',page_links)
        tpl=tpl.replace('{ROWS}',rh or '<tr><td colspan="11" class="text-center text-muted py-4">暂无账单</td></tr>')
        self._html(self._page('账单管理',tpl,'bills'))
