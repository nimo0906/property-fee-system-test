#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import rented-contract Excel sheet into space contract archive."""

from server.backups import create_db_backup
from server.base import BaseHandler
from server.db import get_db
from server.form_parser import parse_form_data
from server.import_cache import load_import_file, save_import_file
from server.import_views import _form_value
from server.merchant_contract_import_parser import MAX_UPLOAD_SIZE, _load_rows
from server.merchant_contract_import_store import _rows_from_form, _upsert_row
from server.merchant_contract_import_view import (
    render_contract_import_preview,
    render_contract_import_second_review,
)


class MerchantContractImportMixin(BaseHandler):
    def _merchant_contract_import_form(self):
        return self._redirect("/import?data_type=commercial_contracts", flash="合同导入已合并到数据导入工作台")

    def _merchant_contract_import_preview(self, form=None):
        if form is None:
            try:
                form = parse_form_data(self.rfile, self.headers)
            except Exception:
                return self._redirect("/import?data_type=commercial_contracts&flash=文件解析失败")
        file_item = form.getvalue("file")
        if not file_item:
            return self._redirect("/import?data_type=commercial_contracts&flash=请选择文件")
        filename = form["file"].filename if "file" in form else ""
        contract_scope = form.getvalue("contract_scope") or "commercial"
        if contract_scope == "b_tower":
            return self._redirect("/import?data_type=commercial_contracts&flash=B座合同导入模板正在补齐；请先使用房间管理维护 B座出租合同，商业合同可继续导入。")
        raw_data = file_item if isinstance(file_item, bytes) else str(file_item).encode("utf-8")
        if len(raw_data) > MAX_UPLOAD_SIZE:
            return self._redirect("/import?data_type=commercial_contracts&flash=文件不能超过10MB")
        try:
            rows = _load_rows(filename, raw_data)
        except Exception as exc:
            return self._redirect(f"/import?data_type=commercial_contracts&flash={exc}")
        token = save_import_file(raw_data)
        return render_contract_import_preview(self, filename, token, rows)

    def _merchant_contract_import_confirm(self, d):
        filename = _form_value(d, "filename")
        if _form_value(d, "row_count"):
            rows = _rows_from_form(d)
        else:
            token = _form_value(d, "upload_token")
            try:
                raw_data = load_import_file(token)
                rows = _load_rows(filename or "contracts.xlsx", raw_data)
            except Exception as exc:
                return self._redirect(f"/import?data_type=commercial_contracts&flash={exc}")
        try:
            backup_name = create_db_backup("auto_before_contract_import")
        except FileNotFoundError:
            return self._redirect("/import?data_type=commercial_contracts&flash=数据库文件不存在，未执行导入")
        db = get_db()
        created = updated = skipped = 0
        skipped_reasons = []
        skipped_rows = []
        try:
            for row in rows:
                blocking = [e for e in row["errors"] if e != "百分比/销售额租金需人工核对"]
                if blocking:
                    skipped += 1
                    row["errors"] = blocking
                    skipped_rows.append(row)
                    if len(skipped_reasons) < 3:
                        skipped_reasons.append(f"Excel {row.get('row_no', '?')}：{'、'.join(blocking)}")
                    continue
                result = _upsert_row(db, row)
                if result == "created":
                    created += 1
                else:
                    updated += 1
            db.commit()
        finally:
            db.close()
        if skipped_rows:
            return render_contract_import_second_review(self, filename, skipped_rows, created, updated)
        flash = f"合同档案导入完成：新增 {created} 条，更新 {updated} 条，跳过 {skipped} 条"
        if skipped_reasons:
            flash += "；跳过原因：" + "；".join(skipped_reasons)
        return self._redirect("/merchant_contracts", flash=flash)
