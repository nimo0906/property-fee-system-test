# SaaS 生产部署一键自检说明

本文用于正式商业版在通用 Linux/VPS、腾讯云 CVM、阿里云 ECS 上交付前的服务器自检。自检脚本只读取部署资产、目录约定和配置文件，不写入客户业务数据，不输出生产密钥。

## 1. 使用方式

在实施人员本地或服务器发布目录执行 dry-run：

```bash
python3 scripts/saas_production_precheck.py --dry-run
```

在服务器上执行正式自检：

```bash
python3 scripts/saas_production_precheck.py
```

若任一检查失败即停止交付，修复后重新执行。

## 2. 检查范围

### 服务器环境

- Python 可运行。
- Docker Compose、Nginx、systemd、logrotate 有明确安装要求。
- 生产 `.env` 必须由 `.env.example` 生成，不提交真实 .env。

### 端口与反向代理

- app 只允许本机端口访问。
- 生产流量必须经过 Nginx HTTPS。
- HTTP 只用于跳转 HTTPS，不承载登录和业务页面。

### 存储目录

- 客户上传数据目录：`/var/lib/property-saas/tenants`
- 系统自身数据目录：`/var/lib/property-saas/system`
- 备份目录：`/var/backups/property-saas`
- 日志目录：`/var/log/property-saas`

客户上传数据目录与系统自身数据目录必须隔离，不得混放授权绑定、导入文件、导出文件和备份文件。

### Docker Compose

- 检查 `docker-compose.yml` 存在。
- 检查 PostgreSQL 和 app 健康检查。
- 检查 app 端口仅本机绑定。
- 检查服务重启策略。

### Nginx HTTPS

- 检查 `deploy/nginx/property-saas.conf` 存在。
- 检查 HTTPS 终止配置或提示必须在上游负载均衡终止 HTTPS。

### systemd

- 检查 `deploy/systemd/property-saas.service` 存在。
- 实施时必须演练 start、stop、restart、status。

### logrotate

- 检查 `deploy/logrotate/property-saas` 存在。
- 日志轮转不得输出生产密钥、数据库密码、客户上传文件明细。

### 备份恢复脚本

- 检查 `scripts/saas_backup.sh`。
- 检查 `scripts/saas_restore.sh`。
- 恢复时必须使用 metadata 和 checksum 校验。

### 授权绑定文件

- 检查授权绑定备份恢复资产。
- 授权绑定文件：`system/license_bindings/tenant_license_bindings.json`
- 授权绑定属于系统自身数据，不属于客户上传数据。

### 上线证据文件

- 检查 `release/saas-release-evidence.md`。
- 检查 `release/saas-isolation-evidence.md`。
- 检查 `scripts/saas_release_gate.py` 已包含生产自检。

## 3. 失败处理

出现以下任一情况，失败即停止交付：

- 端口公网暴露。
- 客户上传数据目录与系统自身数据目录混用。
- Docker Compose、Nginx、systemd、logrotate 任一关键资产缺失。
- 备份恢复脚本缺失。
- 授权绑定文件无法纳入系统侧备份恢复。
- 上线证据文件缺失。
- 页面、日志或输出泄露生产密钥、本机路径或内部字段。
