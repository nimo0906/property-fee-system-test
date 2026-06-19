#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check backup evidence covers first tenant acceptance records."""

from pathlib import Path
import hashlib
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_RECORDS = 'first_tenant_acceptance/records.json'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def verify_sample_metadata():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        backup_dir = root / 'backup'
        system_src = root / 'system-src' / 'first_tenant_acceptance'
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
            f'"acceptance_records":"{ACCEPTANCE_RECORDS}","checksums":"checksums.sha256"}}',
            encoding='utf-8',
        )
        result = subprocess.run(['bash', 'scripts/saas_restore.sh', '--verify-metadata', str(backup_dir)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        require(result.returncode == 0, result.stdout)


def main():
    backup = (ROOT / 'scripts/saas_backup.sh').read_text(encoding='utf-8')
    restore = (ROOT / 'scripts/saas_restore.sh').read_text(encoding='utf-8')
    readiness = (ROOT / 'server/saas_commercial_readiness.py').read_text(encoding='utf-8')
    require(ACCEPTANCE_RECORDS in backup, 'backup metadata missing acceptance record path')
    require('acceptance_records' in backup, 'backup metadata missing acceptance_records field')
    require('--system-files' in restore, 'restore script missing system-files scope')
    require('首租户验收记录备份证据' in readiness, 'commercial readiness missing backup evidence item')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py']:
        text = (ROOT / path).read_text(encoding='utf-8')
        require('scripts/saas_first_tenant_acceptance_backup_evidence_check.py' in text, f'{path} missing backup evidence check')
    verify_sample_metadata()
    print('saas_first_tenant_acceptance_backup_evidence_check: PASS')


if __name__ == '__main__':
    main()
