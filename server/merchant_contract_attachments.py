#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract attachment upload/download."""

import mimetypes
import os
import uuid
import urllib.parse

import server.db as db_module
from server.base import BaseHandler
from server.db import get_db, h, m
from server.form_parser import parse_form_data
from server.ui_components import render_table


ALLOWED_EXTS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_ATTACHMENT_SIZE = 30 * 1024 * 1024


def _data_root():
    root = os.environ.get("PM_DATA_DIR")
    if root:
        return root
    db_dir = os.path.dirname(db_module.DB_PATH)
    return os.path.dirname(db_dir) if os.path.basename(db_dir) == "database" else db_dir


def _attachment_dir(contract_id):
    path = os.path.join(_data_root(), "contract_attachments", str(int(contract_id)))
    os.makedirs(path, exist_ok=True)
    return path


def _clean_name(name):
    base = os.path.basename(name or "attachment")
    return "".join(ch if ch.isalnum() or ch in (" ", ".", "_", "-", "（", "）") else "_" for ch in base).strip() or "attachment"


def _attachment_path(contract_id, stored_name):
    root = os.path.realpath(_attachment_dir(contract_id))
    path = os.path.realpath(os.path.join(root, stored_name))
    if not path.startswith(root + os.sep):
        return None
    return path


def _attachment_rows(contract_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM contract_attachments WHERE contract_id=? ORDER BY id DESC",
        (contract_id,),
    ).fetchall()
    db.close()
    return rows


def parse_multipart(handler, form=None):
    return form if form is not None else parse_form_data(handler.rfile, handler.headers)


def save_contract_attachment(contract_id, file_item, attachment_type, uploaded_by=""):
    if file_item is None or not getattr(file_item, "filename", ""):
        return None, "请选择附件文件"
    original = _clean_name(file_item.filename)
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_EXTS:
        return None, "文件格式不允许，仅支持 PDF/JPG/PNG"
    data = file_item.file.read()
    if not data:
        return None, "附件为空"
    if len(data) > MAX_ATTACHMENT_SIZE:
        return None, "附件不能超过30MB"
    stored = f"{uuid.uuid4().hex}{ext}"
    path = _attachment_path(contract_id, stored)
    with open(path, "wb") as f:
        f.write(data)
    db = get_db()
    cur = db.execute(
        """INSERT INTO contract_attachments(contract_id,attachment_type,original_name,stored_name,file_ext,mime_type,file_size,uploaded_by)
           VALUES(?,?,?,?,?,?,?,?)""",
        (
            contract_id, attachment_type or "合同附件", original, stored, ext,
            file_item.type or mimetypes.guess_type(original)[0] or "application/octet-stream",
            len(data), uploaded_by or "",
        ),
    )
    db.commit(); db.close()
    return cur.lastrowid, ""




def _content_disposition(filename):
    safe_ascii = _ascii_filename(filename)
    encoded = urllib.parse.quote(str(filename or "attachment"), safe="")
    return f'inline; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded}'


def _ascii_filename(filename):
    text = str(filename or "attachment")
    safe = "".join(ch if 32 <= ord(ch) < 127 and ch not in '\";' else "_" for ch in text).strip(" .")
    return safe or "attachment"

def render_contract_attachments(contract_id):
    rows = _attachment_rows(contract_id)
    body = "".join(
        f"""<tr><td>{h(r['attachment_type'] or '合同附件')}</td><td>{h(r['original_name'])}</td>
        <td>{m((r['file_size'] or 0) / 1024)} KB</td><td>{h(r['uploaded_by'] or '-')}</td><td>{h(r['created_at'])}</td>
        <td><a class="btn btn-sm btn-outline-primary" href="/merchant_contracts/{contract_id}/attachments/{r['id']}/download">下载/预览</a>
        {('<form method="POST" action="/merchant_contracts/'+str(contract_id)+'/attachments/'+str(r['id'])+'/recognize" class="d-inline"><button class="btn btn-sm btn-outline-warning">识别协议</button></form>') if (r['attachment_type'] or '') == '补充协议' else ''}</td></tr>"""
        for r in rows
    )
    table_html = render_table(
        ['类型', '文件名', '大小', '上传人', '上传时间', ''],
        body,
        table_class='table table-sm mb-0',
        empty_text='暂无合同附件',
        col_count=6,
    )
    return f"""
    <div class="card mb-3"><div class="card-header">合同附件</div>
      <div class="card-body">
        <form method="POST" action="/merchant_contracts/{contract_id}/attachments" enctype="multipart/form-data" class="row g-2 align-items-end">
          <div class="col-md-3"><label>附件类型</label><select name="attachment_type" class="form-select">
            <option>合同扫描件</option><option>补充协议</option><option>退租协议</option><option>其他附件</option>
          </select></div>
          <div class="col-md-6"><label>选择文件</label><input type="file" name="file" class="form-control" accept=".pdf,.jpg,.jpeg,.png" required></div>
          <div class="col-md-3"><button class="btn btn-primary">上传附件</button></div>
          <div class="col-12 small text-muted">仅允许 PDF、JPG、JPEG、PNG，单个文件最大 30MB；文件保存在本地数据目录，不允许任意路径读取。</div>
        </form>
      </div>
      {table_html}
    </div>"""


class MerchantContractAttachmentMixin(BaseHandler):
    def _merchant_contract_attachment_upload(self, contract_id, form=None):
        if not self.headers.get("Content-Type", "").startswith("multipart/form-data"):
            return self._redirect(f"/merchant_contracts/{contract_id}?flash=请选择附件文件")
        form = parse_multipart(self, form)
        file_item = form["file"] if "file" in form else None
        user = self._get_current_user() or {}
        attachment_id, error = save_contract_attachment(contract_id, file_item, form.getfirst("attachment_type", "合同附件"), user.get("username") or "")
        if error:
            return self._redirect(f"/merchant_contracts/{contract_id}?flash={error}")
        self._audit("merchant_contract_attachment_upload", "merchant_contract", contract_id, None, {"attachment_id": attachment_id}, "上传合同附件")
        return self._redirect(f"/merchant_contracts/{contract_id}", flash="合同附件已上传")

    def _merchant_contract_attachment_download(self, contract_id, attachment_id):
        db = get_db()
        row = db.execute(
            "SELECT * FROM contract_attachments WHERE id=? AND contract_id=?",
            (attachment_id, contract_id),
        ).fetchone()
        db.close()
        if not row:
            return self._redirect(f"/merchant_contracts/{contract_id}?flash=附件不存在")
        path = _attachment_path(contract_id, row["stored_name"])
        if not path or not os.path.exists(path):
            return self._redirect(f"/merchant_contracts/{contract_id}?flash=附件文件不存在")
        data = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", row["mime_type"] or "application/octet-stream")
        self.send_header("Content-Disposition", _content_disposition(row["original_name"]))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
