from server.import_views_helpers import *
from server.basic_import import _normalize_payment_cycle
from server.import_batching import continuation_from_form

class ImportViewMixinPart1:
    def _confirm_preview_rows(self, form):
        """Write user-edited preview rows only after explicit confirmation."""
        from server.backups import create_db_backup
        from server.db import get_db

        data_type = form.getvalue('data_type', 'rooms')
        filename = form.getvalue('filename', '')
        try:
            count = int(form.getvalue('preview_row_count', '0') or 0)
        except ValueError:
            count = 0
        try:
            backup_name = create_db_backup('auto_before_import')
        except FileNotFoundError:
            return self._redirect('/import?flash=数据库文件不存在，未执行导入')

        db = get_db()
        result = self._simple_import_result()
        changed_rooms = []
        try:
            for i in range(count):
                room_number = _form_value(form, f'row_{i}_room_number', '').strip()
                if not room_number:
                    result['skipped'] += 1
                    result['problem_rows'].append({'row_no': i + 1, 'reason': '缺少房号', 'raw': ''})
                    continue
                building = _form_value(form, f'row_{i}_building', '').strip() or '商场'
                unit = _form_value(form, f'row_{i}_unit', '').strip() or ('商场' if building == '商场' else 'A座')
                category = _form_value(form, f'row_{i}_category', '').strip() or '商户'
                floor = _safe_int(_form_value(form, f'row_{i}_floor', '1'), 1)
                area = _safe_float(_form_value(form, f'row_{i}_area', '0'), 0)
                owner_name = _form_value(form, f'row_{i}_owner_name', '').strip()
                owner_phone = _form_value(form, f'row_{i}_owner_phone', '').strip()
                contract_start = _form_value(form, f'row_{i}_contract_start', '').strip()
                contract_end = _form_value(form, f'row_{i}_contract_end', '').strip()
                custom_rate_text = _form_value(form, f'row_{i}_custom_rate', '').strip()
                custom_rate = _safe_float(custom_rate_text, None) if custom_rate_text else None
                raw_payment_cycle = _form_value(form, f'row_{i}_payment_cycle', '').strip()
                payment_cycle = _normalize_payment_cycle(raw_payment_cycle) or raw_payment_cycle
                business_type = _form_value(form, f'row_{i}_business_type', '').strip()
                shop_name = _form_value(form, f'row_{i}_shop_name', '').strip()
                tenant_name = _form_value(form, f'row_{i}_tenant_name', '').strip()
                notes = _form_value(form, f'row_{i}_notes', '').strip()

                owner_id = None
                if owner_name:
                    owner = db.execute('SELECT id,phone FROM owners WHERE name=? LIMIT 1', (owner_name,)).fetchone()
                    if owner:
                        owner_id = owner['id']
                        if owner_phone and not owner['phone']:
                            db.execute('UPDATE owners SET phone=? WHERE id=?', (owner_phone, owner_id))
                    else:
                        cur = db.execute('INSERT INTO owners(name,phone) VALUES(?,?)', (owner_name, owner_phone))
                        owner_id = cur.lastrowid
                        result['imported_owners'] += 1

                room = db.execute('SELECT * FROM rooms WHERE building=? AND room_number=? LIMIT 1', (building, room_number)).fetchone()
                if room:
                    db.execute(
                        """UPDATE rooms SET unit=?,floor=?,category=?,area=?,owner_id=COALESCE(?,owner_id),
                           contract_start=?,contract_end=?,business_type=COALESCE(NULLIF(?,''),business_type),
                           shop_name=COALESCE(NULLIF(?,''),shop_name),tenant_name=COALESCE(NULLIF(?,''),tenant_name),custom_rate=COALESCE(?,custom_rate),
                           payment_cycle=COALESCE(NULLIF(?,''),payment_cycle),notes=? WHERE id=?""",
                        (unit, floor, category, area, owner_id, contract_start, contract_end, business_type, shop_name, tenant_name, custom_rate, payment_cycle, notes, room['id'])
                    )
                    result['updated_rooms'] += 1
                    action = '更新'
                    room_id = room['id']
                else:
                    cur = db.execute(
                        """INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,contract_start,contract_end,business_type,shop_name,tenant_name,custom_rate,payment_cycle,notes)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (building, unit, room_number, floor, category, area, owner_id, contract_start, contract_end, business_type, shop_name, tenant_name, custom_rate, payment_cycle, notes)
                    )
                    result['imported_rooms'] += 1
                    action = '新增'
                    room_id = cur.lastrowid

                changed_rooms.append({
                    'action': action, 'room_id': room_id, 'building': building,
                    'unit': unit, 'room_number': room_number, 'floor': floor, 'area': area,
                    'owner_name': owner_name, 'owner_phone': owner_phone,
                    'contract_start': contract_start, 'contract_end': contract_end,
                    'business_type': business_type, 'shop_name': shop_name, 'tenant_name': tenant_name,
                    'custom_rate': custom_rate, 'payment_cycle': payment_cycle, 'notes': notes, 'category': category,
                })
            result['changed_rooms'] = changed_rooms
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        self._audit('data_import_preview_confirm', 'import', None, None, {'filename': filename, 'data_type': data_type, 'rows': count, 'result': result, 'backup': backup_name}, '预览页编辑确认导入')
        return self._render_import_result(filename, data_type, count, backup_name, result, continuation_from_form(form))

    def _simple_import_result(self, imported_rooms=0, updated_rooms=0, imported_owners=0, skipped=0, errors=None):
        return {
            'imported_rooms': imported_rooms,
            'updated_rooms': updated_rooms,
            'imported_owners': imported_owners,
            'skipped': skipped,
            'errors': errors or [],
            'invalid_contracts': [],
            'skip_examples': [],
            'changed_rooms': [],
            'problem_rows': [],
        }

    def _render_import_result(self, filename, data_type, total_rows, backup_name, result, continuation=None):
        type_names = {
            'owners': '业主信息',
            'rooms': '房间基础资料',
            'bills': '账单记录',
            'payment_ledger': '收款明细表基础资料',
        }
        skip_examples = ''.join(f'<li>{h(x)}</li>' for x in result.get('skip_examples', [])[:20])
        invalid_contracts = ''.join(f'<li>{h(x)}</li>' for x in result.get('invalid_contracts', [])[:20])
        errors = ''.join(f'<li>{h(x)}</li>' for x in result.get('errors', [])[:20])
        problem_rows = result.get('problem_rows', [])
        problem_csv_token = self._save_problem_rows_csv(problem_rows)
        problem_rows_html = self._render_problem_rows(problem_rows, problem_csv_token)
        billing_next_html = ''
        continue_action = '<a href="/import" class="btn btn-primary">继续导入其他文件</a>'
        if continuation:
            continue_action = f'''<form method="POST" action="/import/upload" class="d-inline">
                <input type="hidden" name="mode" value="preview">
                <input type="hidden" name="data_type" value="{h(continuation['data_type'])}">
                <input type="hidden" name="filename" value="{h(continuation['filename'])}">
                <input type="hidden" name="upload_token" value="{h(continuation['upload_token'])}">
                <input type="hidden" name="import_offset" value="{continuation['next_offset']}">
                <button class="btn btn-primary">继续导入后续数据</button>
            </form>
            <a href="/import" class="btn btn-outline-secondary">继续导入其他文件</a>'''
        amount_note = '本次只处理基础资料；历史收款流水和金额不会自动入账，需要用户后续核对确认。'
        if data_type == 'bills':
            amount_note = '账单字段已按本次确认导入；收款流水和历史实收金额仍需用户后续核对确认。'
        self._html(self._page('导入结果', f'''
        <div class="import-hero import-hero-pro">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
                <div>
                    <div class="page-kicker">IMPORT RESULT</div>
                    <h4 class="mb-2">导入结果复核</h4>
                    <p class="mb-0 text-muted">处理完成。系统已在写入前创建自动备份，历史金额不会自动入账。</p>
                </div>
                <span class="badge status-success fs-6 px-3 py-2">已创建备份</span>
            </div>
        </div>
        <div class="alert alert-warning">
            <strong>未导入历史金额。</strong>{h(amount_note)}
        </div>
        <div class="card import-file-card mb-3"><div class="card-body">
            <div class="row g-3 align-items-center">
                <div class="col-md-4"><span class="text-muted small">文件</span><div class="fw-bold">{h(filename)}</div></div>
                <div class="col-md-3"><span class="text-muted small">类型</span><div class="fw-bold">{h(type_names.get(data_type, data_type))}</div></div>
                <div class="col-md-2"><span class="text-muted small">数据行</span><div class="fw-bold">{total_rows} 行</div></div>
                <div class="col-md-3"><span class="text-muted small">自动备份</span><div><code>{h(backup_name)}</code></div></div>
            </div>
        </div></div>
        <div class="row text-center g-2 mb-3">
        <div class="col-md-3"><div class="summary-tile success"><div class="label">新增房间</div><strong>{result.get('imported_rooms', 0)}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile"><div class="label">更新房间</div><strong>{result.get('updated_rooms', 0)}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile"><div class="label">新增业主</div><strong>{result.get('imported_owners', 0)}</strong></div></div>
        <div class="col-md-3"><div class="summary-tile warning"><div class="label">跳过行数</div><strong>{result.get('skipped', 0)}</strong></div></div>
        </div>
        <div class="card mb-3 import-review-card"><div class="card-header"><i class="bi bi-exclamation-diamond"></i> 异常和跳过明细</div>
        <div class="card-body">
        <h6>跳过示例</h6><ul>{skip_examples or '<li class="text-muted">无</li>'}</ul>
        <h6>合同日期异常</h6><ul>{invalid_contracts or '<li class="text-muted">无</li>'}</ul>
        <h6>处理错误</h6><ul>{errors or '<li class="text-muted">无</li>'}</ul>
        </div></div>
        {problem_rows_html}
        {billing_next_html}
        <div class="batch-bar">
            {continue_action}
            <a href="/backups" class="btn btn-outline-secondary">查看备份</a>
            <a href="/rooms" class="btn btn-outline-secondary">查看房间</a>
            <form method="POST" action="/backups/{h(backup_name)}/restore" class="d-inline"
                  onsubmit="return confirm('撤销本次导入会把数据库恢复到导入前状态，当前导入后的改动都会被覆盖。确定撤销？')">
                <button class="btn btn-outline-danger">撤销本次导入</button>
            </form>
        </div>
        ''', 'import'))
