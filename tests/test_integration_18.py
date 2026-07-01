#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 18."""

from tests.integration_base import *


class TestIntegration18(IntegrationTestBase):
    def test_billing_amount_recalculation_uses_fee_name_in_calculation_loop(self):
        with open(os.path.join(PROJECT_ROOT, 'static', 'billing.js'), encoding='utf-8') as f:
            js = f.read()
        calculation_loop = js.split('document.querySelectorAll(".fee-row").forEach(function(row){', 2)[2]
        calculation_loop = calculation_loop.split('// Extra rooms', 1)[0]
        self.assertIn('var n = row.dataset.name || "";', calculation_loop)
        self.assertIn("n.indexOf('物业费')", calculation_loop)


    def test_property_billing_date_range_overrides_room_payment_cycle(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '物业日期区间业主', '13900000009')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='1427', category='居民', area=59.42, owner_id=owner_id)
        db.execute("UPDATE rooms SET payment_cycle='monthly', custom_rate=NULL WHERE id=?", (room_id,))
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()[0]
        db.commit(); db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'fee_types': [str(fee_id)],
            'period_start': '2026-06-02',
            'period_end': '2026-10-02',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = get_db()
        bill = db.execute("SELECT amount,billing_period,due_date FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2026-06~2026-10')
        self.assertEqual(bill['due_date'], '2026-10-02')
        self.assertAlmostEqual(float(bill['amount']), 455.2)


    def test_billing_frontend_uses_room_cycle_only_in_commercial_mode(self):
        status, property_body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('window.BILLING_MODE="property"', property_body)
        self.assertIn('起始日和截止日均计入服务期', property_body)
        self.assertNotIn('收7-9月', property_body)

        status, commercial_body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('window.BILLING_MODE="commercial"', commercial_body)
        self.assertIn('商业收费项目', commercial_body)
        self.assertNotIn('商场商业收费已迁移', commercial_body)

        with open(os.path.join(PROJECT_ROOT, 'static', 'billing.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn('window.shouldUseRoomCycle', js)
        self.assertIn('return false', js)
        self.assertNotIn('if(roomCycle) months = window.cycleMonths(roomCycle);', js)
        self.assertNotIn('new Date(s.value)', js)
        self.assertNotIn('new Date(e.value)', js)
        self.assertIn('window.parseBillingDate', js)


    def test_billing_frontend_proration_parses_date_inputs_as_local_dates(self):
        import subprocess
        script = r'''
const fs = require("fs");
const vm = require("vm");
const js = fs.readFileSync("static/billing.js", "utf8");
const elements = {
  periodStart: { value: "2026-07-01" },
  periodEnd: { value: "2026-09-30" }
};
const context = {
  window: {},
  addEventListener: function() {},
  document: {
    getElementById: function(id) { return elements[id] || null; },
    querySelectorAll: function() { return []; },
    addEventListener: function() {}
  }
};
context.window = context;
vm.createContext(context);
vm.runInContext(js, context);
console.log(context.factorLabel(context.prorateFactor()));
'''
        result = subprocess.run(
            ['node', '-e', script],
            cwd=PROJECT_ROOT,
            env={**os.environ, 'TZ': 'Asia/Shanghai'},
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), '3个月')

    def test_billing_frontend_clears_extra_room_rows_when_switching_to_single_room(self):
        import subprocess
        script = r'''
const fs = require("fs");
const vm = require("vm");
const js = fs.readFileSync("static/billing.js", "utf8");

function Node(tag){
  this.tagName = tag;
  this.children = [];
  this.parent = null;
  this.style = {};
  this.dataset = {};
  this.id = "";
  this.className = "";
  this.value = "";
  this.checked = false;
  this.name = "";
  this.textContent = "";
}
Node.prototype.appendChild = function(child){ child.parent = this; this.children.push(child); return child; };
Node.prototype.insertBefore = function(child, ref){
  child.parent = this;
  const idx = this.children.indexOf(ref);
  if(idx < 0) this.children.push(child); else this.children.splice(idx, 0, child);
  return child;
};
Node.prototype.remove = function(){
  if(this.parent){
    const idx = this.parent.children.indexOf(this);
    if(idx >= 0) this.parent.children.splice(idx, 1);
  }
};
Node.prototype._walk = function(cb){
  this.children.slice().forEach(function(c){ cb(c); c._walk(cb); });
};
Node.prototype._matches = function(sel){
  if(sel === this.tagName) return true;
  if(sel === ".fee-row") return this.className.indexOf("fee-row") >= 0;
  if(sel === ".er-header,.er-row") return this.className.indexOf("er-header") >= 0 || this.className.indexOf("er-row") >= 0;
  if(sel === ".er-subtotal") return this.className.indexOf("er-subtotal") >= 0;
  if(sel === ".fee-check") return this.className.indexOf("fee-check") >= 0;
  if(sel === "[name=extra_room_ids]:checked") return this.name === "extra_room_ids" && this.checked;
  return false;
};
Node.prototype.querySelectorAll = function(sel){
  const out = [];
  this._walk(function(n){ if(n._matches(sel)) out.push(n); });
  return out;
};
Node.prototype.querySelector = function(sel){ return this.querySelectorAll(sel)[0] || null; };
Object.defineProperty(Node.prototype, "innerHTML", {
  set: function(html){
    this._innerHTML = html;
    if(html.indexOf("extra_room_ids") >= 0){
      const c = new Node("input"); c.name = "extra_room_ids"; c.checked = true; this.appendChild(c);
    }
  },
  get: function(){ return this._innerHTML || ""; }
});

const root = new Node("body");
const tbody = new Node("tbody"); root.appendChild(tbody);
const total = new Node("span"); total.id = "totalAmt"; root.appendChild(total);
const room = new Node("select"); room.id = "billingRoom"; room.selectedIndex = 0; root.appendChild(room);
room.options = [
  { value: "1", dataset: { tenantKey: "tenant:many", cat: "商户", water: "非居民", area: "10", floor: "1" } },
  { value: "3", dataset: { tenantKey: "", cat: "商户", water: "非居民", area: "10", floor: "1" } }
];
Object.defineProperty(room, "value", { get: function(){ return this.options[this.selectedIndex].value; } });
const feeRow = new Node("tr"); feeRow.className = "fee-row"; feeRow.dataset = { ft: "99", method: "fixed", price: "100", name: "测试固定费", cycle: "monthly" };
const feeCheck = new Node("input"); feeCheck.className = "fee-check"; feeCheck.checked = true; feeRow.appendChild(feeCheck); tbody.appendChild(feeRow);
const staleExtra = new Node("input"); staleExtra.name = "extra_room_ids"; staleExtra.value = "2"; staleExtra.checked = true; root.appendChild(staleExtra);

const elements = { billingRoom: room, totalAmt: total };
const context = {
  window: {},
  addEventListener: function() {},
  document: {
    getElementById: function(id) { return elements[id] || null; },
    querySelectorAll: function(sel) { return root.querySelectorAll(sel); },
    querySelector: function(sel) { return root.querySelector(sel); },
    createElement: function(tag){ return new Node(tag); },
    addEventListener: function() {}
  }
};
context.window = context;
context.OWNER_ROOMS = {
  "tenant:many": [
    { id: 1, name: "当前房", cat: "商户", area: 10, floor: 1 },
    { id: 2, name: "额外房", cat: "商户", area: 10, floor: 1 }
  ]
};
context.ELEVATOR_TIERS = [];
context.METER_READINGS = {};
context.METER_DETAILS = {};
vm.createContext(context);
vm.runInContext(js, context);

context.calcFees();
const afterMany = tbody.querySelectorAll(".er-header,.er-row").length;
room.selectedIndex = 1;
context.calcFees();
const afterSingle = tbody.querySelectorAll(".er-header,.er-row").length;
console.log(afterMany + "," + afterSingle);
'''
        result = subprocess.run(
            ['node', '-e', script],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), '2,0')


    def test_bills_start_month_filter_includes_multi_month_billing_period(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '多月账单业主', '13900000010')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='1427', category='居民', area=59.42, owner_id=owner_id)
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()[0]
        bill_id = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=fee_id, period='2026-06~2026-10', amount=451.60, status='paid')
        create_payment(db, bill_id=bill_id, amount=451.60)
        db.close()

        status, body = http_get('/bills?period=2026-06-01&keyword=1427', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-06~2026-10', body)
        self.assertIn('金莎国际-B座-1427', body)
        self.assertNotIn('暂无账单', body)


    def test_bills_range_filter_keeps_existing_single_month_bills_visible(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '范围过滤业主', '13900006666')
        room_id = create_room(db, building='RANGEKEEP', unit='B座', room_number='1408', category='商户', owner_id=owner_id)
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2035-06', amount=100, status='unpaid')
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2035-06~2035-09', amount=400, status='unpaid')
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2035-05', amount=50, status='unpaid')
        db.close()

        status, body = http_get('/bills?period=2035-06~2035-09&keyword=1408', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2035-06', body)
        self.assertIn('2035-06~2035-09', body)
        self.assertIn('¥100.0', body)
        self.assertIn('¥400.0', body)
        self.assertNotIn('2035-05', body)
        self.assertNotIn('¥50.0', body)
        self.assertNotIn('暂无账单', body)


    def test_billing_page_labels_extra_rooms_by_tenant_not_owner(self):
        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('同租户其他房间', body)
        self.assertNotIn('同业主其他房间', body)
        self.assertIn('ownerRoomsToggle', body)
        self.assertIn('ownerRoomsSelectAll', body)
        self.assertIn('ownerRoomsClear', body)
        self.assertIn('tenant-room-list', body)
        self.assertIn('/static/billing_ui_extras.js', body)

        status, commercial_body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('同租户其他房间', commercial_body)
        self.assertIn('商业收费项目', commercial_body)
        self.assertNotIn('商场商业收费已迁移', commercial_body)


    def test_commercial_billing_fee_count_matches_commercial_fee_standard_group(self):
        import re
        status, fee_group = http_get('/fee_types?group=commercial', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        commercial_fee_count = fee_group.count('class="card fee-card h-100"')

        status, billing_page = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        stat = re.search(r'<div class="billing-mode-chip stat"><span>收费项目</span><strong>(\d+)</strong><em>已启用</em></div>', billing_page)
        self.assertIsNotNone(stat)
        self.assertEqual(int(stat.group(1)), commercial_fee_count)


    def test_billing_extra_rooms_are_grouped_by_tenant_not_owner(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '同一业主不同租户', '13900005555')
        room_a = create_room(db, building='TENANT', unit='商场', room_number='1402', category='商户', owner_id=owner_id)
        room_b = create_room(db, building='TENANT', unit='商场', room_number='1403', category='商户', owner_id=owner_id)
        room_c = create_room(db, building='TENANT', unit='商场', room_number='1404', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='奈思美发店', shop_name='奈思美发店' WHERE id IN (?,?)", (room_a, room_b))
        db.execute("UPDATE rooms SET tenant_name='其他租户', shop_name='其他租户' WHERE id=?", (room_c,))
        db.commit(); db.close()

        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        match = re.search(r'window\.OWNER_ROOMS=(.*?);window\.BILLING_MODE', body)
        self.assertIsNotNone(match)
        tenant_rooms = json.loads(match.group(1))
        groups = [[r['id'] for r in rooms] for rooms in tenant_rooms.values()]
        self.assertIn([room_a, room_b], [sorted(g) for g in groups])
        self.assertNotIn(sorted([room_a, room_b, room_c]), [sorted(g) for g in groups])
        self.assertIn('data-tenant-key=', body)


    def test_billing_sticky_total_tracks_current_amount_on_scroll(self):
        status, body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('/static/billing_ui_extras.js', body)
        self.assertIn('ownerRoomsToggle', body)
        self.assertIn('tenant-room-list', body)
        self.assertIn('ownerRoomsSelectAll', body)
        self.assertIn('ownerRoomsClear', body)
        with open(os.path.join(PROJECT_ROOT, 'static', 'billing_ui_extras.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn('billingStickyTotal', js)
        self.assertIn('syncStickyTotal', js)
        self.assertIn('ownerRoomsSelectAll', js)
        self.assertIn('ownerRoomsClear', js)



    def test_commercial_billing_excludes_non_mall_commercial_rooms(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '通用商业租户', '13900003333')
        room_id = create_room(db, building='通用项目', unit='写字楼', room_number='OFFICE-801', category='商户', area=88, owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='通用商业租户', shop_name='通用科技店', custom_rate=6, payment_cycle='monthly' WHERE id=?", (room_id,))
        mall_id = create_room(db, building='金莎国际', unit='商场', room_number='MALL-801', category='商户', area=66, owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='商场商业租户', shop_name='商场科技店', custom_rate=6, payment_cycle='monthly' WHERE id=?", (mall_id,))
        db.commit(); db.close()

        status, commercial_body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('通用项目-写字楼-OFFICE-801', commercial_body)
        self.assertNotIn('通用科技店', commercial_body)
        self.assertIn('金莎国际-商场-MALL-801', commercial_body)
        self.assertIn('商场科技店', commercial_body)
        self.assertIn('单元/区域为商场', commercial_body)

        status, property_body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('通用项目-写字楼-OFFICE-801', property_body)
        self.assertNotIn('金莎国际-商场-MALL-801', property_body)


    def test_generic_commercial_bill_generation_scope_is_not_limited_to_mall_unit(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '通用商业出账租户', '13900004444')
        room_id = create_room(db, building='通用项目', unit='办公区', room_number='SHOP-901', category='商业', area=50, owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='通用商业出账租户', custom_rate=7, payment_cycle='monthly' WHERE id=?", (room_id,))
        fee = db.execute("SELECT id,unit_price FROM fee_types WHERE name='装修押金'").fetchone()
        db.commit(); db.close()

        status, _, loc = http_post('/bills/generate', {
            'mode_scope': 'commercial',
            'period_start': '2036-01-01',
            'period_end': '2036-03-01',
            'fee_type_ids': str(fee['id']),
            'mode': 'confirm',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)

        db = get_db()
        bill = db.execute("SELECT amount,billing_period FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee['id'])).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2036-01~2036-03')
        self.assertAlmostEqual(float(bill['amount']), float(fee['unit_price']))


    def test_commercial_billing_redirect_shows_generated_range_bill(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商场跳转租户', '13900001111')
        room_id = create_room(db, building='金莎国际', unit='商场', room_number='JUMP101', category='商户', area=20, owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='跳转租户', payment_cycle='monthly', custom_rate=5 WHERE id=?", (room_id,))
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()[0]
        db.commit(); db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2034-02-01',
            'period_end': '2034-04-01',
            'fee_types': str(fee_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        decoded = urllib.parse.unquote(loc)
        self.assertIn('/bills', decoded)
        self.assertIn('period=2034-02~2034-04', decoded)
        self.assertIn('共生成1笔账单', decoded)
        db = get_db()
        bill = db.execute("SELECT amount,billing_period FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2034-02~2034-04')
        self.assertAlmostEqual(float(bill['amount']), 203.3)


    def test_commercial_billing_generates_fixed_and_household_commercial_fees(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商场固定费租户', '13900002222')
        room_id = create_room(db, building='金莎国际', unit='商场', room_number='FIX101', category='商户', area=20, owner_id=owner_id)
        deposit_fee = db.execute("SELECT id,unit_price FROM fee_types WHERE name='装修押金'").fetchone()
        cleanup_fee = db.execute("SELECT id,unit_price FROM fee_types WHERE name='垃圾清运费'").fetchone()
        db.commit(); db.close()

        status, _, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2034-05-01',
            'period_end': '2034-05-31',
            'fee_types': [str(deposit_fee['id']), str(cleanup_fee['id'])],
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills', loc)

        db = get_db()
        rows = db.execute("""SELECT fee_type_id,amount,billing_period FROM bills
            WHERE room_id=? AND fee_type_id IN(?,?)""",
            (room_id, deposit_fee['id'], cleanup_fee['id'])).fetchall()
        db.close()
        amounts = {r['fee_type_id']: float(r['amount']) for r in rows}
        periods = {r['billing_period'] for r in rows}
        self.assertEqual(periods, {'2034-05'})
        self.assertAlmostEqual(amounts[deposit_fee['id']], float(deposit_fee['unit_price']))
        self.assertAlmostEqual(amounts[cleanup_fee['id']], float(cleanup_fee['unit_price']))


    def test_bill_receipt_setup_uses_natural_date_range(self):
        status, body = http_get('/bills/receipt_setup', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="period_start"', body)
        self.assertIn('name="period_end"', body)
        self.assertIn('按起始日期和截止日期汇总账单', body)
        self.assertNotIn('选择账期（可多选）', body)


    def test_bill_receipt_filters_by_service_date_range(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES(?, ?)", ('收据区间业主', '13933334444')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id) VALUES(?,?,?,?,?,?,?)",
            ('RECEIPTRANGE', 'A座', '2001', 20, '居民', 90, owner_id)
        ).lastrowid
        fee_type_id = db.execute("INSERT INTO fee_types(name, calc_method, unit_price, unit, sort_order) VALUES(?,?,?,?,?)", ('收据区间物业费', 'area', 3, '元/㎡', 1)).lastrowid
        db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, fee_type_id, '2035-05', 270, '2035-05-31', 'unpaid', 'RECEIPT_RANGE_IN', '2035-05-01', '2035-05-31'))
        db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, fee_type_id, '2035-07', 360, '2035-07-31', 'unpaid', 'RECEIPT_RANGE_OUT', '2035-07-01', '2035-07-31'))
        db.commit(); db.close()

        status, receipt_html = http_get(f'/bills/receipt?room_id={room_id}&period_start=2035-05-01&period_end=2035-05-31', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('收据区间业主', receipt_html)
        self.assertIn('2035-05-01 至 2035-05-31', receipt_html)
        self.assertIn('270.0', receipt_html)
        self.assertNotIn('2035-07', receipt_html)
        self.assertNotIn('360.0', receipt_html)

        status, csv_body = http_get(f'/bills/export_receipt?room_id={room_id}&period_start=2035-05-01&period_end=2035-05-31', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2035-05-01 至 2035-05-31', csv_body)
        self.assertIn('270', csv_body)
        self.assertNotIn('2035-07', csv_body)
        self.assertNotIn('360', csv_body)
