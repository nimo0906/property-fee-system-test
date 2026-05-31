# v2.0 Core Services Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抽出账单、收款、业主、房间四个稳定内部服务接口，先服务现有桌面端和后续 `/api/v1`、业主端 H5/小程序扩展。

**Architecture:** 新增轻量服务层文件，服务层返回结构化 dict/list，不返回 HTML，不持有页面状态。第一轮只抽取低风险核心能力：只读查询、账单生成预览、收款预览/入账校验、业主/房间关联查询；现有页面暂不大改，先为后续路由迁移建立可测试接口。

**Tech Stack:** Python 标准库、SQLite、现有 `server.db`、`unittest`/`pytest`、桌面入口 `desktop_app.py`、PyInstaller spec。

---

## File Structure

- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/services.py`
  - 统一导出 `Actor`、`ServiceError`、`BillingService`、`PaymentService`、`OwnerService`、`RoomService`。
  - 控制在 300 行以内；只做第一阶段必要接口。
- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_core_services.py`
  - 覆盖四个服务的核心业务规则。
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/__init__.py`
  - 如现有包导入需要，无强制修改；优先不动。
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/docs/superpowers/specs/2026-05-31-v2-extension-readiness-design.md`
  - 如果实施中发现设计需要更正，只追加“实施备注”，不重写大段内容。

## Task 1: Add OwnerService and RoomService read interfaces

**Files:**
- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_core_services.py`
- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/services.py`

- [ ] **Step 1: Write failing tests for owner and room queries**

Add this complete file to `tests/test_core_services.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for v2.0 core service interfaces."""

import os
import tempfile
import time
import unittest

_db_path = os.path.join(tempfile.gettempdir(), f'test_services_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups')

from server.db import db_init, get_db
from server.services import OwnerService, RoomService


class TestOwnerAndRoomServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_init()

    @classmethod
    def tearDownClass(cls):
        for suffix in ('', '-wal', '-shm'):
            path = _db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def setUp(self):
        self.db = get_db()
        for table in ('payments', 'bills', 'rooms', 'owners'):
            self.db.execute(f'DELETE FROM {table}')
        self.owner_id = self.db.execute(
            "INSERT INTO owners (name, phone, id_card) VALUES (?, ?, ?)",
            ('张三', '13800138000', '610100199001011234'),
        ).lastrowid
        self.room_id = self.db.execute(
            "INSERT INTO rooms (building, unit, room_number, floor, category, area, owner_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ('B座', '1单元', '1801', 18, '商户', 88.5, self.owner_id),
        ).lastrowid
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_owner_detail_masks_sensitive_id_card_and_includes_rooms(self):
        owner = OwnerService().get_owner(self.owner_id)

        self.assertEqual(owner['id'], self.owner_id)
        self.assertEqual(owner['name'], '张三')
        self.assertEqual(owner['phone'], '13800138000')
        self.assertEqual(owner['id_card_masked'], '610100********1234')
        self.assertNotIn('id_card', owner)
        self.assertEqual(owner['rooms'][0]['room_number'], '1801')

    def test_room_detail_includes_owner_summary(self):
        room = RoomService().get_room(self.room_id)

        self.assertEqual(room['id'], self.room_id)
        self.assertEqual(room['building'], 'B座')
        self.assertEqual(room['area'], 88.5)
        self.assertEqual(room['owner']['id'], self.owner_id)
        self.assertEqual(room['owner']['name'], '张三')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_core_services.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'server.services'`.

- [ ] **Step 3: Implement minimal OwnerService and RoomService**

