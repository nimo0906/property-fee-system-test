from server.fees_shared import *

class FeeMixinPart2(BaseHandler):
    def _fee_type_create(self, d):
        db=get_db()
        return_group = qs(d, 'return_group')
        sort_order = _to_int(qs(d, 'sort_order'), 0)
        if sort_order == 0 and return_group in ('property', 'commercial', 'other'):
            sort_order = {'property': 29, 'commercial': 39, 'other': 59}[return_group]
        cur = db.execute("INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes,reminder_advance_days) VALUES(?,?,?,?,?,?,?,?,?)",
                         (qs(d,'name'),qs(d,'calc_method'),_to_float(qs(d,'unit_price'), 0),qs(d,'unit'),qs(d,'billing_cycle','monthly'),
                          sort_order,1 if qs(d,'is_active') else 0,qs(d,'notes'),_to_int(qs(d,'reminder_advance_days'), 30)))
        fid = cur.lastrowid
        new_cats = d.get('new_tier_cat', [])
        new_rates = d.get('new_tier_rate', [])
        if isinstance(new_cats, str): new_cats = [new_cats]
        if isinstance(new_rates, str): new_rates = [new_rates]
        for nc, nr in zip(new_cats, new_rates):
            if nc.strip() and nr.strip():
                db.execute("INSERT INTO fee_type_tiers(fee_type_id,category,rate) VALUES(?,?,?)", (fid, nc.strip(), float(nr.strip())))
        if return_group not in ('property', 'commercial', 'other'):
            return_group = _infer_fee_group({
                'name': qs(d, 'name'),
                'sort_order': sort_order,
            })
        db.commit();db.close()
        suffix = f'?group={return_group}&flash=添加成功' if return_group in ('property','commercial','other') else '?flash=添加成功'
        self._redirect('/fee_types' + suffix)

    def _fee_type_edit(self, fid, d):
        db=get_db()
        db.execute("UPDATE fee_types SET name=?,calc_method=?,unit_price=?,unit=?,billing_cycle=?,sort_order=?,is_active=?,notes=?,reminder_advance_days=? WHERE id=?",
                   (qs(d,'name'),qs(d,'calc_method'),_to_float(qs(d,'unit_price'), 0),qs(d,'unit'),qs(d,'billing_cycle','monthly'),
                    _to_int(qs(d,'sort_order'), 0),1 if qs(d,'is_active') else 0,qs(d,'notes'),_to_int(qs(d,'reminder_advance_days'), 30),fid))
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
        self._redirect(f'/fee_types/{fid}/edit?flash=更新成功')

    def _fee_type_delete(self, fid, data=None):
        data = data or {}
        return_group = qs(data, 'return_group')
        suffix = f'?group={return_group}' if return_group in ('property', 'commercial', 'other') else ''
        db=get_db()
        bc=db.execute("SELECT COUNT(*) FROM bills WHERE fee_type_id=?",(fid,)).fetchone()[0]
        mc=db.execute("SELECT COUNT(*) FROM meter_readings WHERE fee_type_id=?",(fid,)).fetchone()[0]
        fee=db.execute("SELECT name FROM fee_types WHERE id=?",(fid,)).fetchone()
        if not fee:
            db.close()
            return self._redirect('/fee_types' + suffix + ('&' if suffix else '?') + 'flash=收费项目不存在')
        if bc>0 or mc>0:
            details=[]
            if bc>0: details.append(f'{bc}条账单')
            if mc>0: details.append(f'{mc}条抄表记录')
            db.execute("UPDATE fee_types SET is_active=0 WHERE id=?",(fid,))
            db.commit(); db.close()
            return self._redirect('/fee_types' + suffix + ('&' if suffix else '?') + f'flash=已隐藏“{h(fee["name"])}”，历史{"、".join(details)}仍保留')
        db.execute("UPDATE fee_types SET is_active=0 WHERE id=?",(fid,))
        db.commit();db.close()
        self._redirect('/fee_types' + suffix + ('&' if suffix else '?') + 'flash=已删除')

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
<button type="button" class="btn btn-outline-secondary" onclick="if(history.length>1){{history.back()}}else{{location.href='/bills'}}">返回上一级</button></div></form>''','fee_types'))

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
