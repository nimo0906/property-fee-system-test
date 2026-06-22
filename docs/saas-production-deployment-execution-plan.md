# SaaS 云端系统生产部署执行清单

本文用于把当前已经完成的 SaaS 云端后台从代码验收推进到真实服务器部署。当前阶段目标是完成员工后台云端商业版上线试点，不包含业主端 H5、微信/支付宝真实支付、电子票据平台和独立授权云服务后台。

## 1. 当前状态结论

- 代码模块：已完成并通过本地 SaaS 主测试和模块门禁。
- 部署资产：Docker Compose、Nginx、systemd、logrotate、备份恢复脚本、预检脚本已具备。
- 当前阻塞：真实生产服务器尚未配置 `.env`，`APP_SECRET_KEY`、`POSTGRES_PASSWORD` 等生产密钥不能在仓库内提交。
- 下一步重点：代码冻结、服务器部署、生产环境变量配置、HTTPS、生产验收、样例客户试点。

## 2. 部署前代码冻结

在本地执行：

```bash
git status
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest tests/test_saas_*.py tests/test_cloud_migration.py -q
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_preflight_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_acceptance_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_production_precheck.py
```

通过后提交并推送当前分支。真实生产 `.env` 不提交。

## 3. 服务器准备

推荐配置：

- Ubuntu 22.04 或 24.04。
- 2 核 CPU、4GB 内存、80GB SSD 起步。
- 开放 80、443 端口。
- 域名解析到服务器公网 IP。

安装基础组件：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx git
sudo systemctl enable --now docker
```

## 4. 项目部署目录

建议代码目录：

```bash
/opt/property-saas
```

建议数据目录：

```bash
sudo mkdir -p /var/lib/property-saas/tenants
sudo mkdir -p /var/lib/property-saas/system
sudo mkdir -p /var/backups/property-saas
sudo mkdir -p /var/log/property-saas
```

目录含义：

- `/var/lib/property-saas/tenants`：客户上传文件和租户业务文件。
- `/var/lib/property-saas/system`：系统自身运行文件。
- `/var/backups/property-saas`：备份文件。
- `/var/log/property-saas`：运行日志。

## 5. 生产环境变量

在服务器上复制环境文件：

```bash
cd /opt/property-saas
cp .env.example .env
```

必须配置真实值：

```env
APP_SECRET_KEY=replace-with-random-production-secret
POSTGRES_PASSWORD=replace-with-strong-postgres-password
DATABASE_URL=postgresql://property_user:replace-with-strong-postgres-password@postgres:5432/property_saas
SAAS_STORAGE_ROOT=/var/lib/property-saas
SAAS_BACKUP_ROOT=/var/backups/property-saas
```

要求：

- `.env` 只能存在服务器本地。
- 不提交 `.env`。
- 不截图、不转发、不写入日志。
- `APP_SECRET_KEY` 和数据库密码必须使用随机强密码。

## 6. 启动服务

在服务器执行：

```bash
cd /opt/property-saas
docker compose up -d --build
docker compose ps
curl -sS http://127.0.0.1:8000/health
```

预期：

- PostgreSQL healthy。
- app healthy。
- `/health` 返回健康状态。

## 7. Nginx 和 HTTPS

使用现有 Nginx 配置作为基础：

```bash
sudo cp deploy/nginx/property-saas.conf /etc/nginx/sites-available/property-saas
sudo ln -s /etc/nginx/sites-available/property-saas /etc/nginx/sites-enabled/property-saas
sudo nginx -t
sudo systemctl reload nginx
```

签发 HTTPS 证书：

```bash
sudo certbot --nginx -d your-domain.example.com
```

上线前必须确认：

- HTTP 自动跳转 HTTPS。
- 后端 app 端口只本机访问。
- 管理后台不暴露真实密钥。

## 8. 生产预检和验收

服务器上执行：

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_env_file_check.py --env-file .env
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_runtime_check.py
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_acceptance_gate.py
```

业务验收：

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_demo_tenant_drill.py
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_commercial_delivery_drill.py
```

验收路径：

1. 平台管理员登录。
2. 创建样例租户。
3. 创建项目。
4. 导入或录入收费对象。
5. 配置收费项目。
6. 生成账单。
7. 审核账单。
8. 登记收款。
9. 查看报表和欠费。
10. 导出账单或收款记录。
11. 查看审计日志。
12. 创建备份并完成恢复演练记录。

## 9. 试点上线安排

建议分三天推进：

### 第一天：服务器部署

- 完成代码拉取和 `.env` 配置。
- 启动 Docker 服务。
- 配置 Nginx 和 HTTPS。
- 跑生产预检脚本。

### 第二天：样例客户验收

- 创建样例租户。
- 使用脱敏数据完成完整业务闭环。
- 导出验收结果。
- 检查审计和备份恢复记录。

### 第三天：真实客户小范围试点

- 只选一个客户或一个项目。
- 先导入少量真实数据。
- 由员工按真实流程完成出账、审核、收款、报表。
- 记录问题，不在试点当天继续追加新功能。

## 10. 不在本次上线范围

以下内容后置，避免影响员工后台稳定性：

- 业主端 H5。
- 微信/支付宝真实支付。
- 电子票据平台对接。
- 独立授权云服务后台。
- 大规模多客户同时上线。

## 11. 上线完成标准

满足以下条件后，才认为生产部署完成：

- 生产 `.env` 检查通过。
- Docker 服务健康。
- HTTPS 可访问。
- 生产验收 gate 通过。
- 样例客户 drill 通过。
- 商业交付 drill 通过。
- 至少完成一次备份和恢复演练记录。
- 试点客户业务人员确认核心流程可用。
