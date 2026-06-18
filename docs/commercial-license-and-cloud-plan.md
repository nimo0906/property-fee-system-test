# 正式商业版授权与云端部署方案

## 1. 已确认商业规则

| 项目 | 规则 |
|---|---|
| 授权方式 | 按年授权 |
| 默认设备数 | 3 台 |
| 离线宽限期 | 7 天 |
| 到期后 | 不能进入系统 |
| 本地数据 | 授权只控制进入系统，不删除客户本地数据库 |

## 2. 当前桌面版落地边界

- 授权文件放在本机数据目录：`license/license.json`。
- 系统启动和登录后访问业务页时读取授权状态。
- 授权已过期或授权文件异常时，只允许进入登录、授权状态和商业授权说明页。
- 首次使用配置写入本机数据目录：`config/first_run.json`。
- 初始化配置包含公司名称、项目名称、默认收费周期、默认物业费单价、商业收费、水电抄表和车位开关。
- 不把真实授权码、云端密钥、`.env` 或客户数据库提交到仓库。

## 3. 授权服务器后续接口草案

### 3.1 激活设备

`POST /api/license/activate`

请求字段：

- `license_key`
- `device_fingerprint`
- `product_code`
- `app_version`

响应字段：

- `status`
- `customer_name`
- `edition`
- `license_model=annual`
- `device_limit=3`
- `offline_grace_days=7`
- `expires_at`
- `refresh_token`
- `signature`

### 3.2 刷新授权

`POST /api/license/refresh`

请求字段：

- `license_key`
- `device_fingerprint`
- `refresh_token`
- `last_seen_at`

响应字段同激活接口。客户端刷新成功后更新本地 `license.json`。

### 3.3 解绑设备

`POST /api/license/devices/{device_id}/deactivate`

只允许授权后台管理员操作，必须记录操作日志。

## 4. 云端部署分阶段

### A 阶段：授权云服务

- 单独部署授权服务，不迁移客户业务数据。
- 只管理客户、订单、授权、设备、续费和审计。
- 桌面端仍用 SQLite，本地业务不依赖公网在线。

### B 阶段：员工后台云端化预研

- PostgreSQL 多租户 schema。
- 每张业务表增加租户边界设计，但正式改 schema 前必须单独确认。
- 做 SQLite 到 PostgreSQL 的金额、账期、收款、欠费一致性校验。

### C 阶段：正式 SaaS

- HTTPS 域名、反向代理、备份恢复、监控告警。
- 租户用户、角色权限、审计日志、对象存储。
- 业主端、在线支付、电子票据作为独立后续项目，不和授权服务混做。
