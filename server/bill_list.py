#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill list with filtering, grouping, and pagination."""

from server.db import get_db, get_period, calc_bill_late_fee, update_overdue_bills, h, m, qs, date_to_period, period_to_date, add_months, customer_name
from server.billing_periods import append_period_filter, append_natural_date_range_filter
from server.base import BaseHandler
from server.data_health import cleanup_invalid_payments
from server.pagination import business_area_order_sql, clamp_page, parse_page, parse_per_page, render_pagination
from datetime import datetime, date, timedelta
import urllib.parse


def _bill_target_label(row):
    if row['commercial_space_id']:
        return f"商场-{row['space_no'] or ''}"
    return f"{row['building'] or ''}-{row['unit'] or ''}-{row['room_number'] or ''}"


def _bill_scope_label(row):
    try:
        if row['commercial_space_id']:
            return '商业公司收费'
        if row['building'] == '商场' or row['unit'] == '商场':
            return '商业公司收费'
    except Exception:
        pass
    return '物业公司收费'


def _bill_room_label(row):
    if row['commercial_space_id']:
        room = f"商场-{row['space_no'] or ''}"
    else:
        room = f"{row['building'] or ''}-{row['unit'] or ''}-{row['room_number'] or ''}"
    return room


def _bill_object_code(row):
    if row['commercial_space_id']:
        return row['space_no'] or _bill_room_label(row)
    return row['room_number'] or _bill_room_label(row)


def _bill_scope_condition(scope):
    if scope == 'property':
        return " AND b.commercial_space_id IS NULL AND COALESCE(r.building,'')<>'商场' AND COALESCE(r.unit,'')<>'商场'"
    if scope == 'commercial':
        return " AND (b.commercial_space_id IS NOT NULL OR r.building='商场' OR r.unit='商场')"
    return ''


def _bill_scope_url(scope, period_start, period_end, status, fee_type_id, building, category, keyword, auto_batch_no):
    params = []
    for key, value in [
        ('period_start', period_start), ('period_end', period_end), ('status', status),
        ('fee_type_id', fee_type_id), ('building', building), ('category', category),
        ('keyword', keyword), ('auto_batch_no', auto_batch_no),
    ]:
        if value:
            params.append((key, value))
    if scope:
        params.append(('company_scope', scope))
    query = urllib.parse.urlencode(params)
    return '/bills' + (f'?{query}' if query else '')


def _bill_customer_name(row):
    return customer_name(row)


def _bill_group_hint(bills):
    counts = {'unpaid': 0, 'partial': 0, 'paid': 0, 'overdue': 0}
    due = 0
    for bill in bills:
        status = bill['status'] or ''
        if status in counts:
            counts[status] += 1
        due += float(bill['amount'] or 0) - float(bill['paid'] or 0)
    parts = [f'核对：{len(bills)}项']
    if counts['unpaid'] or counts['overdue']:
        parts.append(f'未缴{counts["unpaid"] + counts["overdue"]}')
    if counts['partial']:
        parts.append(f'部分{counts["partial"]}')
    if counts['paid']:
        parts.append(f'已缴{counts["paid"]}')
    parts.append(f'欠费¥{m(due)}')
    return ' · '.join(parts)


