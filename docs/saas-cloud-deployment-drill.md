# SaaS 云端商业版部署演练手册

本文用于第一版员工后台云端商业版上线前演练，覆盖通用 Linux/VPS、腾讯云、阿里云三类普通云主机。当前范围只包含员工后台、租户、权限、收费对象、收费项目、账单、收款、导入、报表、备份、恢复演练和审计；暂不包含业主端 H5、微信/支付宝真实支付。

## 1. 演练目标

- 验证同一套部署产物可运行在通用 Linux/VPS、腾讯云 CVM、阿里云 ECS。
- 验证客户上传数据与系统自身数据隔离，租户数据隔离，不把不同公司数据混在一起。
- 验证 `.env.example` 可转换为生产 `.env`，但不提交真实 .env。
- 验证 Docker Compose、Nginx HTTPS、systemd、logrotate、备份和恢复演练形成闭环。
- 验证商业上线门禁命令可在部署前稳定通过。

## 2. 服务器准备

### 通用 Linux/VPS

- 建议 Ubuntu LTS 或 Debian Stable。
- 开放 80/443，应用端口只允许本机访问。
- 安装 Docker、Docker Compose Plugin、Nginx、systemd、logrotate。

### 腾讯云

- 使用 CVM，安全组仅放行 80/443 和必要 SSH 来源。
- 数据盘单独挂载到 `/var/lib/property-saas`、`/var/backups/property-saas`、`/var/log/property-saas`。
- 证书可使用腾讯云 SSL 证书或 acme.sh。

### 阿里云

- 使用 ECS，安全组仅放行 80/443 和必要 SSH 来源。
- 数据盘同样按客户文件、系统文件、备份、日志分目录挂载。
- 证书可使用阿里云数字证书或 acme.sh。

## 3. 环境变量

1. 复制 `.env.example` 为生产 `.env`。
2. 按说明生成数据库密码、应用密钥和数据库连接参数。
3. 不提交真实 .env，不把真实值写入文档、日志、截图或工单。
4. 执行：

```bash
python3 scripts/saas_env_security_check.py
```

## 4. 数据与目录隔离

- 客户上传数据目录：`/var/lib/property-saas/tenants`
- 系统自身数据目录：`/var/lib/property-saas/system`
- 备份目录：`/var/backups/property-saas`
- 日志目录：`/var/log/property-saas`
- 每张业务表必须按租户过滤；跨租户管理操作必须写审计。
- 导入文件、收据导出、备份文件不得混入应用代码目录。

## 5. 启动演练

```bash
python3 scripts/saas_preflight_check.py
python3 scripts/saas_ops_check.py
docker compose up -d
```

启动后确认 app 只监听 `127.0.0.1:8000`，由 Nginx 对外提供 HTTPS。

## 6. Nginx 与 HTTPS

- 使用 `deploy/nginx/property-saas.conf` 作为反代模板。
- 生产必须启用 HTTPS；可以在 Nginx 或上游负载均衡终止 HTTPS。
- HTTP 仅用于跳转到 HTTPS，不直接承载登录和业务页面。

## 7. systemd 管理

- 使用 `deploy/systemd/property-saas.service` 管理服务生命周期。
- 演练 restart、stop、start、status。
- 服务失败后必须能通过日志定位，不输出敏感值。

## 8. 日志轮转

- 安装 `deploy/logrotate/property-saas`。
- 验证 `/var/log/property-saas/*.log` 会按策略轮转、压缩和保留。
- 登录、导入、出账、收款、备份、恢复演练、高风险操作必须保留审计。

## 9. 备份和恢复演练

```bash
bash scripts/saas_backup.sh
bash scripts/saas_restore.sh --verify-metadata /path/to/backup
```

恢复演练必须记录：

- 备份编号和时间。
- `metadata.json` 与 checksum 校验结果。
- 数据库恢复范围。
- 客户上传文件恢复范围。
- 系统文件恢复范围。
- 账单、收款、欠费、报表核对结果。

## 10. 商业验收命令

部署前按顺序执行：

```bash
python3 scripts/saas_deployment_drill_check.py
python3 scripts/saas_commercial_readiness_check.py
python3 scripts/saas_release_gate.py
```

若任一命令失败，不进入正式交付。

## 11. 回退与故障处理

- 新版本发布前先完成备份和恢复演练。
- 发布失败时先停止 app，保留 PostgreSQL volume，不删除客户数据。
- 需要回退时恢复上一版镜像、配置和数据库备份。
- 如果出现租户越权、金额异常、导入污染或审计缺失，立即停止交付并保留现场证据。

## 12. 不在本阶段处理

- 暂不包含业主端 H5、微信/支付宝真实支付。
- 暂不包含电子票据平台对接。
- 暂不包含独立授权云服务后台。
