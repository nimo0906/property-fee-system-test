# 物业管理收费系统 v2.0 扩展准备设计文档

> 日期：2026-05-31  
> 范围：第三阶段 v2.0 扩展准备  
> 目标：先抽出稳定的账单、收款、业主、房间接口，再为业主端 H5/小程序、在线支付、通知、电子票据、多项目管理预留边界。交付形态继续以桌面 App 为主，同时满足 macOS 和 Windows 的本地使用要求。

## 1. 背景与成功标准

当前系统已经是本地网页应用 + 桌面启动器的形态，核心业务集中在账单、收费、业主、房间、报表、导入、备份等模块。第三阶段不应一开始就做 H5、小程序或支付对接，而应先把内部业务能力沉淀为稳定接口，避免后续每接一个新端都直接依赖页面处理函数或数据库细节。

本阶段完成后，应达到以下标准：

1. 账单、收款、业主、房间四类核心能力有清晰的服务接口边界。
2. 现有桌面端页面继续可用，行为不倒退。
3. 新接口不直接暴露数据库连接、SQL 细节或页面 HTML。
4. H5/小程序以后只依赖稳定接口，不反向绑定桌面页面路由。
5. 在线支付、通知、电子票据、多项目管理有明确扩展点，但本阶段不直接接真实第三方平台。
6. macOS 和 Windows 桌面 App 的数据目录、打包资源、启动诊断、端口、安全边界都有验收要求。

## 2. 非目标

本设计文档只定义扩展准备方案，不在本阶段直接完成以下事项：

- 不接真实微信支付、支付宝、短信、电子发票平台。
- 不立即上线公网 API。
- 不把 SQLite 强制迁移到其他数据库。
- 不改动现有数据库 schema，除非后续单独确认。
- 不做多项目管理的数据迁移，只预留项目上下文边界。
- 不把桌面 App 改成必须联网的 SaaS 形态。

## 3. 推荐方案

推荐采用“内部服务接口先行，HTTP API 后置开放”的方案。

### 方案 A：直接开放 REST API

优点是 H5/小程序可以较快接入。缺点是当前系统的认证、权限、错误码、版本管理、幂等、审计还没有完全按开放 API 标准整理，贸然开放容易把临时结构固化。

### 方案 B：先抽内部服务接口，再逐步开放 HTTP API（推荐）

先在本地代码内抽出账单、收款、业主、房间服务接口，桌面页面仍调用这些服务。待服务接口稳定后，再增加 `/api/v1/...` JSON 路由给 H5/小程序使用。

优点是风险低，不影响现有桌面端；后续接移动端和第三方平台时有稳定底座。缺点是第一阶段看起来不如直接做 H5 快，但长期维护成本更低。

### 方案 C：重构为前后端分离

优点是长期架构更现代。缺点是改动面大，会显著增加打包复杂度和普通用户部署难度，不符合当前桌面 App 优先的交付要求。

结论：采用方案 B。

## 4. 分层架构

目标架构保持轻量，不引入不必要框架。

```text
Desktop App
  ├─ macOS .app / Windows .exe
  ├─ desktop_app.py / desktop_runtime.py
  └─ local HTTP server 127.0.0.1:dynamic-port

Presentation Layer
  ├─ existing HTML routes
  └─ future /api/v1 JSON routes

Application Services
  ├─ BillingService
  ├─ PaymentService
  ├─ OwnerService
  └─ RoomService

Domain / Infrastructure
  ├─ billing_engine.py
  ├─ payment_ledger.py
  ├─ db.py
  ├─ backups.py
  └─ SQLite property.db
```

核心原则：

- 页面路由只负责请求解析、权限判断、渲染响应。
- 服务层负责业务动作和业务校验。
- 数据库访问集中封装，避免新增页面继续散落 SQL。
- 写操作必须保留审计、备份、权限和错误处理。
- 服务返回结构化结果，不返回 HTML。

## 5. 核心接口边界

### 5.1 账单接口 BillingService

职责：查询账单、生成账单、调整账单、删除账单、计算滞纳金、导出账单数据。

建议接口：

