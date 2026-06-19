#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup evidence for first tenant acceptance records."""

import hashlib
import subprocess
import sys
import tarfile
from pathlib import Path


def test_backup_metadata_explicitly_lists_first_tenant_acceptance_records():
    backup = Path('scripts/saas_backup.sh').read_text(encoding='utf-8')
    restore = Path('scripts/saas_restore.sh').read_text(encoding='utf-8')
    expected = 'first_tenant_acceptance/records.json'
    assert expected in backup
    assert 'acceptance_records' in backup
    assert '--system-files' in restore
    assert 'system-files/system_files.tar.gz' in backup


def test_restore_verify_metadata_accepts_backup_with_acceptance_records(tmp_path):
    backup_dir = tmp_path / 'backup'
    system_src = tmp_path / 'system-src' / 'first_tenant_acceptance'
    system_src.mkdir(parents=True)
    (system_src / 'records.json').write_text('{"records":[]}', encoding='utf-8')
    (backup_dir / 'system-files').mkdir(parents=True)
    archive = backup_dir / 'system-files' / 'system_files.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(system_src.parent, arcname='.')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (backup_dir / 'checksums.sha256').write_text(f'{digest}  system-files/system_files.tar.gz\n', encoding='utf-8')
    (backup_dir / 'metadata.json').write_text(
        '{"kind":"property-saas-backup","system_files":"system-files/system_files.tar.gz",'
        '"acceptance_records":"first_tenant_acceptance/records.json","checksums":"checksums.sha256"}',
        encoding='utf-8',
    )
    result = subprocess.run(['bash', 'scripts/saas_restore.sh', '--verify-metadata', str(backup_dir)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
    assert result.returncode == 0, result.stdout


def test_acceptance_backup_evidence_check_script_is_in_release_assets():
    script = 'scripts/saas_first_tenant_acceptance_backup_evidence_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert script in Path(path).read_text(encoding='utf-8')
