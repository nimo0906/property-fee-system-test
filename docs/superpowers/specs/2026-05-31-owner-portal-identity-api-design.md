# 业主端 H5 / 小程序身份与接口设计文档

> 日期：2026-05-31  
> 范围：阶段 3A，业主端身份、只读接口和支付前确认能力设计  
> 状态：已确认可进入设计；后续实现涉及数据库 schema 变更，实施前仍需按任务逐项验证和备份。

## 1. 目标

当前系统已经有后台操作员 JSON API，但这些 API 使用后台 session，不适合直接给业主端 H5/小程序使用。业主端需要独立身份体系，确保业主只能查看本人名下房间、账单、缴费记录，并只能发起本人账单的支付预览。

阶段 3A 目标：

1. 设计业主端身份认证流程。
2. 设计业主端只读 API 和支付预览 API。
3. 明确需要新增的数据库表。
4. 明确 macOS / Windows 桌面 App 下的本地运行要求。
5. 暂不接真实短信、微信支付、支付宝和电子票据平台。

## 2. 非目标

本阶段不做：

- 不上线公网服务。
- 不接真实短信平台。
- 不接真实微信登录或微信支付。
- 不接支付宝。
- 不做电子票据平台对接。
- 不做多项目 schema 迁移。
- 不允许业主端访问后台操作员 API。

## 3. 总体方案

推荐先实现“手机号 + 验证码占位”的本地业主端身份。

流程：

```text
业主输入手机号
  -> POST /api/v1/owner-portal/send-code
  -> 系统查 owners.phone 是否存在
  -> 生成 6 位验证码，保存到 owner_portal_login_codes
  -> 本地测试阶段把验证码返回给前端或写入可查诊断字段

业主输入验证码
  -> POST /api/v1/owner-portal/login
  -> 校验手机号、验证码、过期时间、使用状态
  -> 生成 owner_portal_sessions.token
  -> 后续请求带 owner_portal_token cookie
```

第一版不依赖公网短信，方便桌面 App 本地验收。后续接短信平台时，只替换发送验证码动作，不改变登录接口。

## 4. 数据库 schema 变更

需要新增两张表。

### 4.1 owner_portal_login_codes

用途：保存业主端登录验证码。

```sql
CREATE TABLE IF NOT EXISTS owner_portal_login_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    attempt_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| phone | 业主手机号 |
| code_hash | 验证码哈希，不保存明文验证码 |
| expires_at | 过期时间，建议 5 分钟 |
| used_at | 使用时间，非空表示已使用 |
| attempt_count | 校验失败次数 |

### 4.2 owner_portal_sessions

用途：保存业主端登录 session。

```sql
CREATE TABLE IF NOT EXISTS owner_portal_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    owner_id INTEGER NOT NULL REFERENCES owners(id),
    phone TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| token | 业主端 session token |
| owner_id | 绑定业主 |
| phone | 登录手机号 |
| expires_at | session 过期时间，建议 7 天 |
| revoked_at | 退出或失效时间 |

## 5. 安全规则

1. 验证码不保存明文，只保存哈希。
2. 验证码 5 分钟过期。
3. 同一验证码成功使用后立刻失效。
4. 同一验证码最多允许 5 次失败尝试。
5. 未匹配到业主手机号时，返回统一提示，避免泄露手机号是否存在。
6. 业主端 session 与后台操作员 session 分离。
7. 业主端只能按 `owner_id` 限制查询本人数据。
8. 业主端支付预览必须确认账单 owner_id 与当前 owner_id 一致。
9. 日志不记录验证码明文、完整身份证号或敏感支付信息。
10. 默认仍只监听 `127.0.0.1`，不把本地桌面 API 暴露到公网。

## 6. 业主端 API 设计

### 6.1 发送验证码

```text
POST /api/v1/owner-portal/send-code
```

请求：

```json
{
  "phone": "13800138000"
}
```

成功：

```json
{
  "ok": true,
  "data": {
    "message": "验证码已发送",
    "debug_code": "123456"
  }
}
```

说明：

- `debug_code` 只允许本地测试模式返回。
- 正式接短信后不返回 `debug_code`。

### 6.2 登录

```text
POST /api/v1/owner-portal/login
```

请求：

```json
{
  "phone": "13800138000",
  "code": "123456"
}
```

成功：

```json
{
  "ok": true,
  "data": {
    "owner_id": 1,
    "name": "张三",
    "expires_at": "2026-06-07 12:00:00"
  }
}
```

响应同时设置 cookie：

```text
owner_portal_token=<token>; HttpOnly; SameSite=Lax
```

