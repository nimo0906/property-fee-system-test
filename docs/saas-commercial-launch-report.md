# SaaS 云端商业版上线总报告

## 1. 总体结论

SaaS 云端商业版员工后台主线已形成可部署、可演示、可验收、可签收的第一版商业交付闭环。当前版本面向通用 Linux/VPS、腾讯云、阿里云部署，覆盖登录、租户、权限、收费对象、收费项目、出账、审核、收款、报表、导入、导出、审计、备份和恢复演练。

本阶段不包含业主端 H5、微信/支付宝真实支付、电子票据平台、独立授权云服务后台。

## 2. 阶段完成状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| P0-1 业主与收费对象 | 已完成 | 业主档案、收费对象、导入映射、多租户隔离。 |
| P0-2 计费规则 | 已完成 | 面积计费、固定金额、独立单价、服务期折算。 |
| P0-3 批量出账 | 已完成 | 当前租户项目批量出账，重复账单跳过。 |
| P0-4 收款欠费 | 已完成 | 部分收款、已收、欠费、报表联动。 |
| P0-5 收据导出 | 已完成 | 账单/收款导出和收据详情含业务字段，不含内部字段。 |
| P0-6 导入复核 | 已完成 | 预览不写库、确认后写库、重复对象跳过。 |
| P0-7 高风险审计 | 已完成 | 风险分级、详情脱敏、按租户隔离查询。 |
| P0-8 备份恢复 | 已完成 | 备份记录、恢复演练记录、审计链路。 |
| P0-9 商业上线验收总览 | 已完成 | 后台验收页和商业 readiness 检查。 |
| P0-10 云端部署演练 | 已完成 | 通用 Linux/VPS、腾讯云、阿里云部署演练文档和检查脚本。 |
| P0-11 商业交付演示 | 已完成 | 新租户从空库开始完成项目、收费对象、收费项目、出账、审核、收款、报表、导出、备份恢复演练。 |
| P0-12 最小上线包 | 已完成 | 部署配置、验收演示、运维备份、上线证据清单。 |
| P0-13 客户交付签收 | 已完成 | 上线前人工验收和客户交付签收清单。 |

## 3. 验证命令

正式上线前执行：

```bash
python3 scripts/saas_minimal_launch_package_check.py
python3 scripts/saas_customer_acceptance_signoff_check.py
python3 scripts/saas_commercial_launch_report_check.py
python3 scripts/saas_release_gate.py
```

开发侧全量门禁：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest tests/test_saas_*.py tests/test_cloud_migration.py -q
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q
python3 scripts/desktop_release_check.py
python3 scripts/source_tree_check.py
```

## 4. 部署资产

| 类别 | 资产 |
| --- | --- |
| Compose | `docker-compose.yml` |
| 环境变量示例 | `.env.example` |
| Nginx | `deploy/nginx/property-saas.conf` |
| systemd | `deploy/systemd/property-saas.service` |
| logrotate | `deploy/logrotate/property-saas` |
| 运维手册 | `docs/saas-cloud-ops-runbook.md` |
| 部署演练 | `docs/saas-cloud-deployment-drill.md` |
| 最小上线包 | `docs/saas-minimal-launch-package.md` |

## 5. 演示路径

| 演示项 | 入口 |
| --- | --- |
| 商业交付演示脚本 | `scripts/saas_commercial_delivery_drill.py` |
| 商业交付演示检查 | `scripts/saas_commercial_delivery_drill_check.py` |
| 部署演练检查 | `scripts/saas_deployment_drill_check.py` |
| 最小上线包检查 | `scripts/saas_minimal_launch_package_check.py` |
| 后台商业验收页 | `/backoffice/acceptance` |
| 后台部署清单页 | `/backoffice/deploy-checklist` |

## 6. 签收路径

| 签收项 | 资产 |
| --- | --- |
| 客户交付签收清单 | `docs/saas-customer-acceptance-signoff.md` |
| 客户签收检查脚本 | `scripts/saas_customer_acceptance_signoff_check.py` |
| 上线证据报告 | `release/saas-release-evidence.md` |
| 租户隔离证据 | `release/saas-isolation-evidence.md` |

## 7. 数据和权限边界

- 租户数据隔离：不同公司之间收费对象、账单、收款、报表、审计、备份记录必须隔离。
- 客户上传数据与系统自身数据隔离：客户文件、系统文件、备份和日志分目录保存。
- 平台管理员可跨租户管理但必须审计。
- 租户管理员只能管理本租户员工账号。
- 财务、收费员、管理层按角色权限分离。

## 8. 上线证据

上线证据以 `scripts/saas_release_gate.py` 输出为准，并保留：

- `release/saas-release-evidence.md`
- `release/saas-isolation-evidence.md`
- `docs/saas-customer-acceptance-signoff.md`
- `docs/saas-commercial-launch-report.md`

## 9. 生产注意事项

- 不提交真实 .env。
- 不在页面、日志、导出、报告中记录真实密钥值。
- 正式生产必须通过 HTTPS 访问。
- 发布前必须完成备份和恢复演练。
- 出现租户越权、金额异常、导入污染、审计缺失时不得上线。
