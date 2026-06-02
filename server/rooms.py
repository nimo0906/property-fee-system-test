#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Room management."""

from server.db import get_db, get_fee_type_rate, h, m, qs
from server.base import BaseHandler


class RoomMixin(BaseHandler):

    def _rooms(self, q):

        db=get_db();bld=qs(q,'building');kw=qs(q,'keyword');cat=qs(q,'category')
        sql="SELECT r.*,o.name oname,o.phone ophone FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id"
        cond=[];vals=[]
        if bld:cond.append("r.building=?");vals.append(bld)
        if cat:cond.append("r.category=?");vals.append(cat)
        if kw:cond.append("(r.room_number LIKE ? OR r.building LIKE ? OR r.unit LIKE ? OR r.category LIKE ? OR r.business_type LIKE ? OR r.tenant_name LIKE ? OR r.tenant_phone LIKE ? OR o.name LIKE ? OR o.phone LIKE ? OR CAST(r.area AS TEXT) LIKE ?)");vals.extend([f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%',f'%{kw}%'])
        if cond:sql+=" WHERE "+" AND ".join(cond)
        sql+=" ORDER BY r.building,r.unit,r.room_number"
        rows=db.execute(sql,vals).fetchall()
        blds=db.execute("SELECT DISTINCT building FROM rooms ORDER BY building").fetchall()
        cats=db.execute("SELECT DISTINCT category FROM rooms WHERE category IS NOT NULL AND category<>'' ORDER BY category").fetchall()
        db.close()
        rh = ''.join(
            f'<tr><td><input class="form-check-input room-select" form="roomBatchDeleteForm" type="checkbox" name="room_ids" value="{r["id"]}"></td>'
            f'<td>{h(r["building"])}</td><td>{h(r["unit"])}</td><td><strong>{h(r["room_number"])}</strong></td>'
            f'<td>{h(r["shop_name"] or "-")}</td><td>{h(r["tenant_name"] or "-")}</td><td>{r["floor"] or "-"}F</td>'
            f'<td><span class="badge status-{"info" if r["category"]=="商户" else "neutral"}">{h(r["category"] or "居民")}</span></td>'
            f'<td>{h(r["business_type"] or "-")}</td><td class="text-end">{m(r["area"])}</td><td>{h(r["oname"]or"未分配")}</td>'
            f'<td>{(h(r["contract_start"]) or "")[:7]}{"~" if r["contract_start"] and r["contract_end"] else ""}{(h(r["contract_end"]) or "-")[:7]}</td>'
            f'<td><a href="/rooms/{r["id"]}/edit" class="btn btn-sm btn-outline-primary"><i class="bi bi-pencil"></i></a>'
            f'<form method=POST action="/rooms/{r["id"]}/delete" style=display:inline onsubmit="return confirm(\'确定删除房间？该房间的账单和抄表记录将一并删除！\')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'
            for r in rows
        )
        bo='<option value="">全部楼栋</option>'+''.join(f'<option value="{h(b["building"])}"{" selected" if bld==b["building"] else""}>{h(b["building"])}</option>' for b in blds)
        default_cats = ["居民", "商户", "商业"]
        cat_values = []
        for x in default_cats + [c["category"] for c in cats]:
            if x and x not in cat_values:
                cat_values.append(x)
        cat_opts = '<option value="">全部房间类型</option>' + ''.join(f'<option value="{h(x)}"{" selected" if cat==x else""}>{h(x)}</option>' for x in cat_values)
        tpl=self._load_template('rooms.html')
        tpl=tpl.replace('{BOPTS}',bo).replace('{KW}',h(kw)).replace('{CAT_OPTS}', cat_opts)
        empty = """<tr><td colspan="13" class="text-center text-muted py-5">
        <div><i class="bi bi-door-open" style="font-size:2rem;color:#adb5bd"></i></div>
        <h6 class="mt-2">还没有房间资料</h6>
        <p class="mb-3">推荐先按模板导入楼栋、房号、楼层、面积、业主和合同日期；少量资料也可以手动添加。</p>
        <a class="btn btn-outline-primary btn-sm" href="/import/template/basic.csv" download="basic_info_template.csv">下载基础资料模板</a>
        <a class="btn btn-primary btn-sm" href="/import">导入基础资料</a>
        <a class="btn btn-outline-secondary btn-sm" href="/rooms/create">手动添加房间</a>
        </td></tr>"""
        tpl=tpl.replace('{ROWS}',rh or empty)
        self._html(self._page('房间管理',tpl,'rooms'))

    def _room_form(self, rid):
        db=get_db();room=None
        if rid:room=db.execute("SELECT r.*,o.name oname,o.phone ophone FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id WHERE r.id=?",(rid,)).fetchone()
        owners=db.execute("SELECT * FROM owners ORDER BY name").fetchall()
        db.close()
        if owners:
            oo='<option value="">--选择--</option>'+''.join(f'<option value="{o["id"]}"{" selected" if room and room["owner_id"]==o["id"] else""}>{h(o["name"])}</option>' for o in owners)
        else:
            oo='<option value="">--暂无业主，请先添加--</option>'
        a=f'/rooms/{rid}/edit' if rid else '/rooms/create'
        t='编辑房间' if rid else '添加房间'
        b=h(room['building'] if room else '金莎国际');u=h(room['unit'] if room else '商场')
        n=h(room['room_number'] if room else '');fl=room['floor'] if room else 7
        cat=room['category'] if room else '商户';ar=room['area'] if room else 100
        cr=h(str(room['custom_rate']) if room and room['custom_rate'] else '')
        cs=h(room['contract_start'] or'') if room else ''
        ce=h(room['contract_end'] or'') if room else ''
        bt=h(room['business_type'] or'') if room and 'business_type' in room.keys() else ''
        sn=h(room['shop_name'] or'') if room and 'shop_name' in room.keys() else ''
        tn=h(room['tenant_name'] or'') if room and 'tenant_name' in room.keys() else ''
        tph=h(room['tenant_phone'] or'') if room and 'tenant_phone' in room.keys() else ''
        tic=h(room['tenant_id_card'] or'') if room and 'tenant_id_card' in room.keys() else ''
        tif=h(room['tenant_id_card_front'] or'') if room and 'tenant_id_card_front' in room.keys() else ''
        tib=h(room['tenant_id_card_back'] or'') if room and 'tenant_id_card_back' in room.keys() else ''
        pc=(room['payment_cycle'] if room and 'payment_cycle' in room.keys() and room['payment_cycle'] else 'monthly')
        wt=(room['water_rate_type'] if room and 'water_rate_type' in room.keys() and room['water_rate_type'] else '非居民')
        nt=h(room['notes'] or'') if room else ''
        self._html(self._page(t,f'''<form method=POST action="{a}" class="row g-3">
    <div class="col-md-3"><label>楼栋 *</label><input name="building" class="form-control" value="{b}" required></div>
    <div class="col-md-3"><label>单元/区域</label><select name="unit" class="form-select"><option value="A座" {"selected" if u=="A座" else ""}>A座</option><option value="B座" {"selected" if u=="B座" else ""}>B座</option><option value="商场" {"selected" if u=="商场" else ""}>商场</option></select><small class="text-muted">用于商业收费下拉分组，如 A座、B座、商场。</small></div>
    <div class="col-md-3"><label>铺位号/房号 *</label><input name="room_number" class="form-control" value="{n}" required id="rmNum" oninput="autoFloor()"><small class="text-muted">商场建议填铺位号，如 1F-101。</small></div>
    <div class="col-md-3"><label>楼层</label><input name="floor" type="number" class="form-control" value="{fl}" min="1" max="99" id="rmFloor"></div>
    <div class="col-md-3"><label>房间类型</label><select name="category" class="form-select" id="rmCat" onchange="autoRate()"><option value="居民" {"selected" if cat=="居民" else ""}>居民</option><option value="商户" {"selected" if cat=="商户" else ""}>商户</option><option value="商业" {"selected" if cat=="商业" else ""}>商业</option></select><small class="text-muted">决定收费适用范围；商业收费只取商户/商业。非居民/特行只是水费档位，不是房间类型。</small></div>
    <div class="col-md-3"><label>面积(m²) *</label><input name="area" type="number" class="form-control" value="{ar}" step="0.01" required></div>
    <div class="col-md-3"><label>物业费单价(元/m²·月)</label><input name="custom_rate" type="number" class="form-control" value="{cr}" step="0.01" placeholder="如4.8"><small class="text-muted">商场商户按户维护独立单价。</small></div>
    <div class="col-md-3"><label>水费标准</label><select name="water_rate_type" class="form-select"><option value="非居民" {"selected" if wt=="非居民" else ""}>非居民 5.8元/m³</option><option value="特行" {"selected" if wt=="特行" else ""}>特行 20.11元/m³</option></select><small class="text-muted">仅用于水费(非居民)/水费(特行)选择。</small></div>
    <div class="col-md-3"><label>业主姓名</label><input name="owner_name" class="form-control" value="{h(room["oname"] if room and room["oname"] else "")}" placeholder="直接输入业主姓名" list="ownerNameList"><datalist id="ownerNameList">{''.join(f'<option value="{h(o["name"])}"></option>' for o in owners)}</datalist></div>
    <div class="col-md-3"><label>业主电话</label><input name="owner_phone" class="form-control" value="{h(room["ophone"] if room and room["ophone"] else "")}"></div>
    <div class="col-md-3"><label>身份证号</label><input name="id_card" class="form-control" value="{h(room["id_card"] if room and room["id_card"] else "")}"></div>
    <div class="col-md-3"><label>身份证正面</label><input type="file" class="form-control form-control-sm" accept="image/*" id="idFront" onchange="previewImg(this,'previewFront')"><br><img id="previewFront" src="{h(room["id_card_front"] if room else "" or "")}" style="max-height:60px;max-width:120px;display:{"none" if not (room and room["id_card_front"] if room else "") else "inline"}" class="border rounded"><input name="id_card_front" type="hidden" id="idCardFrontVal" value="{h(room["id_card_front"] if room else "" or "")}"></div>
    <div class="col-md-3"><label>身份证反面</label><input type="file" class="form-control form-control-sm" accept="image/*" id="idBack" onchange="previewImg(this,'previewBack')"><br><img id="previewBack" src="{h(room["id_card_back"] if room else "" or "")}" style="max-height:60px;max-width:120px;display:{"none" if not (room and room["id_card_back"] if room else "") else "inline"}" class="border rounded"><input name="id_card_back" type="hidden" id="idCardBackVal" value="{h(room["id_card_back"] if room else "" or "")}"></div>
    <div class="col-md-3"><label>租户姓名</label><input name="tenant_name" class="form-control" value="{tn}" placeholder="当前承租人姓名"></div>
    <div class="col-md-3"><label>租户电话</label><input name="tenant_phone" class="form-control" value="{tph}" placeholder="承租人联系电话"></div>
    <div class="col-md-3"><label>租户身份证号</label><input name="tenant_id_card" class="form-control" value="{tic}" placeholder="承租人身份证号"></div>
    <div class="col-md-3"><label>租户身份证正面</label><input type="file" class="form-control form-control-sm" accept="image/*" id="tenantIdFront" onchange="previewImg(this,'previewTenantFront')"><br><img id="previewTenantFront" src="{tif}" style="max-height:60px;max-width:120px;display:{"none" if not tif else "inline"}" class="border rounded"><input name="tenant_id_card_front" type="hidden" id="idCardTenantFrontVal" value="{tif}"></div>
    <div class="col-md-3"><label>租户身份证反面</label><input type="file" class="form-control form-control-sm" accept="image/*" id="tenantIdBack" onchange="previewImg(this,'previewTenantBack')"><br><img id="previewTenantBack" src="{tib}" style="max-height:60px;max-width:120px;display:{"none" if not tib else "inline"}" class="border rounded"><input name="tenant_id_card_back" type="hidden" id="idCardTenantBackVal" value="{tib}"></div>
    <div class="col-md-3"><label>合同起始</label><input name="contract_start" type="date" class="form-control" value="{cs}"></div>
    <div class="col-md-3"><label>合同到期</label><input name="contract_end" type="date" class="form-control" value="{ce}"></div>
    <div class="col-md-3"><label>缴费周期</label><select name="payment_cycle" class="form-select"><option value="monthly" {"selected" if pc=="monthly" else ""}>月付</option><option value="quarterly" {"selected" if pc=="quarterly" else ""}>季付</option><option value="semiannual" {"selected" if pc=="semiannual" else ""}>半年付</option></select></div>
    <div class="col-md-3"><label>店铺名称</label><input name="shop_name" class="form-control" value="{sn}" placeholder="如：某某便利店"></div>
    <div class="col-md-3"><label>业态/商户类别</label><input name="business_type" class="form-control" value="{bt}" placeholder="如：餐饮、零售、美容、办公"><small class="text-muted">用于商户类别统计，如：餐饮、零售、美容、办公。</small></div>
    <div class="col-md-3"><label>备注</label><input name="notes" class="form-control" value="{nt}" placeholder="其他补充说明"></div>
    <input type="hidden" name="owner_id" value="{h(str(room["owner_id"]) if room and room["owner_id"] else "")}">
    <div class="col-12"><hr><button class="btn btn-primary"><i class="bi bi-check-lg"></i> 保存</button> <a href="/rooms" class="btn btn-outline-secondary">取消</a></div></form>
    <script src="/static/room_form.js"></script>''', 'rooms'))

    def _room_create(self, d):
        db=get_db()
        cr = qs(d,'custom_rate')
        cat=qs(d,'category','居民')
        if not cr:
            cr = str(get_fee_type_rate(1, cat))
        oname=qs(d,'owner_name').strip()
        ophone=qs(d,'owner_phone').strip()
        oid=qs(d,'owner_id')
        if oname:
            icard=qs(d,'id_card')
            exist=db.execute("SELECT id FROM owners WHERE name=? LIMIT 1",(oname,)).fetchone()
            if exist:
                oid=str(exist[0])
                if icard: db.execute("UPDATE owners SET phone=?,id_card=? WHERE id=?",(ophone,icard,oid))
            else:
                db.execute("INSERT INTO owners(name,phone,id_card) VALUES(?,?,?)",(oname,ophone,icard))
                oid=str(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        db.execute("INSERT INTO rooms(building,unit,room_number,floor,category,area,custom_rate,contract_start,contract_end,owner_id,business_type,shop_name,tenant_name,tenant_phone,tenant_id_card,tenant_id_card_front,tenant_id_card_back,payment_cycle,water_rate_type,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (qs(d,'building'),qs(d,'unit','A座'),qs(d,'room_number'),
                    int(qs(d,'floor') or 0),qs(d,'category','居民'),float(qs(d,'area',0)),
                    float(cr) if cr else None,qs(d,'contract_start'),qs(d,'contract_end'),
                    int(oid) if oid else None,qs(d,'business_type'),qs(d,'shop_name'),qs(d,'tenant_name'),qs(d,'tenant_phone'),qs(d,'tenant_id_card'),qs(d,'tenant_id_card_front'),qs(d,'tenant_id_card_back'),qs(d,'payment_cycle','monthly'),qs(d,'water_rate_type','非居民'),qs(d,'notes')))
        db.commit();db.close()
        self._redirect('/rooms?flash=添加成功')

    def _room_edit(self, rid, d):
        db=get_db()
        cr = qs(d,'custom_rate')
        cat=qs(d,'category','居民')
        if not cr:
            cr = str(get_fee_type_rate(1, cat))
        oname=qs(d,'owner_name').strip()
        ophone=qs(d,'owner_phone').strip()
        oid=qs(d,'owner_id')
        if oname:
            icard=qs(d,'id_card')
            exist=db.execute("SELECT id FROM owners WHERE name=? LIMIT 1",(oname,)).fetchone()
            if exist:
                oid=str(exist[0])
                if icard: db.execute("UPDATE owners SET phone=?,id_card=? WHERE id=?",(ophone,icard,oid))
            else:
                db.execute("INSERT INTO owners(name,phone,id_card) VALUES(?,?,?)",(oname,ophone,icard))
                oid=str(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        db.execute("UPDATE rooms SET building=?,unit=?,room_number=?,floor=?,category=?,area=?,custom_rate=?,contract_start=?,contract_end=?,owner_id=?,business_type=?,shop_name=?,tenant_name=?,tenant_phone=?,tenant_id_card=?,tenant_id_card_front=?,tenant_id_card_back=?,payment_cycle=?,water_rate_type=?,notes=? WHERE id=?",
                   (qs(d,'building'),qs(d,'unit'),qs(d,'room_number'),
                    int(qs(d,'floor') or 0),qs(d,'category','居民'),float(qs(d,'area',0)),
                    float(cr) if cr else None,qs(d,'contract_start'),qs(d,'contract_end'),
                    int(oid) if oid else None,qs(d,'business_type'),qs(d,'shop_name'),qs(d,'tenant_name'),qs(d,'tenant_phone'),qs(d,'tenant_id_card'),qs(d,'tenant_id_card_front'),qs(d,'tenant_id_card_back'),qs(d,'payment_cycle','monthly'),qs(d,'water_rate_type','非居民'),qs(d,'notes'),rid))
        db.commit();db.close()
        self._redirect('/rooms?flash=更新成功')

    def _room_batch_delete(self, d):
        raw = d.get('room_ids', [])
        if isinstance(raw, str):
            raw = [raw]
        ids = [x for x in raw if str(x).isdigit()]
        if not ids:
            return self._redirect('/rooms?flash=请先勾选要删除的房间')
        placeholders = ','.join('?' * len(ids))
        db = get_db()
        bill_count = db.execute(f"SELECT COUNT(*) FROM bills WHERE room_id IN ({placeholders})", ids).fetchone()[0]
        meter_count = db.execute(f"SELECT COUNT(*) FROM meter_readings WHERE room_id IN ({placeholders})", ids).fetchone()[0]
        db.execute(f"DELETE FROM meter_readings WHERE room_id IN ({placeholders})", ids)
        db.execute(f"DELETE FROM bills WHERE room_id IN ({placeholders})", ids)
        db.execute(f"DELETE FROM rooms WHERE id IN ({placeholders})", ids)
        db.commit(); db.close()
        parts = [f'房间{len(ids)}间']
        if bill_count:
            parts.append(f'账单{bill_count}笔')
        if meter_count:
            parts.append(f'抄表{meter_count}条')
        self._redirect('/rooms?flash=已批量删除' + '，'.join(parts))

    def _room_delete(self, rid):
        db=get_db()
        bc=db.execute("SELECT COUNT(*) FROM bills WHERE room_id=?",(rid,)).fetchone()[0]
        mc=db.execute("SELECT COUNT(*) FROM meter_readings WHERE room_id=?",(rid,)).fetchone()[0]
        db.execute("DELETE FROM meter_readings WHERE room_id=?",(rid,))
        db.execute("DELETE FROM bills WHERE room_id=?",(rid,))
        db.execute("DELETE FROM rooms WHERE id=?",(rid,))
        db.commit();db.close()
        parts=[]
        if bc>0: parts.append(f'账单{bc}笔')
        if mc>0: parts.append(f'抄表{mc}条')
        detail='，连带删除' + '、'.join(parts) if parts else ''
        self._redirect(f'/rooms?flash=已删除{detail}')
