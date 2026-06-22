#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 8 gate: import preview, confirm import and error rows.

Checks covered by this module gate:
- import preview
- confirm import
- error rows
- legacy desktop aliases
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
    "docs/saas-legacy-business-migration-gap.md",
    "docs/saas-production-deployment-commands.md",
]
REQUIRED_TESTS = [
    "tests/test_saas_import_review_flow.py",
    "tests/test_saas_import_error_download.py",
    "tests/test_saas_import_pages.py",
    "tests/test_saas_import_batch_review_pages.py",
    "tests/test_saas_charge_target_excel_import.py",
    "tests/test_saas_owner_import_mapping.py",
    "tests/test_saas_module8_import_gate.py",
]
REQUIRED_SOURCE = [
    "server/saas_import_pages.py",
    "server/saas_excel_import.py",
    "server/saas_import_mapping.py",
    "server/saas_import_duplicates.py",
    "server/saas_import_result_pages.py",
]
REQUIRED_KEYWORDS = {
    "docs/saas-cloud-backoffice-plan.md": ["导入预览", "确认导入", "错误行", "tenant/project scope"],
    "docs/saas-legacy-business-migration-gap.md": ["本地端", "错误行可下载", "确认导入记录"],
    "server/saas_import_pages.py": ["导入预览", "确认导入", "错误行", "下载错误行 CSV"],
    "server/saas_excel_import.py": [".xlsx", "导入预览", "确认导入", "错误行"],
    "server/saas_import_mapping.py": ["FIELD_ALIASES", "业主姓名", "房号/铺位号", "面积㎡"],
    "server/saas_import_result_pages.py": ["错误行未污染正式数据", "成功导入", "重复跳过"],
}
TEST_COMMAND = [PYTHON, "-m", "pytest", *REQUIRED_TESTS, "-q"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read(relative_path):
    path = ROOT / relative_path
    require(path.exists(), f"missing module 8 asset: {relative_path}")
    return path.read_text(encoding="utf-8")


def check_assets():
    for relative_path in [*REQUIRED_DOCS, *REQUIRED_TESTS, *REQUIRED_SOURCE]:
        require((ROOT / relative_path).exists(), f"missing module 8 asset: {relative_path}")
    print("PASS module 8 assets")


def check_keywords():
    for relative_path, keywords in REQUIRED_KEYWORDS.items():
        text = read(relative_path)
        for keyword in keywords:
            require(keyword in text, f"missing module 8 keyword {keyword}: {relative_path}")
    print("PASS module 8 import review keywords")


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
    require(result.returncode == 0, "module 8 pytest gate failed")
    print("PASS module 8 pytest gate")


def check_release_gate_registration():
    gate = read("scripts/saas_release_gate.py")
    require("scripts/saas_module8_import_review_gate.py" in gate, "release gate missing module 8 gate")
    print("PASS module 8 release gate registration")


def main():
    check_assets()
    check_keywords()
    check_tests()
    check_release_gate_registration()
    print("saas_module8_import_review_gate: PASS")


if __name__ == "__main__":
    main()
