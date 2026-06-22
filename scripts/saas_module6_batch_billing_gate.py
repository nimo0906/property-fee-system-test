#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 6 gate: batch billing and bill review.

Checks covered by this module gate:
- project scope
- building scope
- category scope
- duplicate skip
- bill review
- tenant isolation
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
REQUIRED_DOCS = [
    "docs/saas-legacy-business-migration-gap.md",
    "docs/saas-cloud-backoffice-plan.md",
    "docs/saas-production-deployment-commands.md",
]
REQUIRED_TESTS = [
    "tests/test_saas_batch_billing.py",
    "tests/test_saas_batch_billing_preview_pages.py",
    "tests/test_saas_bill_pages.py",
    "tests/test_saas_bill_search_batch_pages.py",
    "tests/test_saas_fee_rule_alignment.py",
    "tests/test_saas_module6_batch_billing_gate.py",
]
REQUIRED_SOURCE = [
    "server/saas_batch_billing.py",
    "server/saas_repository_batch_billing.py",
    "server/saas_bill_pages.py",
    "server/saas_bill_preview_pages.py",
    "server/saas_bill_review_ui.py",
    "server/saas_fee_rules.py",
]
REQUIRED_KEYWORDS = {
    "docs/saas-legacy-business-migration-gap.md": ["批量出账", "项目", "楼栋", "分类", "防重复出账"],
    "server/saas_batch_billing.py": ["target_matches_scope", "build_batch_bill_rows", "bill_key", "fee_applies_to_target"],
    "server/saas_repository_batch_billing.py": ["_bill_exists", "skipped_count", "bill.batch_generate"],
    "server/saas_bill_pages.py": ["批量审核", "batch-approve-filtered", "重复出账自动跳过"],
    "server/saas_bill_review_ui.py": ["待审核", "审核通过", "去收款登记"],
    "server/saas_fee_rules.py": ["effective_unit_price", "billing_mode", "unit_price_override", "fixed"],
}
TEST_COMMAND = [
    PYTHON,
    "-m",
    "pytest",
    *REQUIRED_TESTS,
    "-q",
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read(relative_path):
    path = ROOT / relative_path
    require(path.exists(), f"missing module 6 asset: {relative_path}")
    return path.read_text(encoding="utf-8")


def check_assets():
    for relative_path in [*REQUIRED_DOCS, *REQUIRED_TESTS, *REQUIRED_SOURCE]:
        require((ROOT / relative_path).exists(), f"missing module 6 asset: {relative_path}")
    print("PASS module 6 assets")


def check_keywords():
    for relative_path, keywords in REQUIRED_KEYWORDS.items():
        text = read(relative_path)
        for keyword in keywords:
            require(keyword in text, f"missing module 6 keyword {keyword}: {relative_path}")
    print("PASS module 6 scope keywords")


def check_tests():
    result = subprocess.run(
        TEST_COMMAND,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout, end="")
    require(result.returncode == 0, "module 6 pytest gate failed")
    print("PASS module 6 pytest gate")


def check_release_gate_registration():
    gate = read("scripts/saas_release_gate.py")
    require("scripts/saas_module6_batch_billing_gate.py" in gate, "release gate missing module 6 gate")
    print("PASS module 6 release gate registration")


def main():
    check_assets()
    check_keywords()
    check_tests()
    check_release_gate_registration()
    print("saas_module6_batch_billing_gate: PASS")


if __name__ == "__main__":
    main()
