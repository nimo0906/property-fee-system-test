from server.fees_shared import *

class FeeMixinPart1(BaseHandler):
    def _fee_types(self):
        import urllib.parse
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        selected_group = qs(q, 'group', '')
        group_defs = {
            'property': {
                'title': '物业公司', 'icon': 'bi-building-check',
                'desc': '物业基础收费项目：物业费、电梯费、二次供水、公摊和生活垃圾费。',
                'names': FEE_ADMIN_GROUP_NAMES['property'],
            },
            'commercial': {
                'title': '商业公司', 'icon': 'bi-shop',
                'desc': '商业经营相关收费项目：电费、装修、泄水、空调能源等。',
                'names': FEE_ADMIN_GROUP_NAMES['commercial'],
            },
            'other': {
                'title': '其他', 'icon': 'bi-three-dots',
                'desc': '水费档位、停车费、临时收费和其他专项费用。',
                'names': FEE_ADMIN_GROUP_NAMES['other'],
            },
        }
        db = get_db()
        all_rows = db.execute("SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order").fetchall()
        period = get_period()
        calc_n = {'area':'按面积×单价','meter':'按用量×单价','floor':'电梯阶梯','fixed':'固定金额','household':'按户分摊'}
        def group_display_rows(group_key):
            return fee_admin_display_rows(all_rows, group_key)

        summary_map = {
            'property': {'value': 0, 'label': '物业公司'},
            'commercial': {'value': 0, 'label': '商业公司'},
            'other': {'value': 0, 'label': '其他'},
        }
        for key in summary_map:
            summary_map[key]['value'] = len(group_display_rows(key))
        summary_html = ''.join(
            '<div class="col-md-4 col-6"><div class="summary-tile ' + ('primary' if key == selected_group else '') + '"><div class="label">' + item['label'] + '</div><strong>' + str(item['value']) + '</strong></div></div>'
            for key, item in summary_map.items()
        )

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
            html += '<form method=POST action="/fee_types/' + str(r['id']) + '/delete" style=display:inline onsubmit="return confirm(\'确定删除？\')"><input type="hidden" name="return_group" value="' + h(selected_group) + '"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></div></div>'
            html += '<hr><div class="row text-center"><div class="col-4 border-end"><small class="text-muted d-block">计算方式</small><span class="badge status-info">' + calc_n.get(r['calc_method'], r['calc_method']) + '</span></div>'
            html += '<div class="col-4 border-end"><small class="text-muted d-block">单价</small><strong class="fee-price">¥' + price(r['unit_price']) + '</strong></div>'
            html += '<div class="col-4"><small class="text-muted d-block">适用</small>' + cat_hint + '</div></div>'
            html += '<hr class="my-2"><div class="row text-center small"><div class="col-4"><span class="text-muted">本月</span><br><strong>' + str(bc) + '笔</strong></div><div class="col-4"><span class="text-muted">应收</span><br><strong class="money">¥' + m(bt) + '</strong></div><div class="col-4"><span class="text-muted">涉及</span><br><strong>' + str(rc) + '户</strong></div></div>'
            html += notes_html + '</div></div></div>'
            return html

        def _belongs_to_fee_group(row, group_key, defs):
            del defs
            return fee_admin_group(row) == group_key

        if selected_group in group_defs:
            gd = group_defs[selected_group]
            ordered = group_display_rows(selected_group)
            rh = ''.join(card_for(r) for r in ordered)
            header = '<div class="page-intro"><div><h2 class="mb-1"><i class="bi ' + gd['icon'] + '"></i> ' + gd['title'] + '</h2></div><div class="export-actions"><a href="/fee_types" class="btn btn-outline-secondary btn-sm"><i class="bi bi-arrow-left"></i> 返回总览</a><a href="/fee_types/create?group=' + h(selected_group) + '" class="btn btn-primary btn-sm"><i class="bi bi-plus-lg"></i> 添加</a></div></div>'
            content = header + '<div class="row">' + (rh or '<div class="col-12 text-center text-muted py-5">该分组暂无收费项目</div>') + '</div>'
            db.close()
            return self._html(self._page(gd['title'], content, 'fee_types'))

        group_tabs = ''
        for key, gd in group_defs.items():
            active = ' active' if selected_group == key else ''
            group_tabs += '<a class="contract-scope-tab ' + key + active + '" href="/fee_types?group=' + key + '"><i class="bi ' + gd['icon'] + '"></i><span>' + gd['title'] + '</span><strong>' + str(summary_map[key]['value']) + '项</strong></a>'

        group_cards = ''
        for key, gd in group_defs.items():
            present = group_display_rows(key)
            names_preview = '、'.join([h(r['name']) for r in present[:6]]) or '暂无项目'
            active = ' primary' if selected_group == key else ''
            group_cards += '<div class="col-md-4"><a href="/fee_types?group=' + key + '" class="text-decoration-none text-reset"><div class="summary-tile ' + active + ' h-100"><div class="label"><i class="bi ' + gd['icon'] + '"></i> ' + gd['title'] + '</div><strong>' + str(len(present)) + ' 项</strong><div class="text-muted small mt-2">' + gd['desc'] + '</div><div class="small text-muted mt-2">' + names_preview + '</div></div></a></div>'
        db.close()
        content = self._load_template('fee_types.html')
        content = content.replace('{SUMMARY}', summary_html)
        content = content.replace('{GROUP_TABS}', group_tabs)
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
            {"group":"金莎商业","name":"垃圾清运费","calc":"household","price":30,"unit":"元/户","cycle":"once","sort":14,"notes":"一次性固定收取","rad":15,"tiers":{}},
            {"group":"金莎商业","name":"装修管理费","calc":"area","price":3.0,"unit":"元/m2","cycle":"once","sort":15,"notes":"装修期间一次性按面积收","rad":7,"tiers":{"商户":3.0,"居民":2.0}},
            {"group":"金莎商业","name":"装修押金","calc":"fixed","price":2000,"unit":"元","cycle":"once","sort":16,"notes":"验收合格后退还","rad":7,"tiers":{}},
            {"group":"金莎商业","name":"泄水费","calc":"area","price":1.5,"unit":"元/m2","cycle":"once","sort":17,"notes":"一次性排水设施维护费","rad":30,"tiers":{"商户":1.5,"居民":0.8}},
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

        calc_labels = [
            ("area", "按面积×单价"),
            ("meter", "按用量×单价"),
            ("floor", "电梯费阶梯"),
            ("fixed", "固定金额"),
            ("household", "按户分摊"),
        ]
        cycle_labels = [
            ("once", "一次性/固定收费"),
            ("daily", "每日"),
            ("monthly", "每月"),
            ("quarterly", "每季度"),
            ("yearly", "每年"),
        ]
        calc_opts = "".join(
            f'<option value="{value}"{" selected" if cm == value else ""}>{label}</option>'
            for value, label in calc_labels
        )
        cycle_opts = "".join(
            f'<option value="{value}"{" selected" if bc == value else ""}>{label}</option>'
            for value, label in cycle_labels
        )
        tmpl_json = json.dumps(templates, ensure_ascii=False)

        self._html(self._page(t, f"""
{template_section}
<form method=POST action="{a}" class="row g-3">
<input type="hidden" name="return_group" value="{h(group)}">
<div class="col-md-8"><label>名称 <span class="text-danger">*</span></label><input name="name" autocomplete="new-password" autocorrect="off" autocapitalize="off" spellcheck="false" class="form-control" value="{n}" required id="ftName"></div>
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
<div class="col-12"><hr><button class="btn btn-primary btn-lg"><i class="bi bi-check-lg"></i> 保存</button> <button type="button" class="btn btn-outline-secondary btn-lg" onclick="history.length>1 ? history.back() : location.href='/fee_types'"><i class="bi bi-arrow-left"></i> 返回</button> <a href="/fee_types" class="btn btn-outline-secondary btn-lg">取消</a></div></form>""" + """
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
