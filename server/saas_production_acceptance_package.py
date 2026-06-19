#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build sanitized production acceptance evidence package."""

import io
import json
import zipfile
from pathlib import Path

FORBIDDEN = ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '生产环境文件', '.env']
PACKAGE_FILES = [
    ('release/saas-production-acceptance-result.md', 'saas-production-acceptance-result.md'),
    ('release/saas-release-evidence.md', 'saas-release-evidence.md'),
    ('release/saas-isolation-evidence.md', 'saas-isolation-evidence.md'),
    ('release/production_acceptance_signoffs/history.json', 'production_acceptance_signoffs/history.json'),
]


def safe_text(value):
    text = str(value or '')
    for forbidden in FORBIDDEN:
        text = text.replace(forbidden, '[redacted]')
    return text


def package_precheck(root):
    root = Path(root)
    rows = []
    for rel, name in PACKAGE_FILES:
        path = root / rel
        exists = path.exists()
        rows.append({
            'package_name': name,
            'source': rel,
            'status': '存在' if exists else '缺失',
            'included': '是' if exists else '占位进入总包',
        })
    rows.append({
        'package_name': 'backup-coverage.md',
        'source': '自动生成',
        'status': '自动生成',
        'included': '是',
    })
    return rows


def build_evidence_package(root):
    root = Path(root)
    buffer = io.BytesIO()
    files = []
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        for rel, name in PACKAGE_FILES:
            path = root / rel
            text = path.read_text(encoding='utf-8') if path.exists() else '# 文件未生成\n'
            package.writestr(name, safe_text(text))
            files.append(name)
        coverage = _backup_coverage()
        package.writestr('backup-coverage.md', safe_text(coverage))
        files.append('backup-coverage.md')
        manifest = {
            'kind': 'property-saas-production-acceptance-evidence',
            'contains_customer_uploads': False,
            'contains_secrets': False,
            'files': files,
        }
        package.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return buffer.getvalue()


def _backup_coverage():
    return '''# 生产验收证据包备份覆盖说明

- system-files 覆盖生产验收签收历史：production_acceptance_signoffs/history.json
- system-files 覆盖当前生产验收留档：saas-production-acceptance-result.md
- 证据包包含上线证据、租户隔离证据、生产验收留档和签收历史。
- 证据包不包含 生产环境文件、生产密钥、客户上传文件内容或真实服务器绝对路径。
- 恢复演练选择 system-files 后，应核对生产验收签收历史仍可查看和下载。
'''
