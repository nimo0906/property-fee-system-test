# SaaS 云端商业版实施人员一页式上线操作指引

本文给实施人员现场使用，按执行顺序逐项完成。上线目标为通用 Linux/VPS、腾讯云或阿里云的员工后台商业版；不包含业主端 H5、微信/支付宝真实支付。

## 执行顺序

### 1. 准备服务器

- 准备 Linux/VPS、腾讯云 CVM 或阿里云 ECS。
- 只开放 80/443 和必要 SSH 来源。
- 安装 Docker、Docker Compose、Nginx、systemd、logrotate。
- 确认客户上传数据与系统自身数据隔离、租户数据隔离的目录已规划。

### 2. 配置环境变量

- 从 `.env.example` 复制生成生产 `.env`。
- 生成强数据库密码和应用密钥。
- 不提交真实 .env，不把真实值写入截图、文档、工单或日志。

### 3. 启动服务

```bash
python3 scripts/saas_preflight_check.py
docker compose up -d
```

- 确认 app 仅本机端口访问。
- 配置 `deploy/nginx/property-saas.conf` 进行 HTTPS 反代。
- 配置 `deploy/systemd/property-saas.service` 和 `deploy/logrotate/property-saas`。

### 4. 运行上线门禁

```bash
python3 scripts/saas_release_gate.py
```

- 任何 FAIL 都不允许上线。
- WARN 必须记录处理方式，例如 HTTPS 在上游负载均衡终止。

### 5. 执行业务演示

```bash
python3 scripts/saas_commercial_delivery_drill.py
```

- 确认新租户从空库开始能完成项目、收费对象、收费项目、出账、审核、收款、报表、导出、备份恢复演练。

### 6. 执行备份恢复演练

```bash
bash scripts/saas_backup.sh
bash scripts/saas_restore.sh --verify-metadata /path/to/backup
```

- 核对 metadata、checksum、账单、收款、欠费、报表。
- 备份文件不得混入应用代码目录。

### 7. 核对租户隔离

- 核对 `release/saas-isolation-evidence.md`。
- A 公司不能读取 B 公司收费对象、账单、收款、报表、审计、备份记录。
- 客户上传数据与系统自身数据隔离：客户文件、系统文件、备份、日志分目录保存。

### 8. 完成客户签收

- 使用 `docs/saas-customer-acceptance-signoff.md` 完成人工验收。
- 确认部署完成、商业演示通过、备份恢复通过、租户隔离通过、账号权限确认、数据不混用确认。

### 9. 留存上线报告

- 留存 `release/saas-commercial-launch-report.pdf`。
- 留存 `release/saas-commercial-launch-report.docx`。
- 留存 `release/saas-release-evidence.md`。

### 10. 回退条件

出现以下情况不得上线，必须回退或暂停：

- 上线门禁失败。
- 租户数据隔离失败。
- 客户上传数据与系统自身数据隔离失败。
- 金额、账期、收款、欠费核对异常。
- 备份恢复演练失败。
- 审计日志缺失。
