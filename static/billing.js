window.getElevatorRate = function(floor){
    var t = window.ELEVATOR_TIERS || [];
    for(var i = 0; i < t.length; i++)
        if(floor >= t[i].floor_from && floor <= t[i].floor_to) return t[i].rate;
    return 1.0;
};

window.cycleMonths = function(cycle){ return cycle === 'quarterly' ? 3 : (cycle === 'semiannual' ? 6 : 1); };

window.shouldUseRoomCycle = function(){ return false; };

window.parseBillingDate = function(value){
    var m = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if(!m) return new Date(NaN);
    return new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
};

window.calcMonths = function(){
    var s = document.getElementById("periodStart");
    var e = document.getElementById("periodEnd");
    if(!s || !e || !s.value || !e.value) return 1;
    var sd = window.parseBillingDate(s.value), ed = window.parseBillingDate(e.value);
    if(ed <= sd) return 1;
    var days = Math.floor((ed - sd) / (24 * 60 * 60 * 1000));
    return Math.max(1, Math.floor((days + 15) / 30));
};

window.daysInMonth = function(d){ return new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate(); };

window.prorateFactor = function(){
    var s = document.getElementById("periodStart"), e = document.getElementById("periodEnd");
    if(!s || !e || !s.value || !e.value) return 1;
    var sd = window.parseBillingDate(s.value), ed = window.parseBillingDate(e.value);
    if(isNaN(sd.getTime()) || isNaN(ed.getTime())) return 1;
    if(ed < sd){ var tmp = sd; sd = ed; ed = tmp; }
    var total = 0, cur = new Date(sd.getFullYear(), sd.getMonth(), 1);
    while(cur <= ed){
        var dim = window.daysInMonth(cur), ms = new Date(cur.getFullYear(), cur.getMonth(), 1), me = new Date(cur.getFullYear(), cur.getMonth(), dim);
        var a = sd > ms ? sd : ms, b = ed < me ? ed : me;
        if(a <= b) total += (a.getTime() === ms.getTime() && b.getTime() === me.getTime()) ? 1 : (Math.floor((b - a) / 86400000) + 1) / dim;
        cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
    }
    return total || 1;
};

window.factorLabel = function(v){
    return Math.abs(v - Math.round(v)) < 0.000001 ? Math.round(v) + "个月" : (Math.round(v * 10000) / 10000) + "个月";
};

window.updateMonthDisplay = function(){
    var s = document.getElementById("periodStart");
    var e = document.getElementById("periodEnd");
    var mc = document.getElementById("monthCount");
    if(!s || !e || !mc) return;
    if(!s.value || !e.value) { mc.textContent = "请选择日期"; return; }
    var sd = window.parseBillingDate(s.value), ed = window.parseBillingDate(e.value);
    if(ed <= sd) { mc.textContent = "截止须大于起始"; return; }
    var factor = window.prorateFactor();
    mc.textContent = "服务期折算：" + window.factorLabel(factor);
};

window.showOwnerRooms = function(){
    var s = document.getElementById("billingRoom"), sec = document.getElementById("ownerRoomsSection"), lst = document.getElementById("ownerRoomList");
    if(!s || !s.value || !sec || !lst){ if(sec) sec.style.display = "none"; return; }
    var tenantKey = s.options[s.selectedIndex].dataset.tenantKey;
    if(!tenantKey){ sec.style.display = "none"; return; }
    var rm = (window.OWNER_ROOMS || {})[tenantKey];
    if(!rm || rm.length <= 1){ sec.style.display = "none"; return; }
    var cur = parseInt(s.value), ot = rm.filter(function(r){ return r.id !== cur; });
    if(ot.length === 0){ sec.style.display = "none"; return; }
    sec.style.display = "block"; lst.innerHTML = "";
    ot.forEach(function(r){
        var d = document.createElement("div"); d.className = "form-check form-check-inline";
        var c = document.createElement("input"); c.type = "checkbox"; c.name = "extra_room_ids"; c.value = r.id; c.checked = true; c.className = "form-check-input";
        c.onchange = function(){ calcFees(); };
        var l = document.createElement("label"); l.className = "form-check-label"; l.textContent = r.name + " (" + r.cat + ")";
        d.appendChild(c); d.appendChild(l); lst.appendChild(d);
    });
};