```python
class BillingService:
    def list_bills(self, filters: BillFilters) -> BillListResult: ...
    def get_bill(self, bill_id: int) -> BillDetail: ...
    def preview_generation(self, request: BillGenerationRequest) -> BillGenerationPlan: ...
    def generate_bills(self, request: BillGenerationRequest, actor: Actor) -> BillGenerationResult: ...
    def update_bill_amount(self, bill_id: int, request: BillAdjustmentRequest, actor: Actor) -> BillDetail: ...
    def delete_bill(self, bill_id: int, reason: str, actor: Actor) -> DeleteResult: ...
    def calculate_late_fee(self, bill_id: int) -> Money: ...
```

边界要求：

- `generate_bills` 必须支持预览和正式写入分离。
- 修改金额必须记录原因、操作人、修改前后金额。
- 删除账单属于高风险动作，继续只允许管理或明确权限角色执行。
- 账单金额使用统一金额类型或 Decimal，避免浮点误差。
- 返回值中区分 `total_amount`、`paid_amount`、`unpaid_amount`、`late_fee`。

### 5.2 收款接口 PaymentService

职责：单笔收款、批量收款、收款流水、退款或冲正预留、对账导出。

建议接口：

```python
class PaymentService:
    def preview_payment(self, request: PaymentRequest) -> PaymentPreview: ...
    def create_payment(self, request: PaymentRequest, actor: Actor) -> PaymentResult: ...
    def create_batch_payment(self, request: BatchPaymentRequest, actor: Actor) -> BatchPaymentResult: ...
    def list_payments(self, filters: PaymentFilters) -> PaymentListResult: ...
    def get_payment(self, payment_id: int) -> PaymentDetail: ...
    def void_payment(self, payment_id: int, reason: str, actor: Actor) -> VoidResult: ...
```

边界要求：

- 收款写入前自动备份。
- 同一账单重复收款必须校验剩余欠费。
- 线上支付回调以后必须通过幂等键处理，不能重复入账。
- 本阶段只预留 `external_payment_id`、`channel`、`idempotency_key` 等概念，不直接改 schema。
- 收款结果要能驱动收据、发票、通知三类后续动作。

### 5.3 业主接口 OwnerService

职责：业主增删改查、联系方式校验、业主与房间关系查询、业主端身份绑定预留。

建议接口：

```python
class OwnerService:
    def list_owners(self, filters: OwnerFilters) -> OwnerListResult: ...
    def get_owner(self, owner_id: int) -> OwnerDetail: ...
    def create_owner(self, request: OwnerWriteRequest, actor: Actor) -> OwnerDetail: ...
    def update_owner(self, owner_id: int, request: OwnerWriteRequest, actor: Actor) -> OwnerDetail: ...
    def delete_owner(self, owner_id: int, actor: Actor) -> DeleteResult: ...
    def get_owner_portal_profile(self, owner_id: int) -> OwnerPortalProfile: ...
```

边界要求：

- 手机号、身份证等敏感信息不能写入普通日志。
- 业主端 H5/小程序只能看到本人绑定房间和账单。
- 删除业主前必须检查房间、账单、收款关联。
- 后续身份绑定建议采用手机号 + 验证码或微信 openid 绑定，不依赖后台登录账号。

### 5.4 房间接口 RoomService

职责：房间资料、楼栋单元房号、面积、类别、合同期、业主绑定、批量调价预留。

建议接口：

```python
class RoomService:
    def list_rooms(self, filters: RoomFilters) -> RoomListResult: ...
    def get_room(self, room_id: int) -> RoomDetail: ...
    def create_room(self, request: RoomWriteRequest, actor: Actor) -> RoomDetail: ...
    def update_room(self, room_id: int, request: RoomWriteRequest, actor: Actor) -> RoomDetail: ...
    def delete_room(self, room_id: int, actor: Actor) -> DeleteResult: ...
    def list_room_bills(self, room_id: int, filters: BillFilters) -> BillListResult: ...
```

边界要求：

- 房间是账单、收款、业主端查询的核心关联对象，不能随意物理删除有关联数据的房间。
- 面积、类别、合同期变化会影响后续出账，必须记录审计。
- 多项目管理以后，房间查询必须带项目上下文，避免跨项目数据串查。

## 6. H5 / 小程序准备

业主端建议分两步做：

### 6.1 H5 优先

先做本地或内网 H5 业主端，验证业务闭环：

