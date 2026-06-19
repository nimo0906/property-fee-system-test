#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup and restore evidence covers production acceptance signoff history."""

import hashlib
import subprocess
import sys
import tarfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

SCRIPT = 'scripts/saas_production_acceptance_signoff_backup_check.py'
SIGNOFF_HISTORY = 'production_acceptance_signoffs/history.json'
SIGNOFF_RESULT = 'saas-production-acceptance-result.md'


def _login_client():
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': '生产签收备份物业',
        'project_name': '生产签收备份项目',
        'username': 'system_admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200
    return client


def _assert_safe(html):
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo']:
        assert hidden not in html


def test_backup_metadata_explicitly_lists_production_acceptance_signoff_history():
    backup = Path('scripts/saas_backup.sh').read_text(encoding='utf-8')
    restore = Path('scripts/saas_restore.sh').read_text(encoding='utf-8')
    assert SIGNOFF_HISTORY in backup
    assert SIGNOFF_RESULT in backup
    assert 'production_acceptance_signoffs' in backup
    assert 'production_acceptance_result' in backup
    assert '--system-files' in restore
    assert 'system-files/system_files.tar.gz' in backup


def test_restore_verify_metadata_accepts_backup_with_production_signoff_history(tmp_path):
    backup_dir = tmp_path / 'backup'
    system_src = tmp_path / 'system-src'
    history_dir = system_src / 'production_acceptance_signoffs'
    history_dir.mkdir(parents=True)
    (history_dir / 'history.json').write_text('{"records":[]}', encoding='utf-8')
    (system_src / 'saas-production-acceptance-result.md').write_text('# result', encoding='utf-8')
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
    result = subprocess.run(['bash', 'scripts/saas_restore.sh', '--verify-metadata', str(backup_dir)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
    assert result.returncode == 0, result.stdout


def test_backup_pages_explain_production_signoff_history_restore_scope():
    client = _login_client()
    page = client.get('/backoffice/backups')
    assert page.status_code == 200
    for text in ['生产验收签收历史', 'system-files', SIGNOFF_HISTORY, SIGNOFF_RESULT, '恢复演练选择 system-files']:
        assert text in page.text
    _assert_safe(page.text)

    created = client.post('/backoffice/backups/create', follow_redirects=False)
    assert created.status_code == 303
    backup_page = client.get('/backoffice/backups')
    backup_id = backup_page.text.split('/backoffice/backups/')[1].split('"')[0]
    drill = client.post('/backoffice/backups/restore-drills', data={'backup_id': backup_id, 'scope': 'system-files'}, follow_redirects=False)
    assert drill.status_code == 303
    detail = client.get(f'/backoffice/backups/{backup_id}')
    drill_list = client.get('/backoffice/backups')
    drill_href = drill_list.text.split('/backoffice/backups/restore-drills/')[1].split('"')[0]
    drill_page = client.get(f'/backoffice/backups/restore-drills/{drill_href}')
    for response in [detail, drill_page]:
        assert response.status_code == 200
        assert '生产验收签收历史' in response.text
        assert SIGNOFF_HISTORY in response.text
        assert SIGNOFF_RESULT in response.text
        _assert_safe(response.text)


def test_production_signoff_backup_check_script_is_in_release_assets():
    result = subprocess.run([sys.executable, SCRIPT], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    assert 'saas_production_acceptance_signoff_backup_check: PASS' in result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT in Path(path).read_text(encoding='utf-8')
