#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check backup coverage for production acceptance signoff history."""

import hashlib
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app

SCRIPT = 'scripts/saas_production_acceptance_signoff_backup_check.py'
SIGNOFF_HISTORY = 'production_acceptance_signoffs/history.json'
SIGNOFF_RESULT = 'saas-production-acceptance-result.md'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_metadata():
    backup = (ROOT / 'scripts/saas_backup.sh').read_text(encoding='utf-8')
    restore = (ROOT / 'scripts/saas_restore.sh').read_text(encoding='utf-8')
    for item in [SIGNOFF_HISTORY, SIGNOFF_RESULT, 'production_acceptance_signoffs', 'production_acceptance_result']:
        require(item in backup, f'missing backup metadata item: {item}')
    require('--system-files' in restore, 'restore script missing system-files scope')
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        backup_dir = base / 'backup'
        system_src = base / 'system-src'
        (system_src / 'production_acceptance_signoffs').mkdir(parents=True)
        (system_src / 'production_acceptance_signoffs' / 'history.json').write_text('{"records":[]}', encoding='utf-8')
        (system_src / SIGNOFF_RESULT).write_text('# result', encoding='utf-8')
        (backup_dir / 'system-files').mkdir(parents=True)
        archive = backup_dir / 'system-files' / 'system_files.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(system_src, arcname='.')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (backup_dir / 'checksums.sha256').write_text(f'{digest}  system-files/system_files.tar.gz\n', encoding='utf-8')
        (backup_dir / 'metadata.json').write_text(
            '{"kind":"property-saas-backup","system_files":"system-files/system_files.tar.gz",'
            f'"production_acceptance_signoffs":"{SIGNOFF_HISTORY}",'
            f'"production_acceptance_result":"{SIGNOFF_RESULT}","checksums":"checksums.sha256"}}',
            encoding='utf-8',
        )
        result = subprocess.run(['bash', str(ROOT / 'scripts/saas_restore.sh'), '--verify-metadata', str(backup_dir)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        require(result.returncode == 0, result.stdout)
    print('PASS production acceptance signoff backup metadata')


def check_pages():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '签收备份检查物业', 'project_name': '签收备份检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/backups')
    for item in ['生产验收签收历史', SIGNOFF_HISTORY, SIGNOFF_RESULT, '恢复演练选择 system-files']:
        require(item in page.text, f'missing backup page item: {item}')
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id']:
        require(hidden not in page.text, f'forbidden backup page content: {hidden}')
    print('PASS production acceptance signoff backup pages')


def check_registry():
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('PASS production acceptance signoff backup registry')


def main():
    check_metadata()
    check_pages()
    check_registry()
    print('saas_production_acceptance_signoff_backup_check: PASS')


if __name__ == '__main__':
    main()
