# SaaS 云端后台实施记录

## 当前阶段

当前主线是正式商业版 SaaS 云端后台，保持与桌面 SQLite 交付并行，不破坏现有桌面版。

已落地能力：

- FastAPI 后台 API：登录、租户、角色权限、用户管理和 session cookie。
- SQLAlchemy 持久化 repository，并通过 Alembic 管理正式 PostgreSQL schema。
- 登录、租户、角色权限：系统管理员、财务、收费员、前台、管理层只读角色分工。
- 收费对象、收费项目、出账、审核、收款：新账单默认 pending_review，审核后才能收款。
- 导入预览、审核、确认：预览不落库，错误行不污染正确行，确认后只写有效行。
- 收据、导出、对账报表：收款生成 receipt_number，支持账单/收款 CSV 导出和账期汇总。
- 列表筛选、搜索、分页：账单和收款按账期、状态、房号、账单号、收据号查询。
- 备份记录、恢复演练、审计日志：高风险运维操作可追踪。
- 管理员密码重置：租户管理员只能重置本租户员工；平台管理员可跨租户重置全部账号，但跨租户动作写入目标租户审计并标记 `scope=platform`；密码只保存 PBKDF2 哈希，审计日志只记录目标账号和角色，不记录临时密码明文。
- 员工账号生命周期：管理员只能查看、停用、启用本租户员工账号；离职停用会写入 `user.disable` 审计并清理该账号当前会话。
- 账号管理页面：正式商业后台提供账号列表、搜索、角色筛选、状态筛选、分页、停用/启用、重置密码界面；租户管理员只看本租户账号，平台管理员可看全部账号，但页面与动作都保留租户隔离和审计。
- 账号登录闭环：管理员重置密码后，员工必须用新密码重新登录；首次登录后必须先完成改密才能进入业务页面，改密操作会写入 `user.password_change` 审计，不记录明文密码。
- 收费项目页面：`/backoffice/fee-types` 支持查看和新增收费项目/单价；租户管理员、财务、平台管理员可见，收费员只读，所有读写按 tenant/project scope 隔离。
- 账单生成与审核页面：`/backoffice/bills` 支持按收费对象和收费项目生成账单、按账期/状态查询列表、待审核账单页面审核通过；财务和管理员可出账/审核，收费员只读，所有账单按 tenant/project scope 隔离。
- 收款登记页面：`/backoffice/payments` 支持登记已审核账单收款和查看收款列表；财务、收费员、管理员可收款，管理层只读，收款和账单状态按 tenant/project scope 隔离。
- 对账报表页面：`/backoffice/reports` 支持按账期查看账单数量、应收、实收和欠费；管理层只读可看，所有报表按 tenant/project scope 隔离。
- 数据导入页面：`/backoffice/imports` 支持收费对象 CSV 文本预览、确认导入；预览不写库，确认只写有效行，错误行不污染正式数据，导入记录按 tenant/project scope 校验。
- 审计日志页面：`/backoffice/audit-logs` 支持只读查看账号、导入、出账、审核、收款等关键操作；不展示密码明文，日志按 tenant/project scope 隔离。
- 备份恢复页面：`/backoffice/backups` 支持管理员创建备份记录、提交恢复演练，非管理员只读查看；备份和演练审计按 tenant/project scope 隔离。
- 商业验收页面：`/backoffice/acceptance` 汇总站内验收入口和自动验收脚本，覆盖创建项目、导入/录入收费对象、收费项目、出账、审核、收款、报表、审计、备份恢复和租户隔离。
- 云端上线清单页面：`/backoffice/deploy-checklist` 展示 VPS 部署资产、预检脚本、验收脚本、Docker Compose、Nginx、systemd、备份恢复脚本、目录隔离和 HTTPS 上线提醒；页面只读，不展示生产密钥或环境变量值。
- 租户管理员控制台：`/backoffice/tenant-admin` 提供本公司账号列表、停用/启用、重置密码入口，并强调客户上传数据与系统自身数据隔离。
- 平台客户开通页面：`/backoffice/tenant-onboarding` 仅平台管理员可用，用于创建新客户公司、默认项目和首个租户管理员；初始密码只保存哈希并标记首登强制改密，开通动作写入新租户审计。
- 租户状态管理：平台管理员可在 `/backoffice/tenant-projects` 停用/启用客户公司；停用租户员工登录和既有会话业务访问均返回 403，启用后恢复，状态变更写入目标租户审计。
- 租户项目管理页面：`/backoffice/tenant-projects` 提供项目列表与创建入口；租户管理员只能维护本公司项目，平台管理员可只读查看全局租户与项目，但不在此页创建项目。
- 项目切换：员工可通过 `POST /api/auth/switch-project` 或租户项目页面在本租户项目间切换；切换后收费对象、收费项目、账单、收款、报表都按当前项目读取，跨租户项目切换返回 403。
- 后台首页入口：`/backoffice` 展示当前租户、项目、角色和可见模块，账号管理、租户管理员控制台、租户项目管理、云端上线清单从首页可发现，非管理员只看到权限说明。
- 收费对象页面：`/backoffice/charge-targets` 支持查看和新增楼栋/区域、单元/分区、房号/铺位号，写入仍按 tenant/project scope 隔离。
- 多租户隔离：业务表、导入记录、审计日志、上传路径均带 tenant/project scope。
- 客户上传数据和系统自身数据隔离：tenants 与 system 目录分离，备份、日志、系统文件分层。
- 通用 Linux/VPS 部署资产：Docker Compose、Nginx、systemd、logrotate、备份和恢复脚本；Compose 服务包含重启策略、PostgreSQL 健康检查和 SaaS app `/health` 健康检查。
- 备份完整性：`scripts/saas_backup.sh` 生成 `checksums.sha256`，`scripts/saas_restore.sh --verify-metadata` 在恢复前校验备份产物未被篡改。
- 部署前预检：`scripts/saas_preflight_check.py` 校验部署资产、隔离目录合同、后端端口仅本机绑定、环境密钥占位安全，并提示 Nginx/上游负载均衡的 HTTPS 终止状态。

## 验收脚本

- `scripts/saas_acceptance_check.py` 用于分别从空内存租户和临时 SQLite 持久化库执行完整后台闭环：
  登录 → 创建员工 → 配置收费项目 → 导入收费对象 → 生成账单 → 审核账单 → 登记收款 → 查询报表 → 导出 → 备份记录 → 恢复演练 → 审计检查。
- 持久化验收会确认收费对象、收费项目、账单、收款、报表和审计日志均按 tenant/project scope 读写；客户上传数据继续使用 `tenants/{tenant_id}/projects/{project_id}/...`，系统自身数据使用 `system/...`，两类数据不混放。
- 建议每次云端后台关键改动后运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_preflight_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_acceptance_check.py
```

## 当前仍后置

- 业主端 H5 云端重做。
- 微信/支付宝真实支付。
- 电子票据平台对接。
- 授权云服务后台。

## 发布门禁

云端后台改动必须至少运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest tests/test_saas_*.py tests/test_cloud_migration.py -q
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_preflight_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_acceptance_check.py
```

涉及共用逻辑或桌面交付边界时继续运行桌面门禁：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server/*.py server.py desktop_app.py desktop_runtime.py scripts/*.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q
python3 scripts/desktop_release_check.py
python3 scripts/source_tree_check.py
```
