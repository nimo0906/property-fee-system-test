# SaaS 商业版实机部署演练验收清单

本文用于正式商业版交付前，在通用 Linux/VPS、腾讯云 CVM、阿里云 ECS 上做接近生产的实机部署演练。演练目标不是替代真实客户上线，而是在交付前确认部署、登录、租户隔离、业务闭环、授权绑定、备份恢复和证据留存可以完整跑通。失败即停止交付，修复后重新演练。

## 1. 适用范围

- 通用 Linux/VPS：Ubuntu LTS 或 Debian Stable。
- 腾讯云 CVM：安全组、数据盘、HTTPS 证书按腾讯云环境验收。
- 阿里云 ECS：安全组、数据盘、HTTPS 证书按阿里云环境验收。
- 当前只验收员工后台云端商业版。
- 不包含业主端 H5、微信/支付宝真实支付。

## 2. SSH 登录与基础环境

实施人员必须确认：

- 只允许受控 SSH 来源访问服务器。
- 应用端口不对公网开放，只由 Nginx HTTPS 反向代理访问。
- 数据目录、系统目录、备份目录、日志目录分开。
- Docker、Docker Compose Plugin、Nginx、systemd、logrotate 已安装。
- 生产 `.env` 由 `.env.example` 生成，不提交仓库，不写入截图、工单或日志。

## 3. Docker Compose 启动

执行前先通过：

```bash
python3 scripts/saas_env_security_check.py
python3 scripts/saas_preflight_check.py
```

启动服务：

```bash
docker compose up -d
```

验收点：

- PostgreSQL volume 正常挂载。
- app 只监听本机地址。
- 健康检查通过。
- 重启策略生效。

## 4. Nginx HTTPS 反向代理

- 使用 `deploy/nginx/property-saas.conf`。
- 生产必须通过 Nginx HTTPS 反向代理或上游负载均衡访问。
- HTTP 只允许跳转 HTTPS。
- 登录页、后台页面、导入导出路径不得通过明文 HTTP 直接承载。

## 5. systemd 托管与 logrotate 轮转

- 使用 `deploy/systemd/property-saas.service` 做 systemd 托管。
- 演练 `start`、`stop`、`restart`、`status`。
- 使用 `deploy/logrotate/property-saas` 做 logrotate 轮转。
- 日志不得出现生产密钥、数据库密码、客户上传文件明细或内部数据库连接信息。

## 6. 登录与账号边界

演练至少覆盖：

- 平台管理员登录：检查部署清单、商业验收总览、授权状态运维。
- 租户管理员登录：只能管理本租户员工账号、收费对象、账单和收款。
- 非管理员账号：不能执行用户管理、备份恢复、授权绑定等高风险操作。

## 7. 新租户空库业务闭环

每次实机演练必须使用一个新租户，从空库开始跑通：

```text
创建项目
→ 录入收费对象
→ 配置收费项目
→ 生成账单
→ 登记收款
→ 查看欠费/实收报表
→ 导出账单或收款记录
```

验收点：

- 金额、账期、服务期显示一致。
- 部分收款后欠费正确。
- 重复提交不能重复入账。
- 导出文件不包含内部字段。

## 8. 租户隔离验收

- A 公司不能读取 B 公司收费对象、账单、收款、报表、导入文件和备份记录。
- 跨租户管理动作必须由平台管理员执行并保留审计。
- 业务页面不得展示内部租户字段或项目字段。
- 执行并留存：

```bash
python3 scripts/saas_isolation_evidence.py
```

输出证据：`release/saas-isolation-evidence.md`。

## 9. 客户上传数据与系统自身数据隔离

- 客户上传数据只放入客户数据目录。
- 系统自身配置、授权绑定和运维文件放入系统目录。
- 授权绑定文件固定为：

```text
system/license_bindings/tenant_license_bindings.json
```

不得把授权绑定写入客户上传数据目录，不得写入 SaaS 业务表。

## 10. 授权绑定恢复

服务器迁移、容器重建、备份恢复后必须检查授权绑定恢复：

```bash
python3 scripts/saas_license_tenant_binding_check.py
python3 scripts/saas_license_binding_persistence_check.py
python3 scripts/saas_license_binding_backup_check.py
python3 scripts/saas_license_binding_runbook_check.py
```

验收点：

- 授权客户编号仍可读取。
- 授权状态、席位数量、到期时间显示正确。
- 绑定变更有 `license.tenant_bind` 审计。

## 11. 备份恢复演练

执行：

```bash
bash scripts/saas_backup.sh
bash scripts/saas_restore.sh --verify-metadata /path/to/backup
```

恢复后核对：

- 账单、收款、欠费金额一致。
- 客户上传文件恢复范围一致。
- 系统文件恢复范围一致。
- 授权绑定恢复一致。
- 审计链路可追踪。

## 12. 总门禁与证据留存

实机演练最后执行：

```bash
python3 scripts/saas_release_gate.py
python3 scripts/saas_release_evidence.py
```

必须留存：

- `release/saas-release-evidence.md`
- `release/saas-isolation-evidence.md`
- 部署时间、服务器类型、演练人员、演练租户名称。
- 备份编号、恢复校验结果、异常处理记录。

## 13. 失败处理

以下任一情况出现，失败即停止交付：

- 租户隔离失败。
- 金额、账期、服务期核对异常。
- 客户上传数据与系统自身数据隔离失败。
- 授权绑定恢复失败。
- 备份恢复校验失败。
- 页面、日志、导出文件泄露密钥、系统路径或内部字段。
