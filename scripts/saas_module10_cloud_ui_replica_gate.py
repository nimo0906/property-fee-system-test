#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 10 gate: cloud UI replica of local core pages.

Checks covered by this module gate:
- local core page shell
- sidebar navigation
- topbar account actions
- mobile menu
- core business pages
- tenant isolation
- release gate registration
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
REQUIRED_TESTS = ["tests/test_saas_module10_ui_replica_gate.py"]
REQUIRED_SOURCE = [
    "server/saas_user_pages.py",
    "server/saas_backoffice_pages.py",
    "server/saas_charge_target_pages.py",
    "server/saas_fee_type_pages.py",
    "server/saas_bill_pages.py",
    "server/saas_payment_pages.py",
    "server/saas_report_pages.py",
    "server/saas_import_pages.py",
]
REQUIRED_DOCS = ["docs/saas-cloud-backoffice-plan.md"]
REQUIRED_KEYWORDS = {
    "server/saas_user_pages.py": [
        "app-shell", "sidebar-brand", "sidebar-nav", "topbar", "mobile-menu-btn", "content-stack",
    ],
    "docs/saas-cloud-backoffice-plan.md": ["本地 App 风格", "核心页面", "云端 UI 复刻"],
}
TEST_COMMAND = [PYTHON, "-m", "pytest", *REQUIRED_TESTS, "-q"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read(relative_path):
    path = ROOT / relative_path
    require(path.exists(), f"missing module 10 asset: {relative_path}")
    return path.read_text(encoding="utf-8")


def check_assets():
    for relative_path in [*REQUIRED_TESTS, *REQUIRED_SOURCE, *REQUIRED_DOCS]:
        require((ROOT / relative_path).exists(), f"missing module 10 asset: {relative_path}")
    print("PASS module 10 assets")


def check_keywords():
    for relative_path, keywords in REQUIRED_KEYWORDS.items():
        text = read(relative_path)
        for keyword in keywords:
            require(keyword in text, f"missing module 10 keyword {keyword}: {relative_path}")
    print("PASS module 10 UI replica keywords")


def check_tests():
    result = subprocess.run(TEST_COMMAND, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    print(result.stdout, end="")
    require(result.returncode == 0, "module 10 pytest gate failed")
    print("PASS module 10 pytest gate")


def check_release_gate_registration():
    gate = read("scripts/saas_release_gate.py")
    require("scripts/saas_module10_cloud_ui_replica_gate.py" in gate, "release gate missing module 10 gate")
    print("PASS module 10 release gate registration")


def main():
    check_assets()
    check_keywords()
    check_tests()
    check_release_gate_registration()
    print("saas_module10_cloud_ui_replica_gate: PASS")


if __name__ == "__main__":
    main()
