#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee types, tiers, late fee configuration."""

from server.db import get_db, get_period, get_fee_type_rate, h, m, qs
from server.base import BaseHandler
import json


class FeeMixin(BaseHandler):

    # ── 费用类型 ──────────────────────────────────────────────
    def _fee_types(self):
        import urllib.parse
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        selected_group = qs(q, 'group', '')
        group_defs = {
            'property': {
                'title': '物业公司', 'icon': 'bi-building-check',
                'desc': '物业基础收费项目：物业费、电梯费、二次供水、公摊和生活垃圾费。',
                'names': ['物业费(居民)', '物业费(商户)', '电梯费', '二次供水运行费', '公摊能耗费', '生活垃圾费'],
            },
            'commercial': {
                'title': '商业公司', 'icon': 'bi-shop',
                'desc': '商业经营相关收费项目：电费、装修、泄水、空调能源等。',
                'names': ['电费(商业)', '装修管理费', '装修押金', '泄水费', '空调能源费', '空调费(商业)'],
            },
            'other': {
                'title': '其他', 'icon': 'bi-three-dots',
                'desc': '水费档位、停车费、临时收费和其他专项费用。',
                'names': ['垃圾清运费', '水费(非居民)', '水费(特行)', '停车费', '临时收费'],
            },
        }
        db = get_db()
        all_rows = db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order").fetchall()
        period = get_period()
        calc_n = {'area':'按面积×单价','meter':'按用量×单价','floor':'电梯阶梯','fixed':'固定金额','household':'按户分摊'}

        def metric_for(fid):
            bc = db.execute("SELECT COUNT(*) FROM bills WHERE fee_type_id=? AND billing_period=?", (fid, period)).fetchone()[0]
            bt = db.execute("SELECT COALESCE(SUM(amount),0) FROM bills WHERE fee_type_id=? AND billing_period=?", (fid, period)).fetchone()[0]
            rc = db.execute("SELECT COUNT(DISTINCT room_id) FROM bills WHERE fee_type_id=?", (fid,)).fetchone()[0]
            return bc, bt, rc

        def card_for(r):
            bc, bt, rc = metric_for(r['id'])
            cat_hint = ''
            for kw, lb in [('居民','居民'), ('商户','商户'), ('非居民','水费非居民档'), ('特行','水费特行档')]:
                if kw in r['name']:
                    cat_hint = '<span class="badge status-neutral">' + lb + '</span> '
                    break
            notes_html = '<p class="text-muted small mt-1 mb-0">' + h(r['notes'] or '') + '</p>' if r['notes'] else ''
            html = '<div class="col-md-6 col-lg-4 mb-3"><div class="card fee-card h-100"><div class="card-body">'
            html += '<div class="d-flex justify-content-between gap-2"><h5>' + h(r['name']) + '</h5><div>'
            html += '<a href="/fee_types/' + str(r['id']) + '/edit" class="btn btn-sm btn-outline-primary"><i class="bi bi-pencil"></i></a>'
            html += '<form method=POST action="/fee_types/' + str(r['id']) + '/delete" style=display:inline onsubmit="return confirm(\'确定删除？\')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></div></div>'
            html += '<hr><div class="row text-center"><div class="col-4 border-end"><small class="text-muted d-block">计算方式</small><span class="badge status-info">' + calc_n.get(r['calc_method'], r['calc_method']) + '</span></div>'
            html += '<div class="col-4 border-end"><small class="text-muted d-block">单价</small><strong class="fee-price">¥' + m(r['unit_price']) + '</strong></div>'
            html += '<div class="col-4"><small class="text-muted d-block">适用</small>' + cat_hint + '</div></div>'
            html += '<hr class="my-2"><div class="row text-center small"><div class="col-4"><span class="text-muted">本月</span><br><strong>' + str(bc) + '笔</strong></div><div class="col-4"><span class="text-muted">应收</span><br><strong class="money">¥' + m(bt) + '</strong></div><div class="col-4"><span class="text-muted">涉及</span><br><strong>' + str(rc) + '户</strong></div></div>'
            html += notes_html + '</div></div></div>'
            return html

        rows_by_name = {r['name']: r for r in all_rows}

        def _belongs_to_fee_group(row, group_key, defs):
            name = row['name'] or ''
            if name in set(defs[group_key]['names']):
                return True
            sort_order = row['sort_order'] or 0
            if group_key == 'commercial':
                return 30 <= sort_order < 50
            if group_key == 'property':
                return 1 <= sort_order < 30 and name not in set(defs['other']['names'])
            if group_key == 'other':
                return sort_order >= 50
            return False

        if selected_group in group_defs:
            gd = group_defs[selected_group]
            ordered = []
            for name in gd['names']:
                if name in rows_by_name and rows_by_name[name] not in ordered:
                    ordered.append(rows_by_name[name])
            selected_names = set(gd['names'])
            for r in all_rows:
                if _belongs_to_fee_group(r, selected_group, group_defs) and r not in ordered:
                    ordered.append(r)
            rh = ''.join(card_for(r) for r in ordered)
            header = '<div class="page-intro"><div><p class="text-muted mb-1 small">收费标准分组</p><h4 class="mb-0"><i class="bi ' + gd['icon'] + '"></i> ' + gd['title'] + '</h4><p class="text-muted small mb-0 mt-2">' + gd['desc'] + '</p></div><div class="export-actions"><a href="/fee_types" class="btn btn-outline-secondary btn-sm"><i class="bi bi-arrow-left"></i> 返回分组</a><a href="/fee_types/create?group=' + h(selected_group) + '" class="btn btn-primary btn-sm"><i class="bi bi-plus-lg"></i> 添加</a></div></div>'
            content = header + '<div class="row">' + (rh or '<div class="col-12 text-center text-muted py-5">该分组暂无收费项目</div>') + '</div>'
            db.close()
            return self._html(self._page(gd['title'], content, 'fee_types'))

        group_cards = ''
        for key, gd in group_defs.items():
            present = [r for r in all_rows if _belongs_to_fee_group(r, key, group_defs)]
            names_preview = '、'.join([h(r['name']) for r in present[:6]]) or '暂无项目'
            group_cards += '<div class="col-md-4 mb-3"><a href="/fee_types?group=' + key + '" class="text-decoration-none text-reset"><div class="card fee-card h-100"><div class="card-body">'
            group_cards += '<div class="d-flex align-items-center gap-3 mb-3"><div class="page-icon"><i class="bi ' + gd['icon'] + '"></i></div><div><h4 class="mb-1">' + gd['title'] + '</h4><small class="text-muted">' + str(len(present)) + ' 个收费项目</small></div></div>'
            group_cards += '<p class="text-muted small">' + gd['desc'] + '</p><hr><div class="small text-muted">' + names_preview + '</div><div class="mt-3"><span class="btn btn-sm btn-outline-primary">进入查看 <i class="bi bi-arrow-right"></i></span></div>'
            group_cards += '</div></div></a></div>'
        db.close()
        content = self._load_template('fee_types.html')
        content = content.replace('{CARDS}', group_cards)
        self._html(self._page('收费标准', content, 'fee_types'))

    def _fee_type_form(self, fid, group=''):
        db=get_db();ft=None;tiers=[]
        if fid:
            ft=db.execute("SELECT * FROM fee_types WHERE id=?",(fid,)).fetchone()
            tiers=db.execute("SELECT * FROM fee_type_tiers WHERE fee_type_id=? ORDER BY is_default DESC", (fid,)).fetchall()
        rooms=db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.building,r.room_number").fetchall()
        db.close()
        a=f'/fee_types/{fid}/edit' if fid else '/fee_types/create'
        group_titles = {'property': '物业公司', 'commercial': '商业公司', 'other': '其他'}
        group_title = group_titles.get(group, '')
        t='编辑费用类型' if fid else (f'添加{group_title}收费项目' if group_title else '添加费用类型')
        n=h(ft['name'] if ft else '');cm=ft['calc_method'] if ft else 'area'
        up=ft['unit_price'] if ft else 0;u=h(ft['unit'] or'') if ft else '';rad=ft['reminder_advance_days'] if ft and ft['reminder_advance_days'] else 30
        bc=ft['billing_cycle'] if ft else 'monthly';so=ft['sort_order'] if ft else 0
        ia=(ft and ft['is_active']!=0) if ft else True;nt=h(ft['notes'] or'') if ft else ''

        # 费用类型预设模板
        templates = [
            # 金莎物业公司
            {"group":"金莎物业","name":"物业费(居民)","calc":"area","price":1.9,"unit":"元/m2.月","cycle":"monthly","sort":1,"notes":"按建筑面积x1.9","rad":30,"tiers":{"居民":1.9}},
            {"group":"金莎物业","name":"物业费(商户)","calc":"area","price":5.0,"unit":"元/m2.月","cycle":"monthly","sort":2,"notes":"按建筑面积x5.0","rad":30,"tiers":{"商户":5.0}},
            {"group":"金莎物业","name":"电梯费","calc":"floor","price":1.0,"unit":"元/m2.月","cycle":"monthly","sort":3,"notes":"按楼层阶梯x面积","rad":30,"tiers":{}},
            {"group":"金莎物业","name":"二次供水运行费","calc":"area","price":0.5,"unit":"元/m2.月","cycle":"monthly","sort":4,"notes":"面积x0.5","rad":30,"tiers":{}},
            {"group":"金莎物业","name":"生活垃圾费","calc":"household","price":10,"unit":"元/户.月","cycle":"monthly","sort":5,"notes":"按户收取10元","rad":30,"tiers":{}},
            {"group":"金莎物业","name":"公摊能耗费","calc":"household","price":10,"unit":"元/户.月","cycle":"monthly","sort":6,"notes":"按户收取10元","rad":30,"tiers":{}},
            {"group":"金莎物业","name":"水费(非居民)","calc":"meter","price":5.8,"unit":"元/m3","cycle":"monthly","sort":7,"notes":"用量x5.8","rad":15,"tiers":{}},
            {"group":"金莎物业","name":"水费(特行)","calc":"meter","price":20.11,"unit":"元/m3","cycle":"monthly","sort":8,"notes":"用量x20.11","rad":15,"tiers":{}},
            # 金莎商业公司
            {"group":"金莎商业","name":"物业费(商业)","calc":"area","price":5.0,"unit":"元/m2.月","cycle":"monthly","sort":11,"notes":"按建筑面积x单价","rad":30,"tiers":{"商户":5.0}},
            {"group":"金莎商业","name":"电费(商业)","calc":"meter","price":0.85,"unit":"元/度","cycle":"monthly","sort":12,"notes":"按用电量x0.85","rad":15,"tiers":{}},
            {"group":"金莎商业","name":"水费(商业)","calc":"meter","price":5.8,"unit":"元/m3","cycle":"monthly","sort":13,"notes":"按用水量x5.8","rad":15,"tiers":{}},
            {"group":"金莎商业","name":"垃圾清运费","calc":"household","price":30,"unit":"元/户","cycle":"monthly","sort":14,"notes":"按户收取","rad":15,"tiers":{}},
            {"group":"金莎商业","name":"装修管理费","calc":"area","price":3.0,"unit":"元/m2","cycle":"monthly","sort":15,"notes":"装修期间按面积收","rad":7,"tiers":{"商户":3.0,"居民":2.0}},
            {"group":"金莎商业","name":"装修押金","calc":"fixed","price":2000,"unit":"元","cycle":"monthly","sort":16,"notes":"验收合格后退还","rad":7,"tiers":{}},
            {"group":"金莎商业","name":"泄水费","calc":"area","price":1.5,"unit":"元/m2.月","cycle":"monthly","sort":17,"notes":"排水设施维护费","rad":30,"tiers":{"商户":1.5,"居民":0.8}},
        ]

        # 模板卡片（按公司分组）
        template_section = ""
        if not fid:
            groups = {"金莎物业": "金莎物业公司", "金莎商业": "金莎商业公司"}
            tc = ""
            for gkey, glabel in groups.items():
                tc += '<div class="w-100 mb-1 mt-2"><strong><i class="bi bi-building"></i> ' + glabel + '</strong></div>'
                for i, tp in enumerate(templates):
                    if tp.get("group") != gkey:
                        continue
                    label = tp["calc"] + " - ¥" + str(tp["price"]) if tp["price"] > 0 else tp["calc"] + " - 自定义"
                    tc += '<div class="col-4 col-md-2 mb-2"><div class="card template-card" style="cursor:pointer;height:100%" onclick="applyTemplate(' + str(i) + ')"><div class="card-body text-center p-2"><small class="d-block text-truncate"><strong>' + h(tp["name"]) + '</strong></small><small class="text-muted">' + label + '</small></div></div></div>'
            tc += '<div class="w-100 mt-2"><hr></div><div class="col-4 col-md-2 mb-2"><div class="card template-card" style="cursor:pointer;height:100%;border:2px dashed #adb5bd" onclick="applyTemplate(-1)"><div class="card-body text-center p-2"><small><strong>自定义</strong></small><br><small class="text-muted">从空白开始</small></div></div></div>'
            template_section = '<div class="card mb-3"><div class="card-header py-2"><i class="bi bi-template"></i> 选择模板</div><div class="card-body"><div class="row g-1">' + tc + '</div></div></div>'

        # 分档费率表
        tier_rows = ""
        for tier in tiers:
            cats = "".join(f'<option value="{c}"{" selected" if tier["category"]==c else ""}>{c}</option>' for c in ["居民","商户","非居民","特行"])
            tier_rows += "<tr><td><select name=\"tier_cat_" + str(tier["id"]) + "\" class=\"form-select form-select-sm\">" + cats + "</select></td>"
            tier_rows += "<td><input name=\"tier_rate_" + str(tier["id"]) + "\" type=\"number\" class=\"form-control form-control-sm\" value=\"" + str(tier["rate"]) + "\" step=\"0.01\" style=\"width:120px\"></td>"
            tier_rows += '<td><input type="checkbox" name="tier_id" value="' + str(tier['id']) + '" checked hidden><a href="#" class="text-danger" onclick="this.closest(\'tr\').remove()"><i class="bi bi-trash"></i></a></td></tr>'
        tier_table = "<div class=\"col-12\"><div class=\"tier-panel\"><h6><i class=\"bi bi-layers\"></i> 按类别分档费率 <small class=\"text-muted\">不同类别可用不同单价</small></h6>"
        tier_table += "<div class=\"table-responsive\"><table class=\"table table-hover\" id=\"tierTable\"><thead><tr><th>类别</th><th>费率（单价）</th><th style=\"width:60px\">操作</th></tr></thead><tbody>" + tier_rows
        tier_table += "<tr id=\"newTierRow\"><td><select class=\"form-select form-select-sm\" id=\"newTierCat\"><option value=\"居民\">居民</option><option value=\"商户\">商户</option><option value=\"非居民\">非居民</option><option value=\"特行\">特行</option></select></td>"
        tier_table += "<td><input type=\"number\" class=\"form-control form-control-sm\" id=\"newTierRate\" step=\"0.01\" style=\"width:120px\" placeholder=\"单价\"></td>"
        tier_table += '<td><button type="button" class="btn btn-sm btn-outline-success" onclick="addTierRow()"><i class="bi bi-plus"></i></button></td></tr></tbody></table></div><small class="text-muted">按房间类别分别定价，生成账单时自动匹配对应档位费率。</small></div></div>'

        calc_opts = "<option value=\"area\">按面积×单价</option><option value=\"meter\">按用量×单价</option><option value=\"floor\">电梯费阶梯</option><option value=\"fixed\">固定金额</option><option value=\"household\">按户分摊</option>"
        cycle_opts = "<option value=\"daily\">每日</option><option value=\"monthly\">每月</option><option value=\"quarterly\">每季度</option><option value=\"yearly\">每年</option>"
        tmpl_json = json.dumps(templates, ensure_ascii=False)

        self._html(self._page(t, f"""
{template_section}
<form method=POST action="{a}" class="row g-3">
<input type="hidden" name="return_group" value="{h(group)}">
<div class="col-md-8"><label>名称 <span class="text-danger">*</span></label><input name="name" class="form-control" value="{n}" required id="ftName"></div>
<div class="col-md-4"><label>启用</label><div class="form-check mt-2"><input class="form-check-input" type="checkbox" name="is_active" id="ia" {"checked" if ia else ""}><label class="form-check-label" for="ia">已启用</label></div></div>
<div class="col-md-3"><label>计算方式 <span class="text-danger">*</span></label><select name="calc_method" class="form-select" id="ftCalc">{calc_opts}</select></div>
<div class="col-md-3"><label>默认单价 <span class="text-danger">*</span></label><div class="input-group"><span class="input-group-text">¥</span><input name="unit_price" type="number" class="form-control" value="{up}" step="0.01" required id="ftPrice"></div></div>
<div class="col-md-3"><label>单位</label><input name="unit" class="form-control" value="{u}" id="ftUnit" placeholder="如：元/m2.月"></div>
<div class="col-md-3"><label>出账周期</label><select name="billing_cycle" class="form-select" id="ftCycle">{cycle_opts}</select></div>
<div class="col-md-3"><label>催缴提前（天）</label><input name="reminder_advance_days" type="number" class="form-control" value="{rad}" min="0" max="90" id="ftRad"><small class="text-muted">到期前多少天开始催缴提醒</small></div>
<div class="col-md-3"><label>排序</label><input name="sort_order" type="number" class="form-control" value="{so}" id="ftSort"></div>
<div class="col-12"><label>说明 <small class="text-muted">标注计算方式和适用对象</small></label><input name="notes" class="form-control" value="{nt}" id="ftNotes" placeholder="例如：按建筑面积x单价计算"></div>
{tier_table}
<div style="display:none" id="tmplData">{tmpl_json}</div>
<div class="col-12"><hr><button class="btn btn-primary btn-lg"><i class="bi bi-check-lg"></i> 保存</button> <a href="/fee_types" class="btn btn-outline-secondary btn-lg">取消</a></div></form>""" + """
<script>
var TEMPLATES = JSON.parse(document.getElementById("tmplData").textContent);
function addReadonlyTierRow(cat, rate){
var tbody=document.querySelector("#tierTable tbody");
var tr=document.createElement("tr");
var catTd=document.createElement("td");
var catInput=document.createElement("input");
catInput.name="new_tier_cat";
catInput.value=cat;
catInput.readOnly=true;
catInput.className="form-control-plaintext form-control-sm";
catTd.appendChild(catInput);
var rateTd=document.createElement("td");
var rateInput=document.createElement("input");
rateInput.name="new_tier_rate";
rateInput.value=rate;
rateInput.readOnly=true;
rateInput.className="form-control-plaintext form-control-sm";
rateTd.appendChild(rateInput);
rateTd.appendChild(document.createTextNode(" 元"));
var actionTd=document.createElement("td");
var remove=document.createElement("a");
remove.href="#";
remove.className="text-danger";
remove.innerHTML='<i class="bi bi-trash"></i>';
remove.onclick=function(e){e.preventDefault();tr.remove();};
actionTd.appendChild(remove);
tr.appendChild(catTd);
tr.appendChild(rateTd);
tr.appendChild(actionTd);
tbody.insertBefore(tr, document.getElementById("newTierRow"));
}
function applyTemplate(idx){
if(idx<0||idx>=TEMPLATES.length){
document.getElementById("ftName").value="";document.getElementById("ftPrice").value="";document.getElementById("ftUnit").value="";document.getElementById("ftSort").value="";document.getElementById("ftNotes").value="";document.getElementById("ftRad").value="30";return;
}
var t=TEMPLATES[idx];
document.getElementById("ftName").value=t.name;
document.getElementById("ftCalc").value=t.calc;
document.getElementById("ftPrice").value=t.price;
document.getElementById("ftUnit").value=t.unit;
document.getElementById("ftCycle").value=t.cycle;
document.getElementById("ftSort").value=t.sort;
document.getElementById("ftNotes").value=t.notes;
document.getElementById("ftRad").value=t.rad;
var tbody=document.querySelector("#tierTable tbody");
if(tbody){
var rows=tbody.querySelectorAll("tr:not(#newTierRow)");
rows.forEach(function(r){r.remove();});
for(var cat in t.tiers){
var rate=t.tiers[cat];
if(cat&&rate){
addReadonlyTierRow(cat, rate);
}
}
}
}
function addTierRow(){
var cat=document.getElementById("newTierCat").value;
var rate=document.getElementById("newTierRate").value;
if(!rate){alert("请输入费率");return;}
addReadonlyTierRow(cat, rate);
document.getElementById("newTierRate").value="";
}
</script>
<style>.template-card .card-body{{padding:.5rem}}.template-card:hover .card-body{{background:#f0f7ff}}</style>
""",'fee_types'))

    def _fee_type_create(self, d):
        db=get_db()
        return_group = qs(d, 'return_group')
        cur = db.execute("INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes,reminder_advance_days) VALUES(?,?,?,?,?,?,?,?,?)",
                         (qs(d,'name'),qs(d,'calc_method'),float(qs(d,'unit_price',0)),qs(d,'unit'),qs(d,'billing_cycle','monthly'),
                          int(qs(d,'sort_order',0)),1 if qs(d,'is_active') else 0,qs(d,'notes'),int(qs(d,'reminder_advance_days',30))))
        fid = cur.lastrowid
        new_cats = d.get('new_tier_cat', [])
        new_rates = d.get('new_tier_rate', [])
        if isinstance(new_cats, str): new_cats = [new_cats]
        if isinstance(new_rates, str): new_rates = [new_rates]
        for nc, nr in zip(new_cats, new_rates):
            if nc.strip() and nr.strip():
                db.execute("INSERT INTO fee_type_tiers(fee_type_id,category,rate) VALUES(?,?,?)", (fid, nc.strip(), float(nr.strip())))
        db.commit();db.close()
        suffix = f'?group={return_group}&flash=添加成功' if return_group in ('property','commercial','other') else '?flash=添加成功'
        self._redirect('/fee_types' + suffix)

    def _fee_type_edit(self, fid, d):
        db=get_db()
        db.execute("UPDATE fee_types SET name=?,calc_method=?,unit_price=?,unit=?,billing_cycle=?,sort_order=?,is_active=?,notes=?,reminder_advance_days=? WHERE id=?",
                   (qs(d,'name'),qs(d,'calc_method'),float(qs(d,'unit_price',0)),qs(d,'unit'),qs(d,'billing_cycle','monthly'),
                    int(qs(d,'sort_order',0)),1 if qs(d,'is_active') else 0,qs(d,'notes'),int(qs(d,'reminder_advance_days',30)),fid))
        tier_ids = d.get('tier_id', [])
        if isinstance(tier_ids, str): tier_ids = [tier_ids]
        for tid in tier_ids:
            if not tid.strip(): continue
            cat = qs(d, f'tier_cat_{tid}', '')
            rate = qs(d, f'tier_rate_{tid}', '')
            if cat and rate:
                db.execute("UPDATE fee_type_tiers SET category=?,rate=? WHERE id=?", (cat, float(rate), int(tid)))
        new_cats = d.get('new_tier_cat', [])
        new_rates = d.get('new_tier_rate', [])
        if isinstance(new_cats, str): new_cats = [new_cats]
        if isinstance(new_rates, str): new_rates = [new_rates]
        for nc, nr in zip(new_cats, new_rates):
            if nc.strip() and nr.strip():
                db.execute("INSERT INTO fee_type_tiers(fee_type_id,category,rate) VALUES(?,?,?)", (fid, nc.strip(), float(nr.strip())))
        db.commit();db.close()
        self._redirect('/fee_types?flash=更新成功')

    def _fee_type_delete(self, fid):
        db=get_db()
        bc=db.execute("SELECT COUNT(*) FROM bills WHERE fee_type_id=?",(fid,)).fetchone()[0]
        mc=db.execute("SELECT COUNT(*) FROM meter_readings WHERE fee_type_id=?",(fid,)).fetchone()[0]
        if bc>0 or mc>0:
            details=[]
            if bc>0: details.append(f'{bc}条账单')
            if mc>0: details.append(f'{mc}条抄表记录')
            db.close()
            return self._redirect(f'/fee_types?flash=该费用类型下有{"、".join(details)}引用，无法删除')
        db.execute("DELETE FROM fee_types WHERE id=?",(fid,))
        db.commit();db.close()
        self._redirect('/fee_types?flash=已删除')

    # ── 电梯费阶梯设置 ──────────────────────────────────────────
    def _elevator_tiers(self):
        db=get_db()
        tiers=db.execute("SELECT * FROM elevator_fee_tiers ORDER BY floor_from").fetchall()
        db.close()
        rows=chr(10).join(f"""<tr>
<td><input name="ids" type="hidden" value="{t["id"]}">
<input name="floor_from_{t["id"]}" class="form-control form-control-sm" value="{t["floor_from"]}" style="width:70px;display:inline"></td>
<td><input name="floor_to_{t["id"]}" class="form-control form-control-sm" value="{t["floor_to"]}" style="width:70px;display:inline"></td>
<td><input name="rate_{t["id"]}" class="form-control form-control-sm" value="{t["rate"]}" step="0.01" style="width:100px;display:inline"> 元/m²</td>
</tr>""" for t in tiers)
        self._html(self._page("电梯费阶梯设置",f"""<div class="alert alert-info"><i class="bi bi-info-circle"></i> 电梯费 = 楼层对应单价 × 房屋面积。修改后会影响下次生成的账单。</div>
<form method=POST action="/elevator_tiers/update" class="card"><div class="card-body">
<table class="table"><thead><tr><th>起始楼层</th><th>结束楼层</th><th>单价(元/m²)</th></tr></thead><tbody>{rows}</tbody></table>
<button class="btn btn-primary"><i class="bi bi-save"></i> 保存修改</button>
<a href="/fee_types" class="btn btn-outline-secondary">返回费用类型</a>
</div></form>""","fee_types"))

    def _elevator_tiers_update(self, d):
        db=get_db()
        ids_list = d.get("ids", [])
        if isinstance(ids_list, str): ids_list = [ids_list]
        for tid in ids_list:
            if not tid.strip(): continue
            fr = int(qs(d,f"floor_from_{tid}",0))
            to = int(qs(d,f"floor_to_{tid}",0))
            rate = float(qs(d,f"rate_{tid}",0))
            db.execute("UPDATE elevator_fee_tiers SET floor_from=?,floor_to=?,rate=? WHERE id=?", (fr,to,rate,tid))
        db.commit();db.close()
        self._redirect("/elevator_tiers?flash=电梯费阶梯已更新")

    # ── 滞纳金设置 ──────────────────────────────────────────
    def _late_fee_config(self):
        db=get_db()
        cfg=db.execute("SELECT * FROM late_fee_config WHERE id=1").fetchone()
        db.close()
        en='checked' if cfg and cfg['is_active'] else ''
        dr=cfg['daily_rate'] if cfg else 0.001
        mr=cfg['max_rate'] if cfg else 0.05
        gd=cfg['grace_days'] if cfg else 0
        self._html(self._page('滞纳金设置',f'''
<div class="alert alert-info"><i class="bi bi-info-circle"></i> 滞纳金 = 欠费金额 × 日费率 × 逾期天数。账单逾期后自动计算，缴费时一并收取。</div>
<form method=POST action="/late_fee_config/update" class="card"><div class="card-body">
<div class="row g-3"><div class="col-md-6">
<div class="form-check mb-3"><input class="form-check-input" type="checkbox" name="is_active" id="is_active" {en}><label class="form-check-label" for="is_active">启用滞纳金</label></div>
<div class="mb-3"><label>日费率（默认千分之一）</label><div class="input-group"><input name="daily_rate" type="number" class="form-control" value="{dr}" step="0.0001" min="0"><span class="input-group-text">/天</span></div><small class="text-muted">例如0.001 = 每天千分之一</small></div>
<div class="mb-3"><label>最高费率限制</label><div class="input-group"><input name="max_rate" type="number" class="form-control" value="{mr}" step="0.01" min="0"><span class="input-group-text">上限</span></div><small class="text-muted">滞纳金最多不超过欠费金额的百分比</small></div>
<div class="mb-3"><label>宽限期（天）</label><input name="grace_days" type="number" class="form-control" value="{gd}" min="0"><small class="text-muted">到期后几天内不算滞纳金</small></div>
</div><div class="col-md-6"><div class="card bg-light"><div class="card-body"><h6>计算示例</h6>
<p>欠费1000元，逾期30天<br>日费率0.001（千分之一）<br>滞纳金 = 1000 × 0.001 × 30 = <strong>30元</strong></p>
<p class="text-muted small mb-0">最高不超过 1000 × 0.05 = 50元</p></div></div></div></div>
<hr><button class="btn btn-primary"><i class="bi bi-save"></i> 保存设置</button>
<a href="/bills" class="btn btn-outline-secondary">返回账单</a></div></form>''','fee_types'))

    def _late_fee_config_update(self, d):
        db=get_db()
        active=1 if qs(d,'is_active') else 0
        dr=float(qs(d,'daily_rate',0.001))
        mr=float(qs(d,'max_rate',0.05))
        gd=int(qs(d,'grace_days',0))
        c=db.execute("SELECT COUNT(*) FROM late_fee_config").fetchone()[0]
        if c==0:
            db.execute("INSERT INTO late_fee_config(name,daily_rate,max_rate,grace_days,is_active) VALUES('滞纳金',?,?,?,?)",(dr,mr,gd,active))
        else:
            db.execute("UPDATE late_fee_config SET daily_rate=?,max_rate=?,grace_days=?,is_active=? WHERE id=1",(dr,mr,gd,active))
        db.commit();db.close()
        self._redirect('/late_fee_config?flash=滞纳金设置已保存')