window.feeMatchesCategory = function(feeName, roomCat, waterRate){
    waterRate = waterRate || "非居民";
    if(feeName.indexOf("(居民)") >= 0 && roomCat != "居民") return false;
    if(feeName.indexOf("(商户)") >= 0 && roomCat != "商户") return false;
    if(feeName.indexOf("(非居民)") >= 0) return waterRate == "非居民";
    if(feeName.indexOf("(特行)") >= 0) return waterRate == "特行";
    if(feeName.indexOf("(商业)") >= 0 && (roomCat != "商户" && roomCat != "商业")) return false;
    return true;
};

window.isFeeRowSelected = function(row){
    var cb = row ? row.querySelector(".fee-check") : null;
    return !cb || cb.checked;
};

window.billingMeterPeriods = function(){
    var s = document.getElementById("periodStart"), e = document.getElementById("periodEnd");
    if(!s || !e || !s.value || !e.value) return [];
    var sd = window.parseBillingDate(s.value), ed = window.parseBillingDate(e.value);
    if(isNaN(sd.getTime()) || isNaN(ed.getTime())) return [];
    var y = sd.getFullYear(), m = sd.getMonth() + 1;
    var ey = ed.getFullYear(), em = ed.getMonth() + 1, out = [];
    while(y < ey || (y === ey && m <= em)){
        out.push(String(y) + (m < 10 ? "0" + m : String(m)));
        m++;
        if(m > 12){ y++; m = 1; }
    }
    return out;
};

window.sumMeterConsumption = function(roomId, feeId){
    var data = window.METER_READINGS || {}, total = 0;
    window.billingMeterPeriods().forEach(function(period){
        total += parseFloat(data[String(roomId) + ":" + String(feeId) + ":" + period]) || 0;
    });
    return total;
};

window.meterMismatchWarning = function(roomId, feeId, feeName, waterRate){
    if((feeName || "").indexOf("水费(") < 0) return "";
    var details = window.METER_DETAILS || {}, total = 0, names = [];
    window.billingMeterPeriods().forEach(function(period){
        (details[String(roomId) + ":" + period] || []).forEach(function(item){
            if(parseInt(item.fee_id) === parseInt(feeId)) return;
            if((item.fee_name || "").indexOf("水费(") < 0) return;
            total += parseFloat(item.consumption) || 0;
            if(names.indexOf(item.fee_name) === -1) names.push(item.fee_name);
        });
    });
    if(total <= 0) return "";
    return "已录入" + names.join("、") + "用量 " + total + "，但当前房间水费标准为" + (waterRate || "非居民") + "，请先修正抄表费用类型或房间水费标准";
};

