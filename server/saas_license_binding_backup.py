#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup and restore helpers for license binding system file."""

import hashlib
import json
import shutil
from pathlib import Path

KIND = 'license-binding-backup'
BINDING_FILE = 'system/license_bindings/tenant_license_bindings.json'
MANIFEST = 'manifest.json'


def export_binding_backup(store, backup_root):
    backup_root = Path(backup_root)
    target = backup_root / BINDING_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    if store.path.exists():
        shutil.copy2(store.path, target)
    else:
        target.write_text(json.dumps({'bindings': {}}, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {
        'kind': KIND,
        'binding_file': BINDING_FILE,
        'sha256': _sha256(target),
    }
    (backup_root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
    return manifest


def verify_binding_backup(backup_root):
    backup_root = Path(backup_root)
    try:
        manifest = json.loads((backup_root / MANIFEST).read_text(encoding='utf-8'))
        if manifest.get('kind') != KIND or manifest.get('binding_file') != BINDING_FILE:
            return {'ok': False, 'error': 'invalid manifest'}
        binding_path = backup_root / BINDING_FILE
        if not binding_path.exists():
            return {'ok': False, 'error': 'missing binding file'}
        if _sha256(binding_path) != manifest.get('sha256'):
            return {'ok': False, 'error': 'checksum mismatch'}
        return {'ok': True, 'binding_file': BINDING_FILE}
    except Exception as exc:
        return {'ok': False, 'error': f'invalid backup: {exc}'}


def restore_binding_backup(backup_root, target_store):
    result = verify_binding_backup(backup_root)
    if not result.get('ok'):
        raise ValueError(result.get('error'))
    source = Path(backup_root) / BINDING_FILE
    data = json.loads(source.read_text(encoding='utf-8'))
    bindings = {int(k): str(v) for k, v in data.get('bindings', {}).items()}
    target_store.save(bindings)
    return bindings


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
