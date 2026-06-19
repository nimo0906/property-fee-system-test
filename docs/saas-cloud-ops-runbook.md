# SaaS 云端商业版运维手册

本文面向第一版员工后台 SaaS 云端商业版，部署目标是通用 Linux/VPS。桌面版继续独立交付；本手册只描述云端后台的部署、检查、备份、恢复演练、日志轮转和管理员账号运维。

## 1. 部署范围

- 部署形态：FastAPI app + PostgreSQL + Nginx reverse proxy + systemd 管理。
- 启动命令：`docker compose up -d`。
- Nginx 配置：`deploy/nginx/property-saas.conf`。
- systemd 配置：`deploy/systemd/property-saas.service`。
- 日志轮转配置：`deploy/logrotate/property-saas`。
- 环境变量模板：`.env.example`，真实 `.env` 不提交。

## 2. 上线前检查命令

在服务器项目目录执行：

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_preflight_check.py
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_acceptance_check.py
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_ops_check.py
```

预期：三条命令均返回 PASS。`scripts/saas_preflight_check.py` 如提示 HTTPS warning，表示生产前必须在 Nginx 或上游负载均衡终止 HTTPS。

## 3. 目录隔离

- 客户上传数据：`/var/lib/property-saas/tenants`
- 系统自身数据：`/var/lib/property-saas/system`
- 备份目录：`/var/backups/property-saas`
- 日志目录：`/var/log/property-saas`

客户上传数据与系统自身数据隔离，不能把客户 Excel、附件、导入原始材料写入系统目录；系统配置、运行日志、备份元数据也不能混到客户业务目录。

## 4. 日志轮转安装

安装配置示例：

```bash
sudo cp deploy/logrotate/property-saas /etc/logrotate.d/property-saas
sudo logrotate -d /etc/logrotate.d/property-saas
```

配置覆盖 `/var/log/property-saas/*.log`，保留 14 轮，压缩旧日志，使用 `copytruncate` 避免应用进程未重启时日志句柄丢失。

## 5. 备份与恢复演练

创建备份：

```bash
bash scripts/saas_backup.sh /var/backups/property-saas
```

验证备份元数据和校验和：

```bash
bash scripts/saas_restore.sh --verify-metadata /var/backups/property-saas/<backup-dir>
```

恢复必须显式选择单一范围，不允许隐式全量恢复：

```bash
bash scripts/saas_restore.sh --database /var/backups/property-saas/<backup-dir>/db/property_saas.sql
bash scripts/saas_restore.sh --tenant-files /var/backups/property-saas/<backup-dir>/tenant-files/customer_files.tar.gz
bash scripts/saas_restore.sh --system-files /var/backups/property-saas/<backup-dir>/system-files/system_files.tar.gz
```

恢复演练证据至少保留：备份目录名、`metadata.json` 校验结果、恢复范围、演练时间、演练人、演练后登录截图、账单/收款/报表核对结果。

## 6. 管理员重置密码流程

- 租户管理员只能重置本租户员工账号。
- 平台管理员可跨租户重置账号但必须写入目标租户审计。
- 管理员不能通过账号管理页重置自己的密码；本人改密走个人改密入口。
- 临时密码必须满足密码策略，且不能与目标账号当前密码相同。
- 密码不展示在页面、日志或审计明细；审计只记录操作人、目标账号、目标租户、是否已变更。
- 重置后员工必须使用新临时密码登录，并在进入业务页面前完成个人改密。

## 7. 正式上线顺序

1. 准备 `.env`，不得提交真实密钥。
2. 执行 `scripts/saas_preflight_check.py`。
3. 执行 `scripts/saas_ops_check.py`。
4. 执行 `docker compose up -d`。
5. 确认 app 仅监听 `127.0.0.1:8000`。
6. 配置 `deploy/nginx/property-saas.conf` 并完成 HTTPS。
7. 安装 `deploy/systemd/property-saas.service`。
8. 安装 `deploy/logrotate/property-saas`。
9. 执行 `scripts/saas_backup.sh` 和 `scripts/saas_restore.sh --verify-metadata`。
10. 执行 `scripts/saas_acceptance_check.py`。
11. 登录 `/backoffice/acceptance`，检查商业后台闭环状态。

## 8. 禁止事项

- 不在日志、页面、文档中写真实 `POSTGRES_PASSWORD` 或 `APP_SECRET_KEY` 值。
- 不提交真实 `.env`。
- 不把客户上传文件与系统配置、日志、备份密钥混放。
- 不跳过备份恢复演练直接开放生产访问。

## 商业上线总门禁

生产交付前必须执行商业上线总门禁：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_release_gate.py
```

该门禁会顺序执行：

- `scripts/saas_preflight_check.py`
- `scripts/saas_ops_check.py`
- `scripts/saas_acceptance_check.py`
- `scripts/saas_phase1_closure_check.py`
- `scripts/saas_demo_tenant_drill.py`

任一子检查失败都不能进入正式商业云端部署。
