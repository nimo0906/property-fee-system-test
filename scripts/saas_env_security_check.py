#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production SaaS secrets from runtime environment only."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_deploy import validate_env_security

REQUIRED = ("POSTGRES_PASSWORD", "APP_SECRET_KEY")


def masked(name, value):
    if not value:
        return f"{name}: missing"
    return f"{name}: length={len(value)}"


def main():
    parser = argparse.ArgumentParser(description="Check SaaS production secrets without printing values.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate that the runtime secret gate is wired without requiring local production secrets.",
    )
    args = parser.parse_args()
    if args.dry_run:
        print("PASS saas production env security dry-run plan")
        print("POSTGRES_PASSWORD: required; value hidden")
        print("APP_SECRET_KEY: required; value hidden")
        return
    env = {name: os.environ.get(name, "") for name in REQUIRED}
    result = validate_env_security(env)
    missing = [name for name, value in env.items() if not value]
    weak = result.get("weak", [])
    if missing or weak:
        problems = sorted(set(missing + weak))
        print("FAIL saas production env security")
        for name in problems:
            print(masked(name, env.get(name, "")))
        raise SystemExit(1)
    print("PASS saas production env security")
    for name in REQUIRED:
        print(masked(name, env[name]))


if __name__ == "__main__":
    main()
