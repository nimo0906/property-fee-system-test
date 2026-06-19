#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate sanitized production acceptance result archive."""

import argparse
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'release/saas-production-acceptance-result.md'
CHECKS = [
    'scripts/saas_production_env_file_check.py',
    'scripts/saas_production_precheck.py',
    'scripts/saas_production_runtime_check.py',
    'scripts/saas_production_first_tenant_smoke.py',
    'scripts/saas_isolation_evidence.py',
    'scripts/saas_release_evidence.py',
]
FORBIDDEN = ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo', 'tenant_id', 'project_id']


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def build_report(operator, domain):
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    rows = '\n'.join(f'| {item} | PASS/FAIL 手填 | 备注手填 |' for item in CHECKS)
    return f'''# SaaS 生产上线验收结果留档

执行时间：{now}
执行人：{operator}
服务器域名：{domain}

## 检查项结果

| 检查项 | 结果 | 备注 |
| --- | --- | --- |
{rows}

## 首租户业务冒烟结果

- 登录：PASS/FAIL 手填
- 收费对象：PASS/FAIL 手填
- 收费项目：PASS/FAIL 手填
- 出账：PASS/FAIL 手填
- 收款：PASS/FAIL 手填
- 报表：PASS/FAIL 手填
- 导出：PASS/FAIL 手填

## 租户隔离结果

- A 租户不能读取 B 租户收费对象、账单、收款和报表：PASS/FAIL 手填
- 客户上传数据与系统自身数据隔离：PASS/FAIL 手填

## 备份/证据文件位置

- 租户隔离证据：release/saas-isolation-evidence.md
- 上线证据报告：release/saas-release-evidence.md
- 本验收留档：release/saas-production-acceptance-result.md

## 签收

客户签收人：________________
实施人员签字：________________
签收日期：________________

## 安全说明

本留档不包含生产密钥、数据库密码、客户真实数据、本机绝对路径或内部租户字段。
'''


def main():
    parser = argparse.ArgumentParser(description='Generate SaaS production acceptance result archive.')
    parser.add_argument('--operator', default='实施人员手填')
    parser.add_argument('--domain', default='服务器域名手填')
    args = parser.parse_args()
    text = build_report(args.operator, args.domain)
    for item in FORBIDDEN:
        require(item not in text, f'forbidden acceptance result content: {item}')
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding='utf-8')
    print(f'wrote {REPORT.relative_to(ROOT)}')
    print('saas_production_acceptance_result: PASS')


if __name__ == '__main__':
    main()
