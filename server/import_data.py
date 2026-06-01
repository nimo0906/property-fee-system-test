#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data import from CSV/Excel files."""

import os

from server.db import get_db
from server.base import BaseHandler
from server.form_parser import parse_form_data
from server.import_parser import (
    SUPPORTED_EXTENSIONS,
    build_column_map,
    detect_data_type,
    detect_header_row,
    enrich_column_map_from_subheader,
    parse_rows,
)
from server.basic_import import import_basic_info
from server.backups import create_db_backup
from server.import_cache import load_import_file, save_import_file
from server.import_fee_mapping_views import ImportFeeMappingMixin
from server.import_preview_views import ImportPreviewMixin
from server.import_views import ImportViewMixin

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = SUPPORTED_EXTENSIONS


class ImportMixin(ImportPreviewMixin, ImportFeeMappingMixin, ImportViewMixin, BaseHandler):

    COLUMN_MAP = {
        '楼栋':'building','building':'building','号楼':'building','栋':'building',
        '单元':'unit','unit':'unit','座':'unit',
        '房号':'room_number','room_number':'room_number','房间号':'room_number','房间':'room_number','门牌号':'room_number','number':'room_number','铺位号':'room_number','铺位':'room_number',
        '楼层':'floor','floor':'floor','层':'floor','floor_number':'floor',
        '类别':'category','category':'category','类型':'category','category_name':'category',
        '面积':'area','面积㎡':'area','area':'area','area_sqm':'area','建筑面积':'area','平方':'area',
        '物业费单价':'custom_rate','商业物业费单价':'custom_rate','单价':'custom_rate','custom_rate':'custom_rate',
        '缴费周期':'payment_cycle','收费周期':'payment_cycle','付款周期':'payment_cycle','payment_cycle':'payment_cycle',
        '水费标准':'water_rate_type','水费档位':'water_rate_type','water_rate_type':'water_rate_type',
        '业主':'owner_name','业主姓名':'owner_name','owner_name':'owner_name','姓名':'owner_name','name':'owner_name','客户':'owner_name','租户':'owner_name','租户姓名':'tenant_name','租户身份证号':'tenant_id_card','承租人身份证号':'tenant_id_card',
        '电话':'owner_phone','phone':'owner_phone','手机':'owner_phone','手机号':'owner_phone','联系电话':'owner_phone','tel':'owner_phone','mobile':'owner_phone',
        '店铺名称':'shop_name','店铺':'shop_name','商铺名称':'shop_name',
        '业态':'business_type',
        '合同开始日期':'contract_start','合同起始日期':'contract_start','合同开始':'contract_start','起租日期':'contract_start','租赁开始日期':'contract_start',
        '合同到期日期':'contract_end','合同结束日期':'contract_end','合同截止日期':'contract_end','合同到期':'contract_end','合同结束':'contract_end','租赁结束日期':'contract_end',
        '合同日期':'contract_period','合同期':'contract_period','合同缴租期':'contract_period','合同期限':'contract_period','租赁时间':'contract_period',
        '催缴租金租期':'rent_period','租金租期':'rent_period',
        '身份证':'id_card','id_card':'id_card','身份证号':'id_card','证件号':'id_card',
        '费用类型':'fee_type_name','fee_type_name':'fee_type_name','fee_type':'fee_type_name','费用项目':'fee_type_name','收费项目':'fee_type_name','项目':'fee_type_name',
        '账期':'period','period':'period','月份':'period','billing_period':'period','月':'period','收费月份':'period',
        '用户名称':'owner_name','客户名称':'owner_name','住户名称':'owner_name',
        '金额':'amount','amount':'amount','收费金额':'amount','费用金额':'amount','total_amount':'amount','应收':'amount','应缴':'amount','本期金额':'amount',
        '已缴':'paid_amount','paid_amount':'paid_amount','实缴':'paid_amount','已付':'paid_amount','本期收款(合计)':'paid_amount','本期收款合计':'paid_amount',
        '状态':'status','status':'status','缴费状态':'status','bill_status':'status',
        '缴费日期':'payment_date','payment_date':'payment_date','日期':'payment_date','date':'payment_date','收费日期':'payment_date','付款日期':'payment_date',
        '缴费方式':'payment_method','payment_method':'payment_method','支付方式':'payment_method','method':'payment_method','付款方式':'payment_method',
        '滞纳金':'late_fee','late_fee':'late_fee','违约金':'late_fee',
        '备注':'notes','notes':'notes','note':'notes','remark':'notes','说明':'notes',
    }

    def _import_page(self):
        flash = self._get_flash()
        self._html(self._page('数据导入', flash + '''
    <div class="import-hero import-hero-pro">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
            <div>
                <div class="page-kicker">DATA INTAKE</div>
                <h4 class="mb-2">数据导入工作台 <span class="text-muted fs-6">导入向导</span></h4>
                <p class="mb-0 text-muted">按“上传预览、字段核对、确认导入、结果复核”处理。基础资料可写入系统；历史收款金额只做识别核对，不自动入账。</p>
            </div>
            <div class="d-flex gap-2 align-items-center">
                <a class="btn btn-outline-primary" href="/import/template/basic.csv" download="basic_info_template.csv"><i class="bi bi-download"></i> 下载基础资料模板</a>
                <a class="btn btn-outline-secondary" href="/backups"><i class="bi bi-cloud-check"></i> 备份记录</a>
            </div>
        </div>
    </div>
    <div class="import-dashboard">
        <section class="import-upload-panel">
            <div class="section-heading">
                <div>
                    <span class="section-eyebrow">STEP 01</span>
                    <h5>上传文件</h5>
                </div>
                <span class="badge status-info">CSV / XLSX / XLS</span>
            </div>
            <form method=POST action="/import/upload" enctype="multipart/form-data" class="row g-3">
                <div class="col-12">
                    <label class="form-label required-dot">选择文件</label>
                    <input type="file" name="file" class="form-control form-control-lg" accept=".csv,.xlsx,.xls" required>
                    <div class="form-text">最大 10MB。建议先预览识别结果，确认字段映射后再导入。</div>
                </div>
                <div class="col-12">
                    <label class="form-label">数据类型</label>
                    <select name="data_type" class="form-select">
                        <option value="auto">自动检测（推荐）</option>
                        <option value="rooms">房间基础资料</option>
                        <option value="owners">业主信息</option>
                        <option value="payment_ledger">收款明细识别（不自动入账）</option>
                        <option value="bills">账单记录（谨慎使用）</option>
                    </select>
                </div>
                <div class="col-12">
                    <div class="import-action-row">
                        <button name="mode" value="preview" class="btn btn-primary btn-lg"><i class="bi bi-eye"></i> 预览识别结果</button>
                        <button name="mode" value="import" class="btn btn-outline-primary btn-lg" onclick="return confirm('建议先预览并核对字段。确认直接导入？')"><i class="bi bi-cloud-upload"></i> 直接导入</button>
                    </div>
                </div>
            </form>
        </section>
        <aside class="import-side-panel">
            <div class="section-heading">
                <div>
                    <span class="section-eyebrow">CONTROL</span>
                    <h5>导入边界</h5>
                </div>
            </div>
            <div class="import-rule-list">
                <div class="import-rule-item success"><i class="bi bi-check2-circle"></i><div><strong>基础资料导入</strong><span>可写入房间、业主、面积、类别、合同日期、备注资料。</span></div></div>
                <div class="import-rule-item warning"><i class="bi bi-exclamation-triangle"></i><div><strong>收款明细识别</strong><span>列头识别、房号归属、合同日期、跳过行和问题行需要核对。</span></div></div>
                <div class="import-rule-item danger"><i class="bi bi-shield-check"></i><div><strong>安全机制</strong><span>确认导入前自动备份，导错后可一键撤销；历史金额不会自动入账。</span></div></div>
            </div>
        </aside>
    </div>
    <div class="import-flow-grid">
        <div class="import-flow-card"><span>01</span><strong>上传预览</strong><small>先看系统识别出的类型、列头和数据行。</small></div>
        <div class="import-flow-card"><span>02</span><strong>字段核对</strong><small>楼栋、房号、面积、业主、合同日期必须确认。</small></div>
        <div class="import-flow-card"><span>03</span><strong>确认写入</strong><small>写入前自动创建备份，结果页可撤销。</small></div>
        <div class="import-flow-card"><span>04</span><strong>结果复核</strong><small>下载问题行 CSV，修正后可单独重新导入。</small></div>
    </div>
    ''', 'import'))

    def _import_upload(self):
        """处理上传文件并导入数据（校验格式和大小后解析）"""
        try:
            form = parse_form_data(self.rfile, self.headers)
        except:
            return self._redirect("/import?flash=文件解析失败")
        upload_token = form.getvalue("upload_token", "")
        file_item = form.getvalue("file")
        if file_item:
            raw_data = file_item.encode("utf-8") if isinstance(file_item, str) else file_item
            filename = form["file"].filename if hasattr(form["file"], "filename") else ""
        elif upload_token:
            try:
                raw_data = load_import_file(upload_token)
            except FileNotFoundError:
                return self._redirect("/import?flash=导入预览已过期，请重新上传文件")
            filename = form.getvalue("filename", "")
        else:
            return self._redirect("/import?flash=请选择文件")
        data_type = form.getvalue("data_type", "auto")
        mode = form.getvalue("mode", "preview")

        # ── 文件校验 ────────────────────────────────────────────
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return self._redirect(f"/import?flash=不支持的文件格式 {ext}，仅支持 .csv/.xlsx/.xls")
        if len(raw_data) > MAX_UPLOAD_SIZE:
            max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
            return self._redirect(f"/import?flash=文件过大（{len(raw_data)/1024/1024:.1f}MB），最大 {max_mb}MB")
        try:
            rows = parse_rows(filename, raw_data)
        except Exception as e:
            return self._redirect(f"/import?flash=文件解析失败: {str(e)}")
        if len(rows) < 1:
            return self._redirect("/import?flash=文件为空")
        header_idx = detect_header_row(rows, self.COLUMN_MAP)
        headers = rows[header_idx]
        data_rows = rows[header_idx + 1:]
        col_map = build_column_map(headers, self.COLUMN_MAP)
        col_map = enrich_column_map_from_subheader(col_map, headers, rows, self.COLUMN_MAP, header_idx)
        if mode == "import":
            col_map = self._col_map_from_form(form, col_map, len(headers))
        if not col_map:
            return self._redirect("/import?flash=未能识别列头")
        if data_type == "auto":
            data_type = detect_data_type(col_map, headers)
        if mode == "confirm_fee_mapping" and data_type == "payment_ledger":
            return self._render_fee_mapping_result(filename, headers, data_rows, form)
        if mode == "preview" or data_type == "unknown":
            upload_token = save_import_file(raw_data)
            return self._render_import_preview(filename, headers, data_rows, col_map, data_type, header_idx, upload_token)
        # Import
        try:
            backup_name = create_db_backup('auto_before_import')
        except FileNotFoundError:
            return self._redirect('/import?flash=数据库文件不存在，未执行导入')
        db = get_db()
        imported = 0
        skipped = 0
        errors = []
        result = None
        try:
            def gc(key, default=""):
                idx = col_map.get(key)
                if idx is not None and idx < len(row):
                    return row[idx].strip()
                return default
            if data_type == "owners":
                for row_no, row in enumerate(data_rows, start=1):
                    try:
                        name = gc('owner_name')
                        phone = gc('owner_phone')
                        id_card = gc('id_card')
                        if not name:
                            skipped += 1
                            continue
                        exist = db.execute("SELECT id FROM owners WHERE name=? AND (phone=? OR ?='')", (name, phone, phone)).fetchone()
                        if not exist:
                            db.execute("INSERT INTO owners(name,phone,id_card) VALUES(?,?,?)", (name, phone, id_card))
                            imported += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        errors.append(f'第{row_no}行: {e}')
                result = self._simple_import_result(imported_owners=imported, skipped=skipped, errors=errors)
            elif data_type == "rooms":
                result = import_basic_info(db, headers, data_rows, col_map)
                imported = result['imported_rooms'] + result['imported_owners']
                skipped = result['skipped']
                errors = result['errors']
            elif data_type == "payment_ledger":
                result = import_basic_info(db, headers, data_rows, col_map)
                imported = result['imported_rooms'] + result['imported_owners']
                skipped = result['skipped']
                errors = result['errors']
            elif data_type == "bills":
                for row_no, row in enumerate(data_rows, start=1):
                    try:
                        building = gc('building', '')
                        room_number = gc('room_number', '')
                        fee_type_name = gc('fee_type_name')
                        period = gc('period')
                        amount = float(gc('amount', '0'))
                        status = gc('status', 'unpaid')
                        paid_amount = float(gc('paid_amount', '0'))
                        payment_date = gc('payment_date')
                        payment_method = gc('payment_method', 'cash')
                        if not fee_type_name or not period or amount <= 0: continue
                        ft = db.execute("SELECT id FROM fee_types WHERE name=? LIMIT 1", (fee_type_name,)).fetchone()
                        if not ft:
                            errors.append(f"费用类型[{fee_type_name}]不存在")
                            continue
                        room = None
                        if building and room_number:
                            room = db.execute("SELECT id,owner_id FROM rooms WHERE building=? AND room_number=?", (building, room_number)).fetchone()
                        if not room:
                            errors.append(f"房间[{building}-{room_number}]不存在")
                            continue
                        exist = db.execute("SELECT id FROM bills WHERE room_id=? AND fee_type_id=? AND billing_period=?", (room[0], ft[0], period)).fetchone()
                        if exist: skipped += 1; continue
                        bn = f"IMP_{room[0]}_{ft[0]}_{period}"
                        db.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)",
                                   (room[0], room[1], ft[0], period, amount, status, bn))
                        imported += 1
                        # Import payment if paid
                        if paid_amount > 0 and payment_date:
                            bid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                            db.execute("INSERT INTO payments(bill_id,amount_paid,payment_date,payment_method) VALUES(?,?,?,?)",
                                       (bid, paid_amount, payment_date, payment_method))
                            if paid_amount >= amount:
                                db.execute("UPDATE bills SET status=? WHERE id=?", ("paid", bid))
                    except Exception as e:
                        errors.append(f'第{row_no}行: {e}')
                result = self._simple_import_result(imported_rooms=imported, skipped=skipped, errors=errors)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        self._audit('data_import', 'import', None, None, {'filename': filename, 'data_type': data_type, 'rows': len(data_rows), 'result': result, 'backup': backup_name}, '数据导入')
        return self._render_import_result(filename, data_type, len(data_rows), backup_name, result)

    def _basic_import_template(self):
        csv_text = (
            '楼栋,单元/座,铺位号,楼层,房屋类别,面积㎡,商户名称,联系电话,租户姓名,店铺名称,业态,合同开始日期,合同结束日期,催缴租金租期,物业费单价,缴费周期,水费标准,备注\n'
            '金莎国际,商场,1F-101,1,商户,88.5,甲商贸,13900000000,李四,某某便利店,餐饮,2026-01-01,2026-12-31,2026-01-01至2026-06-30,4.8,季付,非居民,历史金额不要填在本模板\n'
            'B座,B座,902,9,居民,95.2,王五,13800000000,,,,2026-01-01,2026-12-31,,,,,仅填写基础资料\n'
        )
        data = ('\ufeff' + csv_text).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="basic_info_template.csv"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