window.calcFees = function(){
    window.updateMonthDisplay();
    var months = window.calcMonths();
    var sel = document.getElementById("billingRoom");
    if(!sel || !sel.value){
        document.getElementById("totalAmt").textContent = "¥0.00";
        document.querySelectorAll("[id^=formula_]").forEach(function(e){ e.textContent = "-"; });
        document.querySelectorAll(".fee-amount").forEach(function(e){ e.value = ""; });
        return;
    }
    var o = sel.options[sel.selectedIndex], cat = o.dataset.cat || "", water = o.dataset.water || "非居民", area = parseFloat(o.dataset.area) || 0, floor = parseInt(o.dataset.floor) || 1, roomRate = parseFloat(o.dataset.rate) || 0, roomCycle = o.dataset.cycle || '', total = 0;
    var targetId = o.dataset.meterTarget || o.dataset.spaceId || o.dataset.roomId || sel.value;
    var factor = window.prorateFactor();
    document.querySelectorAll(".fee-row").forEach(function(row){
        var n = row.dataset.name || "";
        row.style.display = window.feeMatchesCategory(n, cat, water) ? "" : "none";
    });
    document.querySelectorAll(".fee-row").forEach(function(row){
        if(row.style.display === "none") return;
        if(!window.isFeeRowSelected(row)) return;
        var n = row.dataset.name || "";
        var fid = parseInt(row.dataset.ft), mid = row.dataset.method, dp = parseFloat(row.dataset.price) || 0, amt = 0, f = "", monthly = 0, feeCycle = row.dataset.cycle || "monthly";
        if(mid == "area"){ var rate = (n.indexOf('物业费') >= 0 && roomRate > 0) ? roomRate : dp; monthly = area * rate; f = '面积' + area.toFixed(2) + '×单价' + rate.toFixed(2); }
        else if(mid == "floor"){ var er = window.getElevatorRate(floor); monthly = er * area; f = "楼层系数" + er.toFixed(2) + "×" + area.toFixed(2); }
        else if(mid == "meter"){ var con = window.sumMeterConsumption(targetId, fid); monthly = con * dp; f = con > 0 ? "用量合计 " + con + " × " + dp.toFixed(2) : (window.meterMismatchWarning(targetId, fid, n, water) || "(无抄表) × " + dp.toFixed(2)); }
        else if(mid == "fixed"){ monthly = dp; f = "固定 " + dp.toFixed(2); }
        else if(mid == "household"){ monthly = dp; f = "按户 " + dp.toFixed(2); }
        var useFactor = (mid == "meter" || feeCycle == "once") ? 1 : factor;
        amt = monthly * useFactor;
        var ft = document.getElementById("feeAmt_" + fid);
        if(ft){
            if(!ft.dataset.edited) ft.value = amt.toFixed(2);
            else { amt = parseFloat(ft.value) || 0; f = "自定义"; }
        }
        var fm = document.getElementById("formula_" + fid);
        if(fm) fm.textContent = (ft && ft.dataset.edited || mid == "meter" || feeCycle == "once") ? f + " = ¥" + amt.toFixed(2) : f + " × " + window.factorLabel(useFactor) + " = ¥" + amt.toFixed(2);
        total += amt;
    });
    // Extra rooms
    var tenantKey = o ? o.dataset.tenantKey : null, extraTotal = 0;
    if(tenantKey){
        var allRm = (window.OWNER_ROOMS || {})[tenantKey] || [], tbody = document.querySelector("tbody");
        if(tbody){
            var oldSub = tbody.querySelector(".er-subtotal"); if(oldSub) oldSub.remove();
            document.querySelectorAll("[name=extra_room_ids]:checked").forEach(function(cb){
                var rd = allRm.find(function(r){ return r.id === parseInt(cb.value); }); if(!rd) return;
                var ea = parseFloat(rd.area) || 0, ef = parseInt(rd.floor) || 1, rr = parseFloat(rd.rate) || 0, rmMonths = factor;
                var hdrId = "er_hdr_" + rd.id;
                var hdr = document.getElementById(hdrId);
                if(!hdr){
                    hdr = document.createElement("tr"); hdr.id = hdrId; hdr.className = "er-header";
                    hdr.innerHTML = '<td colspan="5" class="text-primary small p-1 ps-3" style="border-top:1px dashed #bbb"><i class="bi bi-door-open"></i> ' + rd.name + '</td>';
                    tbody.appendChild(hdr);
                }
                document.querySelectorAll(".fee-row").forEach(function(row){
                    if(!window.isFeeRowSelected(row)) return;
                    var en = row.dataset.name || "";
                    if(!window.feeMatchesCategory(en, rd.cat, rd.water || "非居民")) return;
                    var fid = parseInt(row.dataset.ft), mid = row.dataset.method, dp = parseFloat(row.dataset.price) || 0, x = 0, formula = "";
                    if(mid == "area"){ var xr = (en.indexOf('物业费') >= 0 && rr > 0) ? rr : dp; x = ea * xr * rmMonths; formula = '面积' + ea.toFixed(2) + '×单价' + xr.toFixed(2) + '×' + rmMonths + '个月'; }
                    else if(mid == "floor"){ var er = window.getElevatorRate(ef); x = er * ea * rmMonths; formula = "楼层系数" + er.toFixed(2) + "×" + ea.toFixed(2) + "×" + rmMonths + "个月"; }
                    else if(mid == "meter"){ var con = window.sumMeterConsumption(rd.meterTarget || rd.id, fid); x = con * dp; formula = con > 0 ? "用量合计 " + con + " × " + dp.toFixed(2) : (window.meterMismatchWarning(rd.id, fid, en, rd.water || "非居民") || "(无抄表) × " + dp.toFixed(2)); }
                    else if(mid == "fixed"){ x = dp * rmMonths; formula = "固定 " + dp.toFixed(2) + " × " + rmMonths + "个月"; }
                    else if(mid == "household"){ x = dp * rmMonths; formula = "按户 " + dp.toFixed(2) + " × " + rmMonths + "个月"; }
                    if(x > 0){
                        total += x; extraTotal += x;
                        var rowId = "er_row_" + rd.id + "_" + fid, nr = document.getElementById(rowId);
                        if(nr){
                            var inp = nr.querySelector(".er-amt");
                            if(inp && !inp.dataset.edited) inp.value = x.toFixed(2);
                            var fm = nr.querySelector(".er-fm");
                            if(fm) fm.textContent = formula + " = ¥" + (inp && inp.dataset.edited ? parseFloat(inp.value).toFixed(2) : x.toFixed(2));
                        } else {
                            nr = document.createElement("tr"); nr.id = rowId; nr.className = "er-row";
                            nr.innerHTML = '<td><input type="checkbox" name="er_opt_' + rd.id + '_' + fid + '" checked class="er-opt" onchange="updateExtraTotal()"></td><td style="padding-left:20px">' + row.dataset.name + '</td><td></td><td class="text-muted small er-fm">' + formula + ' = ¥' + x.toFixed(2) + '</td><td class="text-end"><input type="number" class="form-control form-control-sm text-end er-amt fee-amount" value="' + x.toFixed(2) + '" step="0.01" style="width:120px;display:inline-block"></td>';
                            tbody.insertBefore(nr, hdr.nextSibling);
                        }
                    }
                });
            });
        }
    }
    // Clean up removed extra rooms
    var checkedIds = [];
    document.querySelectorAll("[name=extra_room_ids]:checked").forEach(function(cb){ checkedIds.push(parseInt(cb.value)); });
    document.querySelectorAll(".er-header,.er-row").forEach(function(el){
        if(el.id && el.id.indexOf("er_hdr_") === 0){
            var rid = parseInt(el.id.replace("er_hdr_", ""));
            if(checkedIds.indexOf(rid) === -1) el.remove();
        }
        if(el.id && el.id.indexOf("er_row_") === 0){
            var parts = el.id.split("_"), rid = parseInt(parts[2]);
            if(checkedIds.indexOf(rid) === -1) el.remove();
        }
    });
    if(extraTotal > 0){
        var sub = document.createElement("tr"); sub.className = "er-subtotal";
        sub.innerHTML = '<td colspan="5" class="text-end text-primary small p-1" style="border-top:1px solid #999"><strong>额外房间小计: +¥' + extraTotal.toFixed(2) + '</strong></td>';
        tbody.appendChild(sub);
    }
    document.getElementById("totalAmt").textContent = "¥" + total.toFixed(2);
};