Create `server/services.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable internal service interfaces for v2.0 expansion."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from server.db import get_db


class ServiceError(Exception):
    """Business-level service error safe to show to operators."""


@dataclass(frozen=True)
class Actor:
    username: str = ''
    role: str = ''


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _mask_id_card(value):
    text = str(value or '').strip()
    if len(text) <= 8:
        return text
    return text[:6] + '*' * (len(text) - 10) + text[-4:]


class OwnerService:
    def get_owner(self, owner_id):
        db = get_db()
        try:
            owner = db.execute('SELECT * FROM owners WHERE id=?', (owner_id,)).fetchone()
            if not owner:
                raise ServiceError('业主不存在')
            rooms = db.execute(
                'SELECT id, building, unit, room_number, floor, category, area '
                'FROM rooms WHERE owner_id=? ORDER BY building, unit, room_number',
                (owner_id,),
            ).fetchall()
            result = {
                'id': owner['id'],
                'name': owner['name'],
                'phone': owner['phone'] or '',
                'id_card_masked': _mask_id_card(owner['id_card'] if 'id_card' in owner.keys() else ''),
                'rooms': [dict(r) for r in rooms],
            }
            return result
        finally:
            db.close()


class RoomService:
    def get_room(self, room_id):
        db = get_db()
        try:
            room = db.execute(
                'SELECT r.*, o.name AS owner_name, o.phone AS owner_phone '
                'FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id WHERE r.id=?',
                (room_id,),
            ).fetchone()
            if not room:
                raise ServiceError('房间不存在')
            result = dict(room)
            owner_id = result.get('owner_id')
            result['owner'] = None
            if owner_id:
                result['owner'] = {
                    'id': owner_id,
                    'name': result.pop('owner_name', '') or '',
                    'phone': result.pop('owner_phone', '') or '',
                }
            else:
                result.pop('owner_name', None)
                result.pop('owner_phone', None)
            return result
        finally:
            db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/test_core_services.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit Task 1**

```bash
git add server/services.py tests/test_core_services.py
git commit -m "feat: 抽出业主和房间服务接口"
```

## Task 2: Add BillingService read and generation preview interfaces

**Files:**
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_core_services.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/services.py`

- [ ] **Step 1: Add failing tests for bill detail and generation preview**

Append these tests inside `TestOwnerAndRoomServices` in `tests/test_core_services.py`:

```python
    def test_billing_service_get_bill_returns_amount_breakdown(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试物业费', 'area', 2.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-05', 177.0, '2026-05-31', 'unpaid', 'BILL-SVC-1'),
        ).lastrowid
        self.db.execute(
            "INSERT INTO payments (bill_id, amount_paid, payment_date, payment_method, operator) "
            "VALUES (?, ?, datetime('now','localtime'), ?, ?)",
            (bill_id, 77.0, 'cash', 'admin'),
        )
        self.db.commit()

        from server.services import BillingService
        bill = BillingService().get_bill(bill_id)

        self.assertEqual(bill['id'], bill_id)
        self.assertEqual(bill['bill_number'], 'BILL-SVC-1')
        self.assertEqual(bill['amount'], '177.00')
        self.assertEqual(bill['paid_amount'], '77.00')
        self.assertEqual(bill['unpaid_amount'], '100.00')
        self.assertEqual(bill['room']['room_number'], '1801')
        self.assertEqual(bill['owner']['name'], '张三')

    def test_billing_generation_preview_does_not_write_bills(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试面积费', 'area', 3.0),
        ).lastrowid
        self.db.commit()

        from server.services import BillingService
        before = self.db.execute('SELECT COUNT(*) FROM bills').fetchone()[0]
        plan = BillingService().preview_generation({
            'period': '2026-06',
            'due_date': '2026-06-30',
            'fee_type_ids': [fee_type_id],
        })
        after = self.db.execute('SELECT COUNT(*) FROM bills').fetchone()[0]

        self.assertEqual(before, after)
        self.assertEqual(plan['period'], '2026-06')
        self.assertEqual(plan['items'][0]['room_id'], self.room_id)
        self.assertEqual(plan['items'][0]['amount'], '265.50')
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_core_services.py -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `BillingService`.

- [ ] **Step 3: Implement minimal BillingService**

Append this class to `server/services.py`:

```python
class BillingService:
    def get_bill(self, bill_id):
        db = get_db()
        try:
            row = db.execute(
                'SELECT b.*, ft.name AS fee_type_name, r.building, r.unit, r.room_number, '
                'r.area, o.name AS owner_name, o.phone AS owner_phone '
                'FROM bills b '
                'LEFT JOIN fee_types ft ON b.fee_type_id=ft.id '
                'LEFT JOIN rooms r ON b.room_id=r.id '
                'LEFT JOIN owners o ON b.owner_id=o.id '
                'WHERE b.id=?',
                (bill_id,),
            ).fetchone()
            if not row:
                raise ServiceError('账单不存在')
            paid = db.execute(
                'SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=?',
                (bill_id,),
            ).fetchone()[0]
            amount = _money(row['amount'])
            paid_amount = _money(paid)
            return {
                'id': row['id'],
                'bill_number': row['bill_number'],
                'period': row['billing_period'],
                'status': row['status'],
                'amount': str(amount),
                'paid_amount': str(paid_amount),
                'unpaid_amount': str(max(Decimal('0.00'), amount - paid_amount)),
                'due_date': row['due_date'],
                'fee_type': {'id': row['fee_type_id'], 'name': row['fee_type_name'] or ''},
                'room': {
                    'id': row['room_id'],
                    'building': row['building'] or '',
                    'unit': row['unit'] or '',
                    'room_number': row['room_number'] or '',
                    'area': row['area'] or 0,
                },
                'owner': {'id': row['owner_id'], 'name': row['owner_name'] or '', 'phone': row['owner_phone'] or ''},
            }
        finally:
            db.close()

    def preview_generation(self, request):
        period = request.get('period') or ''
        due_date = request.get('due_date') or ''
        fee_type_ids = request.get('fee_type_ids') or []
        db = get_db()
        try:
            items = []
            rooms = db.execute('SELECT * FROM rooms ORDER BY building, unit, room_number').fetchall()
            for fee_type_id in fee_type_ids:
                fee = db.execute('SELECT * FROM fee_types WHERE id=?', (fee_type_id,)).fetchone()
                if not fee:
                    continue
                for room in rooms:
                    exists = db.execute(
                        'SELECT id FROM bills WHERE room_id=? AND fee_type_id=? AND billing_period=?',
                        (room['id'], fee_type_id, period),
                    ).fetchone()
                    if exists:
                        continue
                    method = fee['calc_method'] or 'fixed'
                    if method == 'area':
                        amount = _money(Decimal(str(room['area'] or 0)) * Decimal(str(fee['unit_price'] or 0)))
                    elif method == 'per_household':
                        amount = _money(fee['unit_price'] or 0)
                    else:
                        amount = _money(fee['unit_price'] or 0)
                    items.append({
                        'room_id': room['id'],
                        'fee_type_id': fee_type_id,
                        'period': period,
                        'due_date': due_date,
                        'amount': str(amount),
                    })
            return {'period': period, 'due_date': due_date, 'items': items, 'total_count': len(items)}
        finally:
            db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/test_core_services.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add server/services.py tests/test_core_services.py
git commit -m "feat: 抽出账单查询和生成预览服务接口"
```

## Task 3: Add PaymentService preview and payment creation guard

**Files:**
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_core_services.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/services.py`

- [ ] **Step 1: Add failing tests for payment preview and overpay guard**

Append these tests inside `TestOwnerAndRoomServices`:

