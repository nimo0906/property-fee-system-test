# 支付订单与幂等设计文档

> 日期：2026-05-31  
> 范围：阶段 3B-1，在线支付准备设计  
> 状态：设计阶段，暂不接真实微信支付、支付宝或电子票据平台。

## 1. 背景

业主端 H5 已经完成本地闭环：登录、首页、房间、账单、账单详情、支付前确认和缴费记录。下一步如果要接在线支付，不能直接让支付回调写入 `payments` 表，否则会出现重复回调重复入账、金额不一致入账、跨业主账单支付、订单状态不清晰等风险。

因此，在接微信支付或支付宝前，必须先建立“支付订单”边界和幂等处理机制。

## 2. 目标

1. 设计支付订单表 `payment_orders`。
2. 设计支付回调幂等表 `payment_callbacks`。
3. 定义支付订单状态机。
4. 定义金额核对和账单归属校验规则。
5. 定义支付成功后的入账边界。
6. 明确桌面 App 本地运行对支付回调的限制。
7. 预留模拟支付成功能力，便于本地验收。

## 3. 非目标

本阶段不做：

- 不直接接真实微信支付。
- 不直接接真实支付宝。
- 不上线公网回调地址。
- 不接电子票据平台。
- 不修改现有收款页面业务流程。
- 不做退款完整流程，只预留状态和字段。

## 4. 总体流程

```text
业主查看账单
  -> 支付前确认
  -> 创建支付订单
  -> 调用支付渠道生成支付参数或二维码
  -> 支付渠道回调
  -> 验签
  -> 幂等检查
  -> 金额和账单归属校验
  -> PaymentService.create_payment()
  -> 更新订单 paid
  -> 业主端展示缴费成功
```

本地桌面测试阶段：

```text
创建支付订单
  -> 点击“模拟支付成功”
  -> 走同一套订单校验和入账逻辑
  -> 不接公网回调
```

## 5. 数据库 schema 设计

### 5.1 payment_orders

```sql
CREATE TABLE IF NOT EXISTS payment_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT NOT NULL UNIQUE,
    owner_id INTEGER NOT NULL REFERENCES owners(id),
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    amount REAL NOT NULL,
    channel TEXT NOT NULL DEFAULT 'mock',
    status TEXT NOT NULL DEFAULT 'created',
    external_payment_id TEXT,
    idempotency_key TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT,
    paid_at TEXT,
    cancelled_at TEXT,
    failure_reason TEXT
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| order_no | 本系统支付订单号，唯一 |
| owner_id | 下单业主 |
| bill_id | 关联账单，第一阶段一笔订单只支持一个账单 |
| amount | 订单金额，必须等于支付前确认金额 |
| channel | `mock`、`wechat`、`alipay` |
| status | 订单状态 |
| external_payment_id | 微信/支付宝交易号 |
| idempotency_key | 前端或调用方传入的幂等键 |
| paid_at | 支付成功时间 |
| failure_reason | 失败原因或异常说明 |

### 5.2 payment_callbacks

```sql
CREATE TABLE IF NOT EXISTS payment_callbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    order_no TEXT NOT NULL,
    received_at TEXT DEFAULT (datetime('now','localtime')),
    processed_at TEXT,
    status TEXT NOT NULL DEFAULT 'received',
    raw_summary TEXT,
    error_message TEXT,
    UNIQUE(channel, external_event_id)
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| channel | 支付渠道 |
| external_event_id | 渠道回调事件 ID 或交易号，和 channel 组成唯一键 |
| order_no | 本系统订单号 |
| status | `received`、`processed`、`duplicate`、`failed` |
| raw_summary | 脱敏后的回调摘要，不保存密钥和完整敏感原文 |
| error_message | 处理失败原因 |

## 6. 状态机

支付订单状态：

```text
created -> pending -> paid
created -> cancelled
pending -> paid
pending -> failed
pending -> cancelled
paid -> refunded（预留）
```

状态说明：

| 状态 | 说明 |
|---|---|
| created | 本地订单已创建，还未向渠道发起支付 |
| pending | 已向渠道发起，等待支付结果 |
| paid | 已支付并已入账 |
| failed | 渠道或校验失败 |
| cancelled | 用户取消或超时取消 |
| refunded | 已退款，第一阶段只预留 |

约束：

- `paid` 状态不可再次入账。
- `cancelled` 和 `failed` 不能直接变为 `paid`，必须重新创建订单。
- 重复回调同一个 `external_event_id` 只能返回已处理结果，不能再次调用 `PaymentService.create_payment()`。

## 7. 金额和归属校验

创建订单时：