window.updateExtraTotal = function(){
    var total = 0;
    document.querySelectorAll(".fee-row").forEach(function(r){
        if(r.style.display !== "none" && window.isFeeRowSelected(r)){
            var inp = document.getElementById("feeAmt_" + r.dataset.ft);
            if(inp) total += parseFloat(inp.value) || 0;
        }
    });
    document.querySelectorAll("[name=extra_room_ids]:checked").forEach(function(cb){
        var rid = parseInt(cb.value);
        document.querySelectorAll(".er-row").forEach(function(row){
            if(row.id && row.id.indexOf("er_row_" + rid + "_") === 0){
                var opt = row.querySelector(".er-opt");
                if(opt && !opt.checked) return;
                var inp = row.querySelector(".er-amt");
                if(inp) total += parseFloat(inp.value) || 0;
            }
        });
    });
    document.getElementById("totalAmt").textContent = "¥" + total.toFixed(2);
};

document.addEventListener("input", function(e){
    if(e.target.classList.contains("fee-amount")){ e.target.dataset.edited = "1"; calcFees(); }
    if(e.target.classList.contains("er-amt")){ e.target.dataset.edited = "1"; updateExtraTotal(); }
});
document.addEventListener("change", function(e){
    if(e.target.id === "checkAll"){
        document.querySelectorAll(".fee-check").forEach(function(c){ c.checked = e.target.checked; });
        calcFees();
    }
    if(e.target.classList.contains("fee-check")) calcFees();
    if(e.target.classList.contains("er-opt")) updateExtraTotal();
});
document.addEventListener("submit", function(e){
    if(e.target.id !== "billingForm") return;
    document.querySelectorAll(".fee-row").forEach(function(row){
        var selected = row.style.display !== "none" && window.isFeeRowSelected(row);
        row.querySelectorAll(".fee-check").forEach(function(inp){ inp.disabled = !selected; });
        row.querySelectorAll(".fee-amount").forEach(function(inp){ inp.disabled = !selected; });
    });
});
window.addEventListener("DOMContentLoaded", function(){
    var s = document.getElementById("billingRoom");
    if(s && s.options.length > 1){
        for(var i = 1; i < s.options.length; i++)
            if(s.options[i].value){ s.selectedIndex = i; break; }
        calcFees();
    }
});

window.toggleRoom = function(rid){
    var rows = document.querySelectorAll(".room-detail-" + rid), icon = document.getElementById("icon_" + rid);
    rows.forEach(function(r){ r.style.display = r.style.display === "none" ? "" : "none"; });
    if(icon) icon.className = icon.className === "bi bi-chevron-right" ? "bi bi-chevron-down" : "bi bi-chevron-right";
};
