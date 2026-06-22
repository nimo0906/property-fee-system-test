#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 6 batch billing and bill review gate registration tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_module6_gate_script_exists_and_is_registered():
    script = ROOT / 'scripts/saas_module6_batch_billing_gate.py'
    assert script.exists(), 'missing module 6 batch billing gate script'
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_module6_batch_billing_gate.py' in gate


def test_module6_gate_script_documents_required_scope_checks():
    script = ROOT / 'scripts/saas_module6_batch_billing_gate.py'
    text = script.read_text(encoding='utf-8')
    for keyword in [
        'project scope',
        'building scope',
        'category scope',
        'duplicate skip',
        'bill review',
        'tenant isolation',
    ]:
        assert keyword in text