1. 业主必须已登录 owner portal。
2. `bill.owner_id` 必须等于当前业主。
3. 订单金额必须大于 0。
4. 订单金额不能超过当前欠费。
5. 如果账单已结清，不允许创建订单。

回调或模拟支付成功时：

1. 订单必须存在。
2. 订单状态必须是 `created` 或 `pending`。
3. 回调金额必须等于订单金额。
4. 回调渠道必须等于订单渠道。
5. 账单当前欠费仍然必须大于等于订单金额。
6. 入账必须调用 `PaymentService.create_payment()`。
7. 入账成功后更新订单 `paid_at` 和 `status='paid'`。

## 8. 服务层设计

建议新增 `server/payment_orders.py`。

```python
class PaymentOrderService:
    def create_order(self, owner_session, request): ...
    def get_order(self, owner_session, order_no): ...
    def list_orders(self, owner_session, filters=None): ...
    def mark_mock_paid(self, owner_session, order_no): ...
    def handle_callback(self, channel, payload): ...
```

### create_order

职责：

- 校验业主 session。
- 校验账单归属。
- 调用 `PaymentService.preview_payment()` 复用金额校验。
- 创建 `payment_orders`。
- 返回订单号、金额、渠道和状态。

### mark_mock_paid

职责：

- 仅用于本地桌面测试。
- 校验订单归属。
- 走和真实回调相同的入账逻辑。
- 调用 `PaymentService.create_payment()`。
- 更新订单状态。

### handle_callback

职责：

- 校验渠道签名。
- 使用 `payment_callbacks` 做幂等。
- 校验订单、金额、渠道和状态。
- 调用统一入账函数。
- 记录处理结果。

## 9. API 设计

### 9.1 创建支付订单

```text
POST /api/v1/owner-portal/payment-orders
```

请求：

```json
{
  "bill_id": 338,
  "amount": "90.00",
  "channel": "mock",
  "idempotency_key": "client-generated-key"
}
```

返回：

```json
{
  "ok": true,
  "data": {
    "order_no": "PO202605311830001234",
    "bill_id": 338,
    "amount": "90.00",
    "channel": "mock",
    "status": "created"
  }
}
```

### 9.2 查询支付订单

```text
GET /api/v1/owner-portal/payment-orders/{order_no}
```

### 9.3 模拟支付成功

```text
POST /api/v1/owner-portal/payment-orders/{order_no}/mock-paid
```

说明：

- 仅本地测试使用。
- 后续真实支付上线时保留为开发/测试开关，生产默认关闭。

### 9.4 支付渠道回调

```text
POST /api/v1/payment-callbacks/{channel}
```

说明：

- 真实微信/支付宝接入时需要公网可访问地址。
- 本地桌面 App 默认没有公网回调能力，需要中转服务或云端部署。

## 10. 桌面 App 限制

当前系统是本地桌面 App：

- macOS 数据目录：`~/Library/Application Support/PropertyFeeSystem`
- Windows 数据目录：`%APPDATA%\PropertyFeeSystem`
- 默认只监听 `127.0.0.1`

因此真实在线支付存在限制：

1. 微信/支付宝无法直接回调用户本机 `127.0.0.1`。
2. 如果要接真实支付，需要公网回调服务。
3. 可选方案：
   - 桌面 App + 云端支付中转服务。
   - 云端部署完整后端。
   - 本地仅做模拟支付，真实支付线下核销。

推荐路线：

```text
先做 mock 支付订单闭环
  -> 再设计云端支付中转服务
  -> 最后接真实微信/支付宝
```

## 11. 测试验收标准

自动化测试：

```bash
python3 -m pytest -q
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py
```

业务验收：

- 业主只能为本人账单创建订单。
- 订单金额不能超过欠费金额。
- mock 支付成功后新增一条 `payments`。
- mock 支付成功后账单状态更新。
- 同一订单重复 mock 支付不会重复入账。
- 重复回调不会重复入账。
- 金额不一致的回调不会入账。
- `payment_callbacks.raw_summary` 不保存密钥或完整敏感原文。
- Windows/macOS 桌面启动不受影响。

## 12. 实施建议

第一步只做本地 mock 支付订单闭环：

1. 新增 `payment_orders` 和 `payment_callbacks` schema。
2. 新增 `PaymentOrderService`。
3. 新增 owner portal 创建订单 API。
4. 新增 mock-paid API。
5. 业主端账单详情页从“支付前确认”升级为“创建模拟支付订单”。
6. 验证不会重复入账。

真实微信/支付宝放到下一阶段，并单独设计公网回调或中转服务。
