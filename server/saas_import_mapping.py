#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy rooms/owners import mapping for SaaS charge targets."""

from server.saas_service import PermissionDenied
from server.saas_import_duplicates import split_new_and_duplicates
from server.saas_batch_billing import normalize_payment_cycle

FIELD_ALIASES = {
    "building": ("building", "楼栋/区域", "楼栋", "区域"),
    "unit": ("unit", "单元/分区", "单元", "分区"),
    "room_number": ("room_number", "房号/铺位号", "房号", "铺位号", "room"),
    "category": ("category", "类型", "类别"),
    "area": ("area", "面积", "建筑面积"),
    "owner_name": ("owner_name", "业主姓名", "业主", "客户名称", "商户名称"),
    "owner_phone": ("owner_phone", "联系电话", "手机号", "业主电话", "电话"),
    "owner_type": ("owner_type", "业主类型", "客户类型"),
    "unit_price_override": ("unit_price_override", "独立单价", "覆盖单价", "商户单价"),
    "floor": ("floor", "楼层", "层数"),
    "shop_name": ("shop_name", "店名", "商户店名", "铺位名称"),
    "tenant_name": ("tenant_name", "租户", "承租人", "承租方"),
    "tenant_phone": ("tenant_phone", "租户电话", "承租人电话", "承租电话"),
    "payment_cycle": ("payment_cycle", "缴费周期", "收费周期"),
    "notes": ("notes", "备注", "说明"),
}


def _pick(row, key, default=""):
    for alias in FIELD_ALIASES[key]:
        value = row.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    return default


def normalize_import_row(row):
    return {
        **row,
        "building": _pick(row, "building"),
        "unit": _pick(row, "unit"),
        "room_number": _pick(row, "room_number"),
        "category": _pick(row, "category", "居民") or "居民",
        "area": _pick(row, "area"),
        "owner_name": _pick(row, "owner_name"),
        "owner_phone": _pick(row, "owner_phone"),
        "owner_type": _pick(row, "owner_type", "业主") or "业主",
        "unit_price_override": _pick(row, "unit_price_override"),
        "floor": _pick(row, "floor"),
        "shop_name": _pick(row, "shop_name"),
        "tenant_name": _pick(row, "tenant_name"),
        "tenant_phone": _pick(row, "tenant_phone"),
        "payment_cycle": normalize_payment_cycle(_pick(row, "payment_cycle")),
        "notes": _pick(row, "notes"),
    }


def attach_import_mapping_methods(cls):
    def preview_charge_target_import(self, user, project_id, rows):
        self._require(user, "import")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        valid, errors = [], []
        for idx, raw in enumerate(rows, start=1):
            row = normalize_import_row(raw)
            try:
                if not row["building"]:
                    raise ValueError("楼栋/区域不能为空")
                if not row["room_number"]:
                    raise ValueError("房号/铺位号不能为空")
                area = float(row.get("area") or 0)
                if area <= 0:
                    raise ValueError("面积必须是数字且大于0")
                row["area"] = area
                if row.get("unit_price_override") not in (None, ""):
                    row["unit_price_override"] = float(row["unit_price_override"])
                else:
                    row["unit_price_override"] = None
                if row.get("floor") not in (None, ""):
                    row["floor"] = int(float(row["floor"]))
                else:
                    row["floor"] = None
                valid.append(row)
            except ValueError as exc:
                errors.append({"row": idx, "error": str(exc), "data": dict(raw)})
        iid = self._id()
        self.imports[iid] = {"id": iid, "tenant_id": user["tenant_id"], "project_id": project_id, "valid_rows": valid, "errors": errors, "confirmed": False}
        self._log(user, project_id, 'import.preview', 'import', iid, {'valid_count': len(valid), 'error_count': len(errors)})
        return {"import_id": iid, "valid_count": len(valid), "error_count": len(errors), "errors": errors}


    def get_import_review(self, user, project_id, import_id):
        self._require(user, "import")
        imp = self.imports.get(import_id)
        if not imp or imp["tenant_id"] != user["tenant_id"] or imp["project_id"] != project_id:
            raise PermissionDenied("cross tenant import")
        return {
            "import_id": import_id,
            "tenant_id": imp["tenant_id"],
            "project_id": imp["project_id"],
            "valid_count": len(imp["valid_rows"]),
            "error_count": len(imp["errors"]),
            "valid_rows": imp["valid_rows"],
            "errors": imp["errors"],
            "confirmed": imp["confirmed"],
        }

    def confirm_charge_target_import(self, user, project_id, import_id):
        self._require(user, "import")
        imp = self.imports.get(import_id)
        if not imp or imp["tenant_id"] != user["tenant_id"] or imp["project_id"] != project_id:
            raise PermissionDenied("cross tenant import")
        if imp["confirmed"]:
            result = {"created_count": 0, "skipped_count": len(imp["errors"])}
            if imp.get("owner_created_count"):
                result["owner_created_count"] = 0
            return result
        created = owner_created = duplicate_skipped = 0
        rows_to_create, duplicate_rows = split_new_and_duplicates(imp["valid_rows"], self.list_charge_targets(user, project_id))
        duplicate_skipped = len(duplicate_rows)
        for row in rows_to_create:
            owner_id = int(row.get("owner_id") or 0)
            if row.get("owner_name"):
                owner = self.create_owner(user, project_id, row["owner_name"], row.get("owner_phone", ""), row.get("owner_type", "业主"))
                owner_id = owner["id"]
                owner_created += 1
            self.create_charge_target(user, project_id, row["building"], row.get("unit", ""), row["room_number"], row.get("category", "居民"), row["area"], owner_id, row.get("unit_price_override"),
                floor=row.get("floor"), shop_name=row.get("shop_name", ""), tenant_name=row.get("tenant_name", ""),
                tenant_phone=row.get("tenant_phone", ""), payment_cycle=row.get("payment_cycle", ""), notes=row.get("notes", ""))
            created += 1
        imp["confirmed"] = True
        imp["owner_created_count"] = owner_created
        skipped_total = len(imp["errors"]) + duplicate_skipped
        self._log(user, project_id, 'import.confirm', 'import', import_id, {'created_count': created, 'skipped_count': skipped_total, 'duplicate_skipped_count': duplicate_skipped, 'owner_created_count': owner_created})
        result = {"created_count": created, "skipped_count": skipped_total}
        if duplicate_skipped:
            result["duplicate_skipped_count"] = duplicate_skipped
        if owner_created:
            result["owner_created_count"] = owner_created
        return result

    cls.preview_charge_target_import = preview_charge_target_import
    cls.get_import_review = get_import_review
    cls.confirm_charge_target_import = confirm_charge_target_import
