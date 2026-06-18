# v2.0 内部 JSON API 说明

> 适用范围：当前桌面 App 内部接口、后续 H5/小程序前置联调。  
> 当前定位：本地桌面系统的受控接口，不是公网开放 API。  
> 最后更新：2026-05-31。

## 1. 基本原则

- 默认访问地址来自桌面启动器打开的本地地址，例如：`http://127.0.0.1:53123`。
- 服务默认只监听 `127.0.0.1`，不面向公网开放。
- API 复用后台登录 session，未登录不能访问。
- 当前 API 用于内部扩展准备，后续业主端 H5/小程序应另行设计业主身份绑定，不直接复用后台操作员账号。
- 写入接口必须走服务层，不允许绕过 `PaymentService` 等核心服务直接写库。
- 不在日志中记录支付密钥、身份证完整号码、支付回调原文等敏感信息。

## 2. 认证方式

当前使用现有后台登录 cookie：

```text
session_token=<token>
```

未登录访问 API 返回 JSON，不返回 HTML 登录页。

```json
{
  "ok": false,
  "error": {
    "code": "unauthorized",
    "message": "请先登录"
  }
}
```

## 3. 统一响应格式

成功：

```json
{
  "ok": true,
  "data": {}
}
```

失败：

```json
{
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "收款金额不能超过欠费金额"
  }
}
```

## 4. 错误码

| HTTP 状态 | code | 说明 |
|---|---|---|
| 401 | `unauthorized` | 未登录或 session 无效 |
| 403 | `forbidden` | 当前角色无权执行该操作 |
| 400 | `validation_error` | 参数或业务校验失败 |
| 404 | `not_found` | 资源或接口不存在 |

## 5. 权限规则

| 接口类型 | admin | operator | readonly |
|---|---:|---:|---:|
| 查询业主、房间、账单 | ✅ | ✅ | ✅ |
| 收款预览 | ✅ | ✅ | ✅ |
| 真实收款写入 | ✅ | ✅ | ❌ |

说明：`readonly` 允许做收款预览，是为了客服或前台可以核对欠费影响；但不能真实入账。

## 6. 当前接口清单

| 方法 | 路径 | 用途 | 写库 |
|---|---|---|---:|
| GET | `/api/v1/owners/{id}` | 查询业主详情和关联房间 | 否 |
| GET | `/api/v1/rooms/{id}` | 查询房间详情和业主摘要 | 否 |
| GET | `/api/v1/bills/{id}` | 查询账单详情、已缴和欠费 | 否 |
| POST | `/api/v1/payments/preview` | 收款前预览 | 否 |
| POST | `/api/v1/payments` | 创建收款记录 | 是 |

## 7. 查询业主

```text
GET /api/v1/owners/1
```

成功示例：

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "name": "张三",
    "phone": "13800138000",
    "id_card_masked": "610100********1234",
    "rooms": [
      {
        "id": 1,
        "building": "住宅楼",
        "unit": "1单元",
        "room_number": "1801",
        "floor": 18,
        "category": "商户",
        "area": 88.5
      }
    ]
  }
}
```

注意：接口不返回完整 `id_card`。

## 8. 查询房间

```text
GET /api/v1/rooms/1
```

成功示例：

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "building": "住宅楼",
    "unit": "1单元",
    "room_number": "1801",
    "floor": 18,
    "category": "商户",
    "area": 88.5,
    "owner_id": 1,
    "owner": {
      "id": 1,
      "name": "张三",
      "phone": "13800138000"
    }
  }
}
```

## 9. 查询账单

```text
GET /api/v1/bills/1
```

成功示例：

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "bill_number": "BILL-001",
    "period": "2026-05",
    "status": "unpaid",
    "amount": "177.00",
    "paid_amount": "77.00",
    "unpaid_amount": "100.00",
    "due_date": "2026-05-31",
    "fee_type": {
      "id": 1,
      "name": "物业费"
    },
    "room": {
      "id": 1,
      "building": "住宅楼",
      "unit": "1单元",
      "room_number": "1801",
      "area": 88.5
    },
    "owner": {
      "id": 1,
      "name": "张三",
      "phone": "13800138000"
    }
  }
}
```

## 10. 收款预览

```text
POST /api/v1/payments/preview
Content-Type: application/x-www-form-urlencoded

bill_id=1&amount=40.00&method=cash
```

成功示例：

```json
{
  "ok": true,
  "data": {
    "bill_id": 1,
    "amount": "40.00",
    "unpaid_before": "120.00",
    "unpaid_after": "80.00",
    "will_mark_paid": false
  }
}
```

校验：

- 金额必须大于 0。
- 金额不能超过当前欠费。
- 只预览，不新增 `payments` 记录，不修改账单状态。

## 11. 创建收款

```text
POST /api/v1/payments
Content-Type: application/x-www-form-urlencoded

bill_id=1&amount=120.00&method=cash&idempotency_key=future-key-1
```

成功示例：

```json
{
  "ok": true,
  "data": {
    "payment_id": 10,
    "bill_id": 1,
    "amount": "120.00",
    "method": "cash",
    "bill_status": "paid",
    "backup_name": "auto_before_api_payment_20260531_163000_000000.db",
    "idempotency_key": "future-key-1"
  }
}
```

写入行为：

- 写入前创建 `auto_before_api_payment_*.db` 自动备份。
- 通过 `PaymentService.create_payment()` 入账。
- 写入 `audit_logs`，动作为 `api_payment_create`。
- `readonly` 角色不能调用。

幂等说明：

- 当前接口接受并返回 `idempotency_key`，用于后续在线支付接入的协议预留。
- 当前没有修改数据库 schema，因此还没有持久化幂等去重。
- 真正接微信支付、支付宝回调前，应单独设计支付订单表或幂等记录表，并先确认 schema 变更。

## 12. 桌面 App 验收注意事项

macOS：

```text
./build_macos_app.command
open dist/物业收费管理系统.app
```

Windows：

```text
build_windows_exe.bat
dist\PropertyBillingSystem\PropertyBillingSystem.exe
```

验收 API 时注意：

- API 地址使用桌面窗口打开的本地端口。
- 登录后复制同一浏览器会话 cookie 才能访问 API。
- 不要把本地 API 暴露到公网。
- 新增 API 文件或文档后，维护人员要检查 PyInstaller spec 是否需要纳入新资源。
- 真实收款 API 会写数据库，测试前先备份或使用测试账单。

## 13. 当前自动化验证命令

```bash
python3 -m pytest tests/test_core_services.py tests/test_integration.py -q
python3 -m pytest -q
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py
```
