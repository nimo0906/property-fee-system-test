#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 7 gate: payment, arrears and ledger.

Checks covered by this module gate:
- partial payment
- arrears linkage
- idempotency conflict
- payment ledger
- tenant isolation
- release gate registration
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
REQUIRED_DOCS = [
    "docs/saas-cloud-backoffice-plan.md",
    "docs/saas-production-deployment-commands.md",
    "docs/saas-day1-operations-checklist.md",
]
REQUIRED_TESTS = [
    "tests/test_saas_payment_arrears_alignment.py",
    "tests/test_saas_payment_idempotency.py",
    "tests/test_saas_payment_pages.py",
    "tests/test_saas_payment_search_receipt_pages.py",
    "tests/test_saas_receipt_export_report.py",
    "tests/test_saas_module7_payment_gate.py",
]
REQUIRED_SOURCE = [
    "server/saas_billing_service.py",
    "server/saas_repository.py",
    "server/saas_repository_search.py",
    "server/saas_payment_pages.py",
    "server/saas_bill_balances.py",
    "server/saas_report_pages.py",
]
REQUIRED_KEYWORDS = {
    "docs/saas-cloud-backoffice-plan.md": ["收款登记页面", "对账报表页面", "收据", "tenant/project scope"],
    "docs/saas-day1-operations-checklist.md": ["部分收款", "欠费", "收款列表", "报表汇总"],
    "server/saas_billing_service.py": ["remaining arrears", "idempotency key conflict", "bill not found"],
    "server/saas_repository.py": ["remaining arrears", "idempotency key conflict", "receipt_number"],
    "server/saas_repository_search.py": ["paid_amount", "unpaid_amount", "receipt_number"],
    "server/saas_payment_pages.py": ["收款流水", "欠费联动", "幂等防重复", "收后欠费余额"],
    "server/saas_bill_balances.py": ["paid_amount", "unpaid_amount"],
}
TEST_COMMAND = [PYTHON, "-m", "pytest", *REQUIRED_TESTS, "-q"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read(relative_path):
    path = ROOT / relative_path
    require(path.exists(), f"missing module 7 asset: {relative_path}")
    return path.read_text(encoding="utf-8")


def check_assets():
    for relative_path in [*REQUIRED_DOCS, *REQUIRED_TESTS, *REQUIRED_SOURCE]:
        require((ROOT / relative_path).exists(), f"missing module 7 asset: {relative_path}")
    print("PASS module 7 assets")


def check_keywords():
    for relative_path, keywords in REQUIRED_KEYWORDS.items():
        text = read(relative_path)
        for keyword in keywords:
            require(keyword in text, f"missing module 7 keyword {keyword}: {relative_path}")
    print("PASS module 7 payment arrears keywords")


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
    require(result.returncode == 0, "module 7 pytest gate failed")
    print("PASS module 7 pytest gate")


def check_release_gate_registration():
    gate = read("scripts/saas_release_gate.py")
    require("scripts/saas_module7_payment_arrears_gate.py" in gate, "release gate missing module 7 gate")
    print("PASS module 7 release gate registration")


def main():
    check_assets()
    check_keywords()
    check_tests()
    check_release_gate_registration()
    print("saas_module7_payment_arrears_gate: PASS")


if __name__ == "__main__":
    main()