- 业主身份绑定。
- 查看本人房间。
- 查看待缴账单。
- 查看历史缴费。
- 下载或查看收据/电子票据状态。
- 发起在线支付前的订单预览。

H5 的优势是迭代快，和桌面 App 可以共用后端接口。

### 6.2 小程序后接

小程序接入时复用 `/api/v1/owner-portal/...`，只增加微信登录、openid 绑定、微信支付参数生成等适配层，不重写账单和收款逻辑。

业主端 API 初步建议：

```text
GET  /api/v1/owner-portal/profile
GET  /api/v1/owner-portal/rooms
GET  /api/v1/owner-portal/bills?status=unpaid
GET  /api/v1/owner-portal/payments
POST /api/v1/owner-portal/payment-orders
```

## 7. 在线支付、通知、电子票据、多项目扩展点

### 7.1 在线支付

先定义支付订单概念，再接支付渠道。

```text
PaymentOrder
  ├─ order_no
  ├─ owner_id
  ├─ bill_ids
  ├─ amount
  ├─ channel
  ├─ status
  ├─ external_payment_id
  └─ idempotency_key
```

回调处理要求：

- 必须验签。
- 必须幂等。
- 必须核对金额、订单状态、账单状态。
- 成功后通过 PaymentService 入账，不直接写数据库。

### 7.2 通知

通知统一走事件模型，不把短信、微信、邮件逻辑写进收款或账单核心流程。

建议事件：

```text
BillGenerated
PaymentReceived
BillOverdue
InvoiceIssued
RepairStatusChanged
```

本阶段只需在接口设计中预留事件，不直接接短信平台。

### 7.3 电子票据

电子票据应依赖收款结果和发票状态，不应在收款写入时强制同步开票。

建议流程：

1. 收款成功。
2. 生成待开票记录或允许人工触发。
3. 调用电子票据平台。
4. 回写票据号码、状态、下载地址。
5. 通知业主端可查看。

### 7.4 多项目管理

多项目管理会影响所有核心表和查询权限，属于高风险 schema 变更，应单独设计和确认。

本阶段只做代码边界预留：

- 服务接口统一接受 `ProjectContext`。
- 当前单项目桌面版默认 `project_id = default`。
- 不在本阶段给现有表直接加 `project_id`。
- 后续迁移前必须出具数据迁移方案、备份方案、回滚方案。

## 8. 桌面 App 要求

### 8.1 通用要求

- 默认只监听 `127.0.0.1`，不对局域网或公网开放。
- 端口使用动态空闲端口，避免与用户电脑上其他服务冲突。
- 数据库写入用户数据目录，不写安装目录。
- 新增模板、静态文件、文档、依赖时必须同步检查 PyInstaller spec。
- 启动失败必须落到用户可找到的错误日志。
- 退出桌面窗口后本地服务应停止。

### 8.2 macOS 要求

交付入口：

```text
build_macos_app.command -> dist/物业管理收费系统.app
```

数据目录：

```text
~/Library/Application Support/PropertyFeeSystem
```

验收要求：

- 双击 `.app` 能启动桌面窗口。
- 浏览器能打开本地登录页。
- `property.db` 和 `backups` 出现在用户数据目录。
- 启动失败能找到 `startup_error.log`。
- 打包后模板、静态资源、说明文档可访问。

### 8.3 Windows 要求

交付入口：

```text
build_windows_exe.bat -> dist\PropertyFeeSystem\PropertyFeeSystem.exe
```

数据目录：

```text
%APPDATA%\PropertyFeeSystem
```

验收要求：

- 双击 `.exe` 能启动桌面窗口。
- 首次使用缺依赖时有清晰诊断。
- `diagnose_windows.bat` 能输出 Python、数据目录、数据库、备份目录、缺失依赖。
- 交付时必须复制整个 `dist\PropertyFeeSystem` 文件夹，而不是单独复制 exe。
- Windows 路径、中文文件名、空格路径都不能导致启动失败。

## 9. 分阶段路线

### 阶段 1：接口抽取准备

目标：把账单、收款、业主、房间核心业务从页面处理函数中抽出服务边界。

交付物：

- `BillingService`
- `PaymentService`
- `OwnerService`
- `RoomService`
- 服务层单元测试
- 页面路由回归测试

