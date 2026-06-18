#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant-scoped storage key builder for SaaS cloud files."""

import re
from pathlib import PurePosixPath


class SaasStorage:
    SYSTEM_PREFIX = "system"
    TENANT_PREFIX = "tenants"
    CUSTOMER_CATEGORIES = {"imports", "attachments", "reports", "temp"}
    SYSTEM_CATEGORIES = {"templates", "defaults", "schema", "dictionaries"}

    def __init__(self, root_dir):
        self.root_dir = str(root_dir).rstrip("/")

    def system_asset_path(self, category, filename):
        safe_category = self._category(category, self.SYSTEM_CATEGORIES)
        safe_filename = self._filename(filename)
        return self._join(self.SYSTEM_PREFIX, safe_category, safe_filename)

    def upload_path(self, tenant_id, project_id, upload_id, category, filename):
        tenant_id = self._positive_id(tenant_id, "tenant_id")
        project_id = self._positive_id(project_id, "project_id")
        upload_id = self._positive_id(upload_id, "upload_id")
        safe_category = self._category(category, self.CUSTOMER_CATEGORIES)
        safe_filename = self._filename(filename)
        return self._join(
            self.TENANT_PREFIX,
            str(tenant_id),
            "projects",
            str(project_id),
            safe_category,
            str(upload_id),
            "original",
            safe_filename,
        )

    def _join(self, *parts):
        path = PurePosixPath(*parts).as_posix()
        if path.startswith("../") or "/../" in path or path.startswith("/"):
            raise ValueError("unsafe storage path")
        return path

    def _category(self, value, allowed):
        category = str(value or "").strip().lower()
        if category not in allowed:
            raise ValueError("unsupported storage category")
        return category

    def _positive_id(self, value, field):
        if value is None:
            raise ValueError(f"{field} is required")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be an integer") from exc
        if number <= 0:
            raise ValueError(f"{field} must be positive")
        return number

    def _filename(self, value):
        raw = str(value or "")
        unsafe = "/" in raw or "\\" in raw or ".." in raw.split("/")
        name = PurePosixPath(raw).name.strip()
        name = name.replace("\\", "_")
        name = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", name)
        name = name.strip("._ ")
        if unsafe and name:
            name = f"file_{name}"
        if not name:
            raise ValueError("filename is required")
        if name in {"system", "tenants"}:
            raise ValueError("reserved filename")
        return name
