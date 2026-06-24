from server.import_data_shared import *
from server.import_batching import parse_nonnegative_int
from server.bill_snapshots import room_snapshot, apply_snapshot
from server.money import money_float

class ImportMixinPart2(BaseHandler):
    def _import_upload(self, form=None):
        """处理上传文件并导入数据（校验格式和大小后解析）"""
        if form is None:
            try:
                form = parse_form_data(self.rfile, self.headers)
            except:
                return self._redirect("/import?flash=文件解析失败")
        mode = form.getvalue("mode", "preview")
        if mode == "confirm_preview_rows":
            return self._confirm_preview_rows(form)
        if mode == "confirm_commercial_contracts":
            return self._merchant_contract_import_confirm(form)
        if mode == "confirm_b_tower_contracts":
            return self._confirm_b_tower_contract_import(form)
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
        allow_create_rooms = form.getvalue("allow_create_rooms") == "1"
        import_offset = parse_nonnegative_int(form.getvalue("import_offset", "0"), 0)

        # ── 文件校验 ────────────────────────────────────────────
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return self._redirect(f"/import?flash=不支持的文件格式 {ext}，仅支持 .csv/.xlsx/.xls")
        if len(raw_data) > MAX_UPLOAD_SIZE:
            max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
            return self._redirect(f"/import?flash=文件过大（{len(raw_data)/1024/1024:.1f}MB），最大 {max_mb}MB")
        if data_type == "commercial_contracts" or (data_type == "auto" and _has_commercial_contract_sheet(filename, raw_data)):
            data_type = "commercial_contracts"
            try:
                contract_rows = load_commercial_contract_rows(filename, raw_data)
            except Exception as e:
                return self._redirect(f"/import?flash=合同文件解析失败: {str(e)}")
            token = save_import_file(raw_data)
            return render_contract_import_preview(self, filename, token, contract_rows)
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
        if mode in ("import", "preview"):
            col_map = self._col_map_from_form(form, col_map, len(headers))
        if not col_map:
            return self._redirect("/import?flash=未能识别列头")
        if data_type == "auto":
            if looks_like_b_tower_contract(headers, data_rows):
                data_type = "b_tower_contracts"
            else:
                data_type = detect_data_type(col_map, headers)
        if data_type == "b_tower_contracts":
            contract_rows = parse_b_tower_contract_rows(headers, data_rows)
            token = save_import_file(raw_data)
            return render_b_tower_contract_preview(self, filename, token, contract_rows, allow_create_rooms)
        if mode == "confirm_fee_mapping" and data_type == "payment_ledger":
            return self._render_fee_mapping_result(filename, headers, data_rows, form)
        if mode == "preview" or data_type == "unknown":
            upload_token = upload_token or save_import_file(raw_data)
            return self._render_import_preview(
                filename, headers, data_rows, col_map, data_type, header_idx, upload_token, import_offset
            )
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
            elif data_type == "b_tower_contracts":
                contract_rows = parse_b_tower_contract_rows(headers, data_rows)
                result = import_b_tower_contract_rows(db, contract_rows, allow_create_rooms)
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
                        amount = money_float(gc('amount', '0'))
                        status = gc('status', 'unpaid')
                        paid_amount = money_float(gc('paid_amount', '0'))
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
                        cur = db.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)",
                                   (room[0], room[1], ft[0], period, amount, status, bn))
                        apply_snapshot(db, cur.lastrowid, room_snapshot(db, room[0], room[1]))
                        imported += 1
                        # Import payment if paid
                        if paid_amount > 0 and payment_date:
                            bid = cur.lastrowid
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

    def _confirm_b_tower_contract_import(self, form):
        try:
            backup_name = create_db_backup('auto_before_b_tower_contract_import')
        except FileNotFoundError:
            return self._redirect('/import?data_type=b_tower_contracts&flash=数据库文件不存在，未执行导入')
        rows = rows_from_b_tower_form(form)
        allow_create = form.getvalue('allow_create_rooms') == '1'
        db = get_db()
        try:
            result = import_b_tower_contract_rows(db, rows, allow_create)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        filename = form.getvalue('filename', 'b_tower_contracts.xlsx')
        self._audit('b_tower_contract_import', 'rooms', None, None, {'filename': filename, 'rows': len(rows), 'allow_create': allow_create, 'result': result, 'backup': backup_name}, 'B座出租合同导入')
        return self._render_import_result(filename, 'b_tower_contracts', len(rows), backup_name, result)