验收：

- 原有测试通过。
- 账单生成、收费、业主管理、房间管理页面可正常使用。
- 服务层测试覆盖关键业务规则，而不是只测试有返回。

### 阶段 2：内部 JSON API

目标：在本地桌面服务中增加受控 `/api/v1` JSON 接口，先供内部 H5 使用。

交付物：

- API 错误码约定。
- API 认证与权限边界。
- 账单、收款、业主、房间只读接口。
- 必要写接口的 CSRF 或 token 保护方案。

验收：

- 未登录访问 API 返回明确错误。
- readonly 不能执行写操作。
- API 不返回身份证完整号码等敏感字段。
- 桌面页面与 API 共用服务层。

### 阶段 3：业主端 H5

目标：业主可查本人房间、账单、缴费记录，并能进入支付前确认页。

交付物：

- 业主端登录或绑定流程。
- 待缴账单列表。
- 缴费历史。
- 支付订单预览。

验收：

- 业主只能看到本人数据。
- H5 在手机浏览器可正常使用。
- 桌面端管理员能查看业主端绑定状态。

### 阶段 4：小程序与在线支付

目标：在 H5 验证通过后接小程序和支付渠道。

交付物：

- 小程序登录适配。
- 支付订单创建。
- 支付回调验签和幂等处理。
- 支付成功自动入账。

验收：

- 重复回调不会重复收款。
- 金额不一致不会入账。
- 支付成功后桌面端和业主端状态一致。

### 阶段 5：通知、电子票据、多项目

目标：在核心接口稳定后扩展平台能力。

交付物：

- 通知事件队列或本地事件表。
- 电子票据状态流转。
- 多项目 schema 设计和迁移方案。

验收：

- 通知失败不影响收款入账。
- 电子票据失败可重试。
- 多项目迁移前可完整备份和回滚。

## 10. 测试验收标准

### 10.1 自动化测试

每个阶段至少运行：

```bash
python3 -m pytest
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py
```

新增服务层后，应增加以下测试：

- 账单生成预览不写库。
- 正式生成账单金额正确。
- 收款不能超过欠费金额。
- 批量收款部分失败时结果可追踪。
- readonly 角色不能调用写接口。
- 业主端不能越权查看其他业主账单。
- 打包资源清单包含新增模板、静态文件、文档。

### 10.2 手工桌面验收

macOS：

```text
build_macos_app.command
open dist/物业管理收费系统.app
```

Windows：

```text
build_windows_exe.bat
dist\PropertyFeeSystem\PropertyFeeSystem.exe
```

验收页面：

- 登录页。
- 收费工作台。
- 房间管理。
- 业主管理。
- 账单管理。
- 缴费记录。
- 数据备份。

### 10.3 安全验收

- 不硬编码密钥。
- 不提交 `.env`。
- 日志不记录身份证、完整手机号、支付密钥、支付回调原始敏感字段。
- 默认只绑定 `127.0.0.1`。
- 写接口必须鉴权。
- 删除、恢复、schema 变更、多项目迁移必须单独确认。

## 11. 风险与处理

| 风险 | 影响 | 处理 |
|---|---|---|
| 服务层抽取时改变现有页面行为 | 影响桌面用户 | 先写服务层测试，再改页面调用，保留回归测试 |
| API 过早公开 | 安全和兼容压力 | 先内部使用，版本稳定后再开放 |
| 支付回调重复 | 重复入账 | 使用幂等键和订单状态机 |
| 多项目直接改表 | 数据迁移风险高 | 单独设计 schema 和迁移脚本，先完整备份 |
| Windows/macOS 打包漏资源 | 普通用户启动失败 | 每次新增资源同步检查 spec，并做桌面验收 |
| 敏感信息泄露 | 合规和信任风险 | 日志脱敏，API 字段最小化 |

## 12. 下一步实施建议

下一步先做“阶段 1：接口抽取准备”。实施顺序：

1. 为账单、收款、业主、房间分别补服务层测试。
2. 抽出只读查询服务，降低风险。
3. 抽出写操作服务，保留备份、审计、权限校验。
4. 让现有页面路由调用服务层。
5. 运行完整测试和桌面启动验证。
6. 再进入 `/api/v1` JSON 接口设计。
