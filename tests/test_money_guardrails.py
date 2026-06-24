#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guardrails for final RMB amount precision."""

from pathlib import Path
import re
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = PROJECT_ROOT / 'server'

ROUND_TWO_ALLOWLIST = {
    'meter.py',
    'meter_ledger.py',
}
STEP_001_ALLOW_KEYWORDS = (
    'area', '面积', '单价', 'unit_price', 'custom_rate', 'rate_', 'max_rate',
    'reading', '读数', 'percent', '比例', '建筑面积', '合同面积',
)


class TestMoneyGuardrails(unittest.TestCase):
    def test_final_amount_code_does_not_use_round_to_cents(self):
        offenders = []
        pattern = re.compile(r'round\([^\n]+,\s*2\)')
        for path in SERVER_ROOT.glob('*.py'):
            if path.name in ROUND_TWO_ALLOWLIST:
                continue
            text = path.read_text(encoding='utf-8')
            for match in pattern.finditer(text):
                offenders.append(f'{path.name}:{text.count(chr(10), 0, match.start()) + 1}:{match.group(0)}')
        self.assertEqual(offenders, [])

    def test_amount_inputs_do_not_use_cent_step(self):
        offenders = []
        pattern = re.compile(r'<input[^>]+step=["\']0\.01["\'][^>]*>', re.I)
        for path in SERVER_ROOT.glob('*.py'):
            text = path.read_text(encoding='utf-8')
            for match in pattern.finditer(text):
                snippet = match.group(0)
                if any(keyword in snippet for keyword in STEP_001_ALLOW_KEYWORDS):
                    continue
                offenders.append(f'{path.name}:{text.count(chr(10), 0, match.start()) + 1}:{snippet}')
        self.assertEqual(offenders, [])