class BillListMixin(BaseHandler):

    def _bills_review(self, q):
        update_overdue_bills()
        cleanup_invalid_payments()
        raw_period = qs(q, 'period', '').strip()
        period = date_to_period(raw_period or get_period())
        period_start = qs(q, 'period_start', '').strip()
        period_end = qs(q, 'period_end', '').strip()
        if not period_start and not period_end:
            period_start = period_to_date(period)
            try:
                y, mo = [int(x) for x in period_start[:7].split('-')]
                period_end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
            except Exception:
                period_end = period_start
        scope = qs(q, 'scope', 'all')
        building = qs(q, 'building')
        db = get_db()
        sql = '''SELECT b.*,r.building,r.unit,r.room_number,r.category,s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,f.name ft,o.name owner_name,
               COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid,
               a.old_amount adj_old,a.new_amount adj_new,a.reason adj_reason,a.created_at adj_time
               FROM bills b
               LEFT JOIN rooms r ON b.room_id=r.id
               LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
               LEFT JOIN fee_types f ON b.fee_type_id=f.id
               LEFT JOIN owners o ON b.owner_id=o.id
               LEFT JOIN bill_adjustments a ON a.id=(SELECT id FROM bill_adjustments WHERE bill_id=b.id ORDER BY created_at DESC,id DESC LIMIT 1)
               WHERE 1=1'''
        vals = []
        if period_start or period_end:
            sql, vals = append_natural_date_range_filter(sql, vals, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        elif period:
            sql, vals = append_period_filter(sql, vals, period, 'b.billing_period')
        if building:
            sql += " AND (r.building=? OR (?='商场' AND b.commercial_space_id IS NOT NULL))"; vals.extend([building, building])
        if scope == 'adjusted':
            sql += ' AND a.id IS NOT NULL'
        elif scope == 'unpaid':
            sql += " AND b.status IN ('unpaid','overdue','partial')"
        review_area_order = business_area_order_sql("COALESCE(r.building,'商场')", "COALESCE(r.unit,'商场')")
        sql += f" ORDER BY CASE WHEN a.id IS NOT NULL THEN 0 ELSE 1 END,{review_area_order},COALESCE(r.building,'商场'),r.unit,COALESCE(r.room_number,s.space_no),b.fee_type_id LIMIT 200"
        rows = db.execute(sql, vals).fetchall()
        total_adj = sum(1 for r in rows if r['adj_new'] is not None)
        amount_total = sum(float(r['amount'] or 0) for r in rows)
        blds = db.execute("SELECT building FROM (SELECT DISTINCT building FROM rooms UNION SELECT '商场' WHERE EXISTS (SELECT 1 FROM commercial_spaces)) ORDER BY building").fetchall()
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
            room = _bill_target_label(r)
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
        <div class="page-intro">
          <div>
            <h2 class="mb-1">账单核对</h2>
          </div>
          <div class="export-actions">
            <a class="btn btn-outline-secondary btn-sm" href="/bills"><i class="bi bi-arrow-left"></i> 返回账单</a>
          </div>
        </div>
        <div class="row g-2 mb-3">
        <div class="col-md-4 col-6"><div class="summary-tile primary"><div class="label">显示账单</div><strong>{len(rows)}</strong></div></div>
        <div class="col-md-4 col-6"><div class="summary-tile warning"><div class="label">人工修正</div><strong>{total_adj}</strong></div></div>
        <div class="col-md-4 col-12"><div class="summary-tile success"><div class="label">金额合计</div><strong class="money">¥{m(amount_total)}</strong></div></div>
        </div>
        <div class="card mb-3"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><strong>核对筛选</strong></div><div class="card-body">
        <form method="GET" action="/bills/review" class="row g-2 align-items-end">
        <div class="col-md-3"><label>起始日期</label><input type="date" name="period_start" value="{h(period_start)}" class="form-control"></div>
        <div class="col-md-3"><label>截止日期</label><input type="date" name="period_end" value="{h(period_end)}" class="form-control"></div>
        <div class="col-md-2"><label>楼栋</label><select name="building" class="form-select">{bld_opts}</select></div>
        <div class="col-md-2"><label>核对范围</label><select name="scope" class="form-select">{scope_opts}</select></div>
        <div class="col-md-2 d-flex align-items-end"><button class="btn btn-primary me-2">筛选</button><a class="btn btn-outline-secondary" href="/bills">返回账单</a></div>
        </form></div></div>
        <div class="card"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><strong>核对明细</strong></div><div class="table-responsive">
        <table class="table table-sm mb-0"><thead><tr><th>类型</th><th>编号</th><th>房间</th><th>业主</th><th>收费项目</th><th class="text-end">原金额</th><th class="text-end">新金额</th><th>截止日</th><th>原因</th><th>操作</th></tr></thead><tbody>{body}</tbody></table>
        </div></div>
        ''', 'bills'))

    def _bills(self, q):
        update_overdue_bills()
        db=get_db()
        cleanup_invalid_payments(db)
        s=qs(q,'status');fid=qs(q,'fee_type_id');raw_period=qs(q,'period','').strip()
        period_start=qs(q,'period_start','').strip();period_end=qs(q,'period_end','').strip()
        p=raw_period if '~' in raw_period else (date_to_period(raw_period) if raw_period else '')
        if p and not period_start and not period_end:
            period_start = period_to_date(p.split('~', 1)[0])
            period_end = period_to_date(p.split('~', 1)[-1])
            try:
                y, mo = [int(x) for x in period_end[:7].split('-')]
                period_end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
            except Exception:
                period_end = period_end[:7] + '-31'
        kw=qs(q,'keyword');bld=qs(q,'building');cat=qs(q,'category');auto_batch_no=qs(q,'auto_batch_no')
        company_scope=qs(q,'company_scope')
        if company_scope not in ('property', 'commercial'):
            company_scope=''
        current_query = urllib.parse.urlencode([
            (k, v)
            for k, vals in q.items()
            for v in vals
            if v != ''
        ])
        current_path = '/bills' + (f'?{current_query}' if current_query else '')
        detail_back = urllib.parse.urlencode({'back': current_path})
        sql='''SELECT b.*,r.building,r.unit,r.room_number,r.floor,r.category,r.tenant_name,s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,f.name ft,o.name owner_name,
               COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
               FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN fee_types f ON b.fee_type_id=f.id LEFT JOIN owners o ON b.owner_id=o.id WHERE 1=1'''
        vals=[]
        if period_start or period_end:
            sql, vals = append_natural_date_range_filter(sql, vals, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        elif p:
            sql, vals = append_period_filter(sql, vals, p, 'b.billing_period')
        if s:sql+=" AND b.status=?";vals.append(s)
        if fid and fid!='0':sql+=" AND b.fee_type_id=?";vals.append(fid)
        if bld:sql+=" AND (r.building=? OR (?='商场' AND b.commercial_space_id IS NOT NULL))";vals.extend([bld,bld])
        if cat:sql+=" AND (r.category=? OR (? IN ('商户','商业') AND b.commercial_space_id IS NOT NULL))";vals.extend([cat,cat])
        if auto_batch_no:sql+=" AND b.auto_batch_no=?";vals.append(auto_batch_no)
        if kw:sql+=" AND (r.building LIKE ? OR r.room_number LIKE ? OR r.unit LIKE ? OR s.space_no LIKE ? OR s.shop_name LIKE ? OR s.merchant_name LIKE ?)";vals.extend([f'%{kw}%']*6)
        base_sql_for_scope_summary = sql
        base_vals_for_scope_summary = list(vals)
        sql += _bill_scope_condition(company_scope)
        area_order = business_area_order_sql("COALESCE(r.building,'商场')", "COALESCE(r.unit,'商场')")
        sql += f" ORDER BY {area_order},COALESCE(r.building,'商场'),r.unit,COALESCE(r.room_number,s.space_no),b.fee_type_id"
        pg=parse_page(qs(q,'page','1'))
        per_page=parse_per_page(qs(q,'per_page','50'))
        total_rows=db.execute("SELECT COUNT(*) FROM ("+sql+")",vals).fetchone()[0]
        summary=db.execute(
            "SELECT COUNT(DISTINCT COALESCE('r'||room_id,'s'||commercial_space_id)) rooms,COUNT(*) bills,COALESCE(SUM(amount),0) amount,"
            "COALESCE(SUM(paid),0) paid,SUM(CASE WHEN status IN ('unpaid','overdue') THEN 1 ELSE 0 END) unpaid,"
            "SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) paid_count FROM ("+sql+")",
            vals,
        ).fetchone()
        scope_summary_order = f" ORDER BY {area_order},COALESCE(r.building,'商场'),r.unit,COALESCE(r.room_number,s.space_no),b.fee_type_id"
        scope_summary = db.execute(
            "SELECT "
            "SUM(CASE WHEN commercial_space_id IS NOT NULL OR building='商场' OR unit='商场' THEN 0 ELSE 1 END) property_count,"
            "SUM(CASE WHEN commercial_space_id IS NOT NULL OR building='商场' OR unit='商场' THEN 1 ELSE 0 END) commercial_count,"
            "COALESCE(SUM(CASE WHEN commercial_space_id IS NOT NULL OR building='商场' OR unit='商场' THEN 0 ELSE amount-paid END),0) property_due,"
            "COALESCE(SUM(CASE WHEN commercial_space_id IS NOT NULL OR building='商场' OR unit='商场' THEN amount-paid ELSE 0 END),0) commercial_due "
            "FROM ("+base_sql_for_scope_summary+scope_summary_order+")",
            base_vals_for_scope_summary,
        ).fetchone()
        total_pages=max(1,(total_rows+per_page-1)//per_page)
        pg=clamp_page(pg,total_pages)
        sql+=" LIMIT ? OFFSET ?"
        vals.extend([per_page, (pg-1)*per_page])
        rows=db.execute(sql,vals).fetchall()
        fts=db.execute("SELECT * FROM fee_types ORDER BY sort_order").fetchall()
        blds=db.execute("SELECT building FROM (SELECT DISTINCT building FROM rooms UNION SELECT '商场' WHERE EXISTS (SELECT 1 FROM commercial_spaces)) ORDER BY building").fetchall()
        ta=summary['amount'];tp=summary['paid']
        t_unpaid=summary['unpaid'] or 0
        t_paid=summary['paid_count'] or 0
        t_rooms=summary['rooms'] or 0
        property_count = scope_summary['property_count'] or 0
        commercial_count = scope_summary['commercial_count'] or 0
        property_due = scope_summary['property_due'] or 0
        commercial_due = scope_summary['commercial_due'] or 0
        db.close()
        sn={'paid':'status-paid','unpaid':'status-unpaid','overdue':'status-overdue','partial':'status-partial'}
        ln={'paid':'已缴','unpaid':'未缴','overdue':'逾期','partial':'部分缴'}
        owner_groups={}
        for r in rows:
            on=h(_bill_customer_name(r))
            scope = _bill_scope_label(r)
            group_key = f'{scope}|{on}'
            if group_key not in owner_groups:
                owner_groups[group_key] = {'scope': scope, 'owner': on, 'rooms': {}}
            rid=('space', r['commercial_space_id']) if r['commercial_space_id'] else ('room', r['room_id'])
            rn=h(_bill_target_label(r))
            if rid not in owner_groups[group_key]['rooms']:
                owner_groups[group_key]['rooms'][rid]={'name':rn,'bills':[]}
            owner_groups[group_key]['rooms'][rid]['bills'].append(r)
        rh=''
        oidx=0
        def _scope_order(item):
            og = item[1]
            return (0 if og['scope'] == '物业公司收费' else 1, og['owner'])
        for _, og in sorted(owner_groups.items(), key=_scope_order):
            oidx+=1
            owner_group = f'o{oidx}'
            o_total=sum(b['amount'] for rl in og['rooms'].values() for b in rl['bills'])
            o_paid=sum(b['paid'] for rl in og['rooms'].values() for b in rl['bills'])
            o_rem=o_total-o_paid
            o_rem_html = f'<strong class="money money-due">¥{m(o_rem)}</strong>' if o_rem>0 else '<span class="money money-paid">¥0.00</span>'
            owner_chk = f'<input type="checkbox" class="owner-group-chk" data-owner-group="{owner_group}" title="选择该租户下全部账单" onclick="event.stopPropagation();toggleBillGroup(\'owner\',\'{owner_group}\',this.checked)">'
            rh+=f'<tr class="table-secondary" onclick="toggleRoom(\'{owner_group}\')" style="cursor:pointer">'
            object_chips = ''.join(f'<span class="bill-object-chip">{h(name)}</span>' for name in sorted(rl['name'] for rl in og['rooms'].values()))
            inline_codes = ''.join(f'<span class="bill-inline-code">{h(_bill_object_code(rl["bills"][0]))}</span>' for rl in og['rooms'].values() if _bill_object_code(rl['bills'][0]) and _bill_object_code(rl['bills'][0]) != rl['name'])
            rh+=f'<td>{owner_chk}</td><td><div class="bill-owner-line"><i class="bi bi-chevron-right" id="icon_{owner_group}"></i> <strong>{og["owner"]}</strong> <span class="badge bg-light text-dark ms-1">{len(og["rooms"])}间</span><span class="bill-object-chips">{object_chips}</span>{inline_codes}</div></td>'
            rh+=f'<td><span class="badge status-info">{og["scope"]}</span></td>'
            rh+=f'<td></td>'
            rh+=f'<td></td>'
            owner_bills = [b for rl in og['rooms'].values() for b in rl['bills']]
            rh+=f'<td><small class="text-muted">{h(_bill_group_hint(owner_bills))}</small></td><td class="text-end"><span class="money">¥{m(o_total)}</span></td><td class="text-end"><span class="money money-paid">¥{m(o_paid)}</span></td>'
            rh+=f'<td class="text-end">{o_rem_html}</td>'
            rh+=f'<td></td><td></td></tr>'
            for ridx, (rid, rl) in enumerate(og['rooms'].items(), 1):
                room_group = f'{owner_group}r{ridx}'
                r_total=sum(b['amount'] for b in rl['bills'])
                r_paid=sum(b['paid'] for b in rl['bills'])
                r_rem=r_total-r_paid
                r_rem_html = f'<strong class="money money-due">¥{m(r_rem)}</strong>' if r_rem>0 else '<span class="money money-paid">¥0.00</span>'
                room_chk = f'<input type="checkbox" class="room-group-chk" data-owner-group="{owner_group}" data-room-group="{room_group}" title="选择该房间下全部账单" onclick="event.stopPropagation();toggleBillGroup(\'room\',\'{room_group}\',this.checked)">'
                rh+=f'<tr class="room-detail-{owner_group} bill-room-row" onclick="toggleBillRoom(\'{room_group}\')" style="display:none;background:#f8f9fa;cursor:pointer">'
                rh+=f'<td>{room_chk}</td><td style="padding-left:25px"><i class="bi bi-chevron-right" id="icon_{room_group}"></i> <strong>{rl["name"]}</strong><span class="visually-hidden">房间：{rl["name"]}</span></td>'
                rh+=f'<td><span class="badge status-info">{og["scope"]}</span></td>'
                rh+=f'<td>{h(_bill_room_label(rl["bills"][0]))}</td><td><small class="text-muted">{h(_bill_group_hint(rl["bills"]))}</small></td><td class="text-end"><span class="money">¥{m(r_total)}</span></td><td class="text-end"><span class="money money-paid">¥{m(r_paid)}</span></td>'
                rh+=f'<td class="text-end">{r_rem_html}</td>'
                rh+=f'<td></td>'
                rh+=f'<td></td>'
                rh+=f'<td></td></tr>'
                for b in rl['bills']:
                    rem=b['amount']-b['paid']
                    rem_html = f'<strong class="money money-due">¥{m(rem)}</strong>' if rem>0 else '<span class="money money-paid">¥0.00</span>'
                    chk=f'<input type=checkbox name=bill_ids value="{b["id"]}" class=bill-chk form="billActionForm" data-owner-group="{owner_group}" data-room-group="{room_group}">'
                    rh+=f'<tr class="bill-detail-{room_group}" style="display:none">'
                    rh+=f'<td>{chk}</td>'
                    rh+=f'<td><small>{h(b["bill_number"]or"-")}</small><div class="small text-muted">{h(_bill_customer_name(b))}</div></td>'
                    rh+=f'<td><span class="badge status-info">{og["scope"]}</span></td>'
                    rh+=f'<td>{h(_bill_room_label(b))}</td>'
                    rh+=f'<td><span class="badge status-info">{h(b["ft"])}</span></td>'
                    if b['service_start'] and b['service_end']:
                        period_text = f'{h(b["service_start"])} 至 {h(b["service_end"])}'
                    else:
                        period_text = h(b["billing_period"])
                    rh+=f'<td>{period_text}</td>'
                    rh+=f'<td class="text-end"><span class="money">¥{m(b["amount"])}</span></td><td class="text-end"><span class="money money-paid">¥{m(b["paid"])}</span></td>'
                    rh+=f'<td class="text-end">{rem_html}</td>'
                    rh+=f'<td><span class="badge {sn.get(b["status"],"status-neutral")}">{ln.get(b["status"],b["status"])}</span></td>'
                    back_q = urllib.parse.urlencode({'back': current_path})
                    rh+=f'<td><a href="/bills/{b["id"]}?{detail_back}" class="btn btn-sm btn-outline-secondary bill-row-action"><i class="bi bi-eye"></i></a>'
                    rh+=f'<a href="/bills/{b["id"]}/edit?{back_q}" class="btn btn-sm btn-outline-warning bill-row-action"><i class="bi bi-pencil"></i></a>'
                    if b['status']!='paid': rh+=f'<a href="/bills/{b["id"]}/pay?{back_q}" class="btn btn-sm btn-outline-primary bill-row-action"><i class="bi bi-credit-card"></i></a>'
                    rh+=f'<form method=POST action="/bills/{b["id"]}/delete" style=display:inline class="bill-row-action" onsubmit="rememberBillsBeforeLeave();return confirm(\'确定删除？已有缴费记录的账单无法删除！\')"><input type="hidden" name="back" value="{h(current_path)}"><button type="submit" class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'
        ft_opts='<option value="">全部类型</option>'+''.join(f'<option value="{f["id"]}"{" selected" if fid==str(f["id"]) else""}>{h(f["name"])}</option>' for f in fts)
        bld_opts='<option value="">全部楼栋</option>'+''.join(f'<option value="{h(b["building"])}"{" selected" if bld==b["building"] else""}>{h(b["building"])}</option>' for b in blds)
        tpl=self._load_template('bills.html')
        batch_notice = ''
        if auto_batch_no:
            batch_notice = f'''<div class="alert alert-info d-flex flex-wrap justify-content-between align-items-center gap-2">
            <div>当前正在查看自动出账批次 <code>{h(auto_batch_no)}</code></div>
            <div><a class="btn btn-sm btn-outline-primary" href="/auto_billing/runs/{h(auto_batch_no)}">返回批次详情</a>
            <a class="btn btn-sm btn-outline-secondary" href="/bills">清除批次筛选</a></div></div>'''
        tpl = batch_notice + tpl
        tpl=tpl.replace('{PERIOD_START}',h(period_start)).replace('{PERIOD_END}',h(period_end)).replace('{FT_OPTS}',ft_opts).replace('{BLD_OPTS}',bld_opts)
        tpl=tpl.replace('{KW}',h(kw))
        tpl=tpl.replace('{COMPANY_SCOPE_FIELD}', f'<input type="hidden" name="company_scope" value="{h(company_scope)}">' if company_scope else '')
        tpl=tpl.replace('<form method=POST id="billActionForm"></form>',
                        f'<form method=POST id="billActionForm"><input type="hidden" name="back" value="{h(current_path)}"></form>')
        tpl=tpl.replace('{SUN}',' selected' if s=='unpaid' else '').replace('{SPA}',' selected' if s=='paid' else '')
        tpl=tpl.replace('{SOV}',' selected' if s=='overdue' else '')
        tpl=tpl.replace('{ROOMS}',str(t_rooms)).replace('{COUNT}',str(total_rows))
        tpl=tpl.replace('{TOTAL_ROWS}',str(total_rows)).replace('{PAGE}',str(pg)).replace('{TOTAL_PAGES}',str(total_pages))
        tpl=tpl.replace('{TOTAL_AMT}',m(ta)).replace('{TOTAL_PAID}',m(tp))
        tpl=tpl.replace('{UNPAID_CNT}',str(t_unpaid))
        property_url = _bill_scope_url('property', period_start, period_end, s, fid, bld, cat, kw, auto_batch_no)
        commercial_url = _bill_scope_url('commercial', period_start, period_end, s, fid, bld, cat, kw, auto_batch_no)
        all_url = _bill_scope_url('', period_start, period_end, s, fid, bld, cat, kw, auto_batch_no)
        active_all = ' active' if not company_scope else ''
        active_property = ' active' if company_scope == 'property' else ''
        active_commercial = ' active' if company_scope == 'commercial' else ''
        all_current = ' aria-current="page"' if not company_scope else ''
        property_current = ' aria-current="page"' if company_scope == 'property' else ''
        commercial_current = ' aria-current="page"' if company_scope == 'commercial' else ''
        scope_summary_html = f'''
        <a class="ledger-scope-chip all{active_all}" href="{h(all_url)}"{all_current}><i class="bi bi-layers"></i> 全部账单 <strong>{property_count + commercial_count}笔</strong></a>
        <a class="ledger-scope-chip property{active_property}" href="{h(property_url)}"{property_current}><i class="bi bi-building"></i> 物业公司收费 <strong>{property_count}笔</strong><em>欠费¥{m(property_due)}</em></a>
        <a class="ledger-scope-chip commercial{active_commercial}" href="{h(commercial_url)}"{commercial_current}><i class="bi bi-shop"></i> 商业公司收费 <strong>{commercial_count}笔</strong><em>欠费¥{m(commercial_due)}</em></a>
        '''
        tpl=tpl.replace('{BILL_SCOPE_SUMMARY}',scope_summary_html)
        has_unpaid=any(r['status']!='paid' for r in rows)
        paid_btn='<button class="btn btn-sm btn-primary" type="submit" form="billActionForm" formaction="/bills/batch_pay" formtarget="_self" formmethod="POST"><i class="bi bi-credit-card"></i> 缴费</button>'
        btn=f'''
        <div class="batch-bar">
        <a class="btn btn-sm btn-outline-primary" href="/bills/review?period_start={h(period_start)}&period_end={h(period_end)}"><i class="bi bi-clipboard-check"></i> 核对工作台</a>
        <small class="text-muted me-1"><i class="bi bi-info-circle"></i> 勾选后操作：</small>
        {paid_btn}
        <span class="export-actions">
        <button class="btn btn-sm btn-outline-secondary" type="button" onclick="submitBillAction('/bills/print_selected','_blank')"><i class="bi bi-printer"></i> 打印</button>
        <button class="btn btn-sm btn-outline-secondary" type="button" onclick="submitBillAction('/bills/receipt_by_ids','_blank')"><i class="bi bi-receipt"></i> 收据</button>
        <button class="btn btn-sm btn-outline-secondary" type="button" onclick="submitBillAction('/bills/export_selected','_self')"><i class="bi bi-download"></i> 导出</button>
        </span>
        <button class="btn btn-sm btn-outline-warning" type="button" onclick="submitBillAction('/bills/batch_edit','_self')"><i class="bi bi-pencil-square"></i> 批量修正</button>
        </div>'''
        tpl=tpl.replace('{BTN_TOP}',btn).replace('{BTN_BOTTOM}',btn)
        tpl=tpl.replace('{SUN}',' selected' if s=='unpaid' else '').replace('{SPA}',' selected' if s=='paid' else '')
        tpl=tpl.replace('{SOV}',' selected' if s=='overdue' else '').replace('{SPT}',' selected' if s=='partial' else '')
        page_query=[('period_start',period_start),('period_end',period_end),('status',s),('fee_type_id',fid),('building',bld),('category',cat),('keyword',kw),('company_scope',company_scope)]
        if auto_batch_no:
            page_query.append(('auto_batch_no', auto_batch_no))
        page_links=render_pagination('/bills', page_query, pg, total_pages, per_page, total_rows, '账单分页')
        tpl=tpl.replace('{PAGE_LINKS}',page_links)
        tpl=tpl.replace('{ROWS}',rh or '<tr><td colspan="11" class="text-center text-muted py-4">暂无账单</td></tr>')
        self._html(self._page('账单管理',tpl,'bills'))
