#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 9 gate: reports, exports, receipts and print.

Checks covered by this module gate:
- report summary
- CSV exports
- receipt detail
- print pages
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
    "tests/test_saas_receipt_export_report.py",
    "tests/test_saas_report_pages.py",
    "tests/test_saas_report_page_enhancements.py",
    "tests/test_saas_report_project_summary.py",
    "tests/test_saas_receipt_detail_fields.py",
    "tests/test_saas_receipt_print_export_alignment.py",
    "tests/test_saas_export_receipt_alignment.py",
    "tests/test_saas_module9_reports_print_gate.py",
]
REQUIRED_SOURCE = [
    "server/saas_report_pages.py",
    "server/saas_payment_pages.py",
    "server/saas_billing_api.py",
    "server/saas_report_project_api.py",
    "server/saas_csv_export.py",
]
REQUIRED_KEYWORDS = {
    "docs/saas-cloud-backoffice-plan.md": ["对账报表页面", "导出", "收据", "打印"],
    "server/saas_report_pages.py": ["报表工作台", "打印报表", "正式对账报表", "欠费账单明细"],
    "server/saas_payment_pages.py": ["收据详情", "收据打印", "导出收据", "window.print()"],
    "server/saas_csv_export.py": ["bill_export_rows", "payment_export_rows", "arrears_bill_export_rows"],
}
TEST_COMMAND = [PYTHON, "-m", "pytest", *REQUIRED_TESTS, "-q"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read(relative_path):
    path = ROOT / relative_path
    require(path.exists(), f"missing module 9 asset: {relative_path}")
    return path.read_text(encoding="utf-8")


def check_assets():
    for relative_path in [*REQUIRED_DOCS, *REQUIRED_TESTS, *REQUIRED_SOURCE]:
        require((ROOT / relative_path).exists(), f"missing module 9 asset: {relative_path}")
    print("PASS module 9 assets")


def check_keywords():
    for relative_path, keywords in REQUIRED_KEYWORDS.items():
        text = read(relative_path)
        for keyword in keywords:
            require(keyword in text, f"missing module 9 keyword {keyword}: {relative_path}")
    print("PASS module 9 report/export/receipt/print keywords")


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
    require(result.returncode == 0, "module 9 pytest gate failed")
    print("PASS module 9 pytest gate")


def check_release_gate_registration():
    gate = read("scripts/saas_release_gate.py")
    require("scripts/saas_module9_report_export_print_gate.py" in gate, "release gate missing module 9 gate")
    print("PASS module 9 release gate registration")


def main():
    check_assets()
    check_keywords()
    check_tests()
    check_release_gate_registration()
    print("saas_module9_report_export_print_gate: PASS")


if __name__ == "__main__":
    main()