### 6.3 当前业主资料

```text
GET /api/v1/owner-portal/profile
```

返回：

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "name": "张三",
    "phone": "13800138000",
    "id_card_masked": "610100********1234"
  }
}
```

### 6.4 我的房间

```text
GET /api/v1/owner-portal/rooms
```

只返回当前 owner_id 名下房间。

### 6.5 我的账单

```text
GET /api/v1/owner-portal/bills?status=unpaid
```

只返回当前 owner_id 名下账单。支持过滤：

| 参数 | 说明 |
|---|---|
| status | `unpaid`、`partial`、`paid` |
| period | 账期，如 `2026-05` |

### 6.6 我的缴费记录

```text
GET /api/v1/owner-portal/payments
```

只返回当前 owner_id 相关账单的缴费记录。

### 6.7 业主端收款预览

```text
POST /api/v1/owner-portal/payments/preview
```

请求：

```json
{
  "bill_id": 1,
  "amount": "120.00"
}
```

规则：

- 账单必须属于当前业主。
- 金额不能超过欠费。
- 不写数据库。
- 后续接在线支付时，这一步作为支付订单创建前的确认页基础。

## 7. H5 页面最小闭环

第一版 H5 不追求复杂视觉，只做可用闭环：

```text
/owner-portal/login
/owner-portal/dashboard
/owner-portal/bills
/owner-portal/bills/{id}
/owner-portal/payments
```

页面能力：

1. 手机号登录。
2. 查看本人房间。
3. 查看待缴账单。
4. 查看账单详情。
5. 查看缴费历史。
6. 进入支付前确认页。

## 8. 桌面 App 要求

macOS：

- 仍通过 `desktop_app.py` 或 `dist/物业管理收费系统.app` 启动。
- 数据表由 `db_init()` 自动补齐。
- 数据保存在 `~/Library/Application Support/PropertyFeeSystemData/database/property.db`。

Windows：

- 仍通过 `PropertyFeeSystem.exe` 或 `start_windows.bat` 启动。
- 数据表由 `db_init()` 自动补齐。
- 数据保存在 `%APPDATA%\PropertyFeeSystemData\property.db`。

通用：

- 新增 H5 模板、静态资源后，必须检查 PyInstaller spec 是否包含。
- 启动失败仍写 `startup_error.log`。
- 业主端测试数据不得放入日志。

## 9. 实施路线

### 阶段 3A-1：schema 与服务层

- `db_init()` 新增两张 owner portal 表。
- 新增 `OwnerPortalService`。
- 测试验证码生成、哈希、过期、使用后失效、失败次数。
- 测试 session 创建、过期和撤销。

### 阶段 3A-2：owner portal API

- `POST /api/v1/owner-portal/send-code`
- `POST /api/v1/owner-portal/login`
- `GET /api/v1/owner-portal/profile`
- `GET /api/v1/owner-portal/rooms`
- `GET /api/v1/owner-portal/bills`
- `GET /api/v1/owner-portal/payments`
- `POST /api/v1/owner-portal/payments/preview`

### 阶段 3A-3：H5 最小页面

- 登录页。
- 我的账单页。
- 账单详情页。
- 缴费历史页。
- 支付前确认页。

### 阶段 3B：真实短信与支付准备

- 短信服务配置。
- 支付订单表设计。
- 幂等记录表设计。
- 微信/支付宝回调验签设计。

## 10. 验收标准

自动化测试：

```bash
python3 -m pytest -q
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py
```

业务验收：

- 未登录业主端 API 返回 JSON `401 unauthorized`。
- 手机号验证码登录成功后，只能看到本人房间。
- 业主 A 不能访问业主 B 的账单。
- 收款预览不写入 payments。
- 验证码过期后不能登录。
- 验证码使用后不能重复登录。
- 后台操作员登录状态与业主端登录状态互不影响。
- macOS 和 Windows 桌面启动入口不受影响。

## 11. 风险与处理

| 风险 | 影响 | 处理 |
|---|---|---|
| 手机号重复绑定多个业主 | 登录后数据归属不清 | 第一版允许一个手机号匹配多个 owner 时返回需后台处理，不自动登录 |
| 验证码被暴力尝试 | 安全风险 | 限制失败次数和过期时间 |
| 业主越权查账单 | 严重数据泄露 | 所有 owner portal 查询必须带当前 owner_id 条件 |
| 本地 debug_code 泄露 | 安全风险 | 仅本地测试返回，正式短信接入关闭 |
| schema 变更影响旧库 | 启动失败 | 通过 `CREATE TABLE IF NOT EXISTS` 和测试覆盖旧库补表 |
