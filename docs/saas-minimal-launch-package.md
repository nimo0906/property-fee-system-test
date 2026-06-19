# SaaS 云端商业版最小上线包清单

本文定义第一版员工后台云端商业版的最小上线包。上线包用于通用 Linux/VPS、腾讯云、阿里云部署交付，不提交真实 .env，不包含业主端 H5、微信/支付宝真实支付、电子票据和独立授权云服务后台。

## 1. 上线包范围

- 员工后台：登录、租户、项目、角色权限、收费对象、收费项目、出账、审核、收款、报表、导入、导出、审计、备份和恢复演练。
- 部署目标：通用 Linux/VPS、腾讯云 CVM、阿里云 ECS。
- 数据边界：客户上传数据与系统自身数据隔离，租户数据隔离。

## 2. 部署配置

必须包含：

- `docker-compose.yml`
- `.env.example`
- `deploy/nginx/property-saas.conf`
- `deploy/systemd/property-saas.service`
- `deploy/logrotate/property-saas`

要求：生产环境从 `.env.example` 复制生成 `.env`，但不提交真实 .env，不在文档、页面、日志、导出中出现真实密钥值。

## 3. 运行服务

必须包含：

- PostgreSQL volume
- app service
- Nginx reverse proxy
- HTTPS 终止说明
- systemd 管理说明
- logrotate 日志轮转说明

## 4. 数据隔离

必须包含：

- 客户文件目录：`/var/lib/property-saas/tenants`
- 系统文件目录：`/var/lib/property-saas/system`
- 备份目录：`/var/backups/property-saas`
- 日志目录：`/var/log/property-saas`
- 租户数据隔离检查脚本和证据报告

## 5. 验收演示

必须包含：

- `docs/saas-cloud-deployment-drill.md`
- `docs/saas-commercial-delivery-drill.md`
- `scripts/saas_deployment_drill_check.py`
- `scripts/saas_commercial_delivery_drill.py`
- `scripts/saas_commercial_delivery_drill_check.py`
- `scripts/saas_demo_tenant_drill.py`
- `scripts/saas_commercial_readiness_check.py`

## 6. 运维备份

必须包含：

- `scripts/saas_backup.sh`
- `scripts/saas_restore.sh`
- `scripts/saas_ops_check.py`
- `docs/saas-cloud-ops-runbook.md`

备份和恢复演练必须保留 metadata、checksum、恢复范围、账单/收款/欠费/报表核对结果。

## 7. 上线证据

必须包含：

- `scripts/saas_release_gate.py`
- `scripts/saas_minimal_launch_package_check.py`
- `scripts/saas_isolation_evidence.py`
- `scripts/saas_release_evidence.py`
- `release/saas-isolation-evidence.md`
- `release/saas-release-evidence.md`

交付前必须先运行：

```bash
python3 scripts/saas_minimal_launch_package_check.py
python3 scripts/saas_release_gate.py
```