```python
    def test_payment_preview_rejects_amount_greater_than_unpaid(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试停车费', 'fixed', 100.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-07', 100.0, '2026-07-31', 'unpaid', 'BILL-PAY-1'),
        ).lastrowid
        self.db.commit()

        from server.services import PaymentService, ServiceError
        with self.assertRaisesRegex(ServiceError, '收款金额不能超过欠费金额'):
            PaymentService().preview_payment({'bill_id': bill_id, 'amount': '120.00'})

    def test_payment_create_marks_bill_paid_when_fully_collected(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试垃圾费', 'fixed', 10.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-08', 10.0, '2026-08-31', 'unpaid', 'BILL-PAY-2'),
        ).lastrowid
        self.db.commit()

        from server.services import Actor, PaymentService
        result = PaymentService().create_payment(
            {'bill_id': bill_id, 'amount': '10.00', 'method': 'cash'},
            Actor(username='admin', role='admin'),
        )
        bill = self.db.execute('SELECT status FROM bills WHERE id=?', (bill_id,)).fetchone()

        self.assertEqual(result['amount'], '10.00')
        self.assertEqual(result['bill_status'], 'paid')
        self.assertEqual(bill['status'], 'paid')
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_core_services.py -q
```

Expected: FAIL with missing `PaymentService`.

- [ ] **Step 3: Implement minimal PaymentService**

Append this class to `server/services.py`:

```python
class PaymentService:
    def preview_payment(self, request):
        bill_id = int(request.get('bill_id') or 0)
        amount = _money(request.get('amount') or 0)
        bill = BillingService().get_bill(bill_id)
        unpaid = Decimal(bill['unpaid_amount'])
        if amount <= Decimal('0.00'):
            raise ServiceError('收款金额必须大于0')
        if amount > unpaid:
            raise ServiceError('收款金额不能超过欠费金额')
        return {
            'bill_id': bill_id,
            'amount': str(amount),
            'unpaid_before': str(unpaid),
            'unpaid_after': str(unpaid - amount),
            'will_mark_paid': amount == unpaid,
        }

    def create_payment(self, request, actor=None):
        actor = actor or Actor()
        preview = self.preview_payment(request)
        bill_id = preview['bill_id']
        amount = Decimal(preview['amount'])
        method = request.get('method') or 'cash'
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO payments (bill_id, amount_paid, payment_date, payment_method, operator) "
                "VALUES (?, ?, datetime('now','localtime'), ?, ?)",
                (bill_id, float(amount), method, actor.username),
            )
            new_status = 'paid' if preview['will_mark_paid'] else 'partial'
            db.execute('UPDATE bills SET status=? WHERE id=?', (new_status, bill_id))
            db.commit()
            return {
                'payment_id': cur.lastrowid,
                'bill_id': bill_id,
                'amount': str(amount),
                'method': method,
                'bill_status': new_status,
            }
        finally:
            db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/test_core_services.py -q
```

Expected: all core service tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add server/services.py tests/test_core_services.py
git commit -m "feat: 抽出收款预览和入账服务接口"
```

## Task 4: Run repository verification and commit plan/docs status

**Files:**
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/docs/superpowers/plans/2026-05-31-v2-core-services.md`

- [ ] **Step 1: Run focused service tests**

Run:

```bash
python3 -m pytest tests/test_core_services.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run full existing tests**

Run:

```bash
python3 -m pytest -q
```

Expected: all tests pass. If tests fail because of existing environment or unrelated data fixture issues, capture the exact failure and do not hide it.

- [ ] **Step 3: Run py_compile verification**

Run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py
```

Expected: command exits 0 with no output.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short --branch
```

Expected: only intended tracked changes remain; ignored DB/build/cache files do not appear.

- [ ] **Step 5: Commit plan if not committed**

Run:

```bash
git add docs/superpowers/plans/2026-05-31-v2-core-services.md
git commit -m "docs: 编写核心服务接口实施计划"
```

Expected: plan committed. If already committed, skip with clear note.

## Self-Review

- Spec coverage: 阶段 1 的四类核心接口由 Task 1-3 覆盖；桌面要求没有代码改动，但 Task 4 保留桌面入口编译验证；H5/支付/通知/票据/多项目只保留设计边界，不进入本轮代码。
- Placeholder scan: 本计划不包含 placeholder markers。
- Type consistency: `Actor`、`ServiceError`、`OwnerService`、`RoomService`、`BillingService`、`PaymentService` 均在 `server/services.py` 定义；测试引用与定义一致。
