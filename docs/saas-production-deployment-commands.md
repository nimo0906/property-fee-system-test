# SaaS 生产部署实施命令清单

本文用于通用 Linux/VPS、腾讯云 CVM、阿里云 ECS 的正式商业版员工后台部署。目标是让实施人员从发布目录到 systemd 托管启动、健康检查、登录检查和上线门禁形成可复核闭环。

## 1. 进入发布目录

```bash
cd /opt/property-saas
```

发布目录应包含 `docker-compose.yml`、`.env.example`、`deploy/`、`scripts/`、`server/` 和 `docs/`。

## 2. 创建生产环境文件

```bash
cp .env.example .env
chmod 600 .env
```

编辑 `.env` 时只填写生产环境值，不把真实 `.env` 提交到仓库，不把密钥写入截图、日志、工单或交付文档。客户上传数据与系统自身数据隔离，目录保持：

- 客户上传数据：`/var/lib/property-saas/tenants`
- 系统自身数据：`/var/lib/property-saas/system`
- 备份目录：`/var/backups/property-saas`
- 日志目录：`/var/log/property-saas`

## 3. 启动容器服务

```bash
docker compose pull
docker compose up -d
```

若镜像由本机源码构建，先按项目交付说明构建，再执行 `docker compose up -d`。

## 4. 安装 systemd 服务

```bash
sudo install -m 0644 deploy/systemd/property-saas.service /etc/systemd/system/property-saas.service
sudo systemctl daemon-reload
sudo systemctl enable --now property-saas
sudo systemctl status property-saas --no-pager
```

`property-saas.service` 会加载 `/opt/property-saas/.env`，确保 VPS 重启后仍带上数据库、应用密钥和 SaaS 存储目录环境变量。

## 5. 安装 Nginx 与日志轮转

```bash
sudo install -m 0644 deploy/nginx/property-saas.conf /etc/nginx/conf.d/property-saas.conf
sudo nginx -t
sudo systemctl reload nginx
sudo install -m 0644 deploy/logrotate/property-saas /etc/logrotate.d/property-saas
sudo logrotate -d /etc/logrotate.d/property-saas
```

生产访问必须使用 HTTPS。HTTP 只允许跳转 HTTPS，不承载登录和业务页面。

## 6. 健康检查和登录检查

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS https://your-domain.example.com/login
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_runtime_check.py
```

第一条检查本机 app 健康状态；第二条检查公网域名、HTTPS、Nginx 反向代理和登录页可达性。

## 7. 上线门禁和证据

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_env_file_check.py --env-file .env
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_precheck.py
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_release_gate.py
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_runtime_check.py --dry-run
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_first_tenant_smoke.py --dry-run
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_isolation_evidence.py
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_release_evidence.py
```

任一命令失败即停止交付，修复后从失败步骤重新执行。上线证据报告必须脱敏，不包含生产密钥、客户资料、本机路径和内部租户字段。

## 8. 备份恢复演练

```bash
bash scripts/saas_backup.sh /var/backups/property-saas
bash scripts/saas_restore.sh --verify-metadata /var/backups/property-saas/<backup-dir>
```

恢复演练只验证 metadata 和 checksum 时不写入业务库。实际恢复必须显式选择 database、tenant-files 或 system-files 范围。

## 9. 失败处理

出现以下任一情况，失败即停止交付：

- `.env` 未创建或权限过宽。
- systemd 未加载生产环境文件。
- `/health` 不可达。
- `/login` 不可达或 HTTPS 未完成。
- 客户上传数据与系统自身数据隔离不符合约定。
- 上线门禁、隔离证据、备份恢复任一检查失败。

## 10. 首租户业务冒烟

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_first_tenant_smoke.py --base-url https://your-domain.example.com
```

该冒烟只使用测试租户和测试账期，覆盖登录、收费对象、收费项目、出账、收款、报表、导出、租户隔离，不导入真实客户数据。

## 11. 生产一键验收总入口

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_acceptance_gate.py --env-file .env --base-url https://your-domain.example.com
```

该入口串联 `.env` 现场校验、生产预检、运行状态、首租户业务冒烟、租户隔离证据和上线证据报告。失败即停止交付。

## 生产验收结果留档

一键验收完成后生成：`release/saas-production-acceptance-result.md`。该文件记录执行人、服务器域名、检查项 PASS/FAIL、首租户业务冒烟、租户隔离、备份/证据文件位置、客户签收人和实施人员签字，不包含生产密钥或客户真实数据。

可单独执行：

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_production_acceptance_result.py --operator "实施人员手填" --domain your-domain.example.com
```

## 12. 水电表抄表模块上线检查

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_module11_meter_reading_gate.py
```

上线后用测试租户登录 `/backoffice/meter-readings`，新建 `billing_mode=meter` 的水费或电费项目，录入一条已确认抄表，确认生成待审核账单；检查页面和日志不得展示 `.env`、数据库密码或生产密钥。


## 13. 商户合同、合同变更模块上线检查

```bash
PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_module13_merchant_contract_gate.py
```

上线后用测试租户登录 `/backoffice/merchant-contracts`，选择商户铺位新增一份合同，录入一条生效日调价变更，再生成该生效日之后账期的合同账单；检查金额口径为 `合同面积 × 租金单价 + 合同面积 × 物业费单价`，状态为 `pending_review`，页面和日志不得展示 `.env`、数据库密码或生产密钥。
