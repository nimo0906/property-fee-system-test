#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP route dispatch for backend pages."""

import re
import urllib.parse

from server.db import qs
from server.permissions import required_post_role, role_allows

DISABLED_MODULE_PATTERNS = (
    r'^/repairs(?:/.*)?$',
    r'^/parking(?:/.*)?$',
    r'^/deposits(?:/.*)?$',
)


def _is_disabled_module_path(path):
    return any(re.match(pattern, path) for pattern in DISABLED_MODULE_PATTERNS)


READONLY_GET_ALLOWED = (
    r'^/$',
    r'^/owners$',
    r'^/rooms$',
    r'^/bills(?:/.*)?$',
    r'^/collections(?:/.*)?$',
    r'^/reminders(?:/.*)?$',
    r'^/reports(?:/.*)?$',
    r'^/logout$',
)


OPERATOR_GET_BLOCKED = (
    r'^/backups(?:/.*)?$',
    r'^/audit_logs$',
    r'^/system_health(?:/.*)?$',
    r'^/system_update(?:/.*)?$',
    r'^/trial_data_reset$',
    r'^/users(?:/.*)?$',
)


MANAGER_GET_BLOCKED = (
    r'^/backups(?:/.*)?$',
    r'^/audit_logs$',
    r'^/system_health(?:/.*)?$',
    r'^/system_update(?:/.*)?$',
    r'^/trial_data_reset$',
)


def _role_blocks_get(role, path):
    if role == 'readonly':
        return not any(re.match(pattern, path) for pattern in READONLY_GET_ALLOWED)
    if role == 'operator':
        return any(re.match(pattern, path) for pattern in OPERATOR_GET_BLOCKED)
    if role == 'manager':
        return any(re.match(pattern, path) for pattern in MANAGER_GET_BLOCKED)
    return False


# ── GET routing ────────────────────────────────────────────
def handle_get(handler):
    p = urllib.parse.urlparse(handler.path).path
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    if _is_disabled_module_path(p):
        return handler._error(404)
    if p.startswith('/api/v1/'):
        return handler._api_get(p)
    if p.startswith('/owner-portal/') or p == '/owner-portal':
        return handler._error(404)
    if p not in ('/login', '/logout', '/register') and not p.startswith('/static/'):
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        if _role_blocks_get(u.get('role'), p):
            return handler._redirect('/?flash=无权限访问该页面')
    if p == '/login': return handler._login()
    elif p == '/register': return handler._register()
    elif p == '/logout': return handler._logout()
    elif p == '/': return handler._index()
    elif p == '/rooms': return handler._rooms(q)
    elif p == '/late_fee_config': return handler._late_fee_config()
    elif p == '/rooms/create': return handler._room_form(None)
    elif (m := re.match(r'^/rooms/(\d+)/edit$', p)): return handler._room_form(int(m.group(1)))
    elif p == '/owners': return handler._owners(q)
    elif p == '/owners/create': return handler._owner_form(None)
    elif (m := re.match(r'^/owners/(\d+)/edit$', p)): return handler._owner_form(int(m.group(1)))
    elif p == '/fee_types': return handler._fee_types()
    elif p == '/batch_ops': return handler._batch_ops(q)
    elif p == '/fee_types/create': return handler._fee_type_form(None, qs(q, 'group'))
    elif p == '/elevator_tiers': return handler._elevator_tiers()
    elif (m := re.match(r'^/fee_types/(\d+)/edit$', p)): return handler._fee_type_form(int(m.group(1)))
    elif p == '/meter_readings': return handler._meter_list(q)
    elif p == '/meter_readings/create': return handler._meter_form()
    elif p == '/repairs': return handler._repairs(q)
    elif p == '/repairs/create': return handler._repair_form(None)
    elif (m := re.match(r'^/repairs/(\d+)$', p)): return handler._repair_detail(int(m.group(1)))
    elif p == '/invoices': return handler._invoices(q)
    elif p == '/invoice_requests': return handler._invoice_requests(q)
    elif (m := re.match(r'^/invoices/(\d+)/print$', p)): return handler._invoice_print(int(m.group(1)))
    elif p == '/deposits': return handler._deposits(q)
    elif p == '/deposits/create': return handler._deposit_form(None)
    elif (m := re.match(r'^/deposits/(\d+)/edit$', p)): return handler._deposit_form(int(m.group(1)))
    elif (m := re.match(r'^/deposits/(\d+)/refund$', p)): return handler._deposit_refund(int(m.group(1)))
    elif p == '/parking': return handler._parking(q)
    elif p == '/parking/create': return handler._parking_form(None)
    elif (m := re.match(r'^/parking/(\d+)/edit$', p)): return handler._parking_form(int(m.group(1)))
    elif p == '/reminders': return handler._reminders(q)
    elif p == '/collections': return handler._collections(q)
    elif p == '/reminders/print': return handler._reminder_print(q)
    elif p == '/billing': return handler._billing()
    elif p == '/billing/calc': return handler._redirect('/billing?flash=请从收费页面选择房间和费用后生成账单')
    elif p == '/commercial_billing': return handler._commercial_billing()
    elif p == '/auto_billing': return handler._auto_billing(q)
    elif (m := re.match(r'^/auto_billing/runs/([^/]+)$', p)): return handler._auto_billing_run_detail(m.group(1))
    elif p == '/shared_expenses': return handler._shared_expenses(q)
    elif p == '/bills': return handler._bills(q)
    elif p == '/bills/review': return handler._bills_review(q)
    elif p == '/bills/generate': return handler._bill_gen(q)
    elif p == '/bills/export': return handler._bill_export()
    elif p == '/bills/export_generated': return handler._bill_export_generated(q)
    elif (m := re.match(r'^/bills/(\d+)$', p)): return handler._bill_detail(int(m.group(1)), q)
    elif (m := re.match(r'^/bills/(\d+)/print$', p)): return handler._bill_print(int(m.group(1)))
    elif (m := re.match(r'^/bills/(\d+)/pay$', p)): return handler._bill_pay(int(m.group(1)))
    elif (m := re.match(r'^/bills/(\d+)/edit$', p)): return handler._bill_edit(int(m.group(1)))
    elif p == '/bills/print_batch': return handler._bill_print_batch(q)
    elif p == '/bills/receipt': return handler._bill_receipt(q)
    elif p == '/bills/receipt_setup': return handler._receipt_setup(q)
    elif p == '/bills/export_receipt': return handler._export_receipt(q)
    elif p == '/payments': return handler._payments(q)
    elif p == '/payments/export.csv': return handler._payments_csv(q)
    elif p == '/users': return handler._users()
    elif p == '/users/create': return handler._user_form(None)
    elif (m := re.match(r'^/users/(\d+)/edit$', p)): return handler._user_form(int(m.group(1)))
    elif p == '/import': return handler._import_page()
    elif p == '/import/template/basic.csv': return handler._basic_import_template()
    elif (m := re.match(r'^/import/problem_rows/([A-Za-z0-9_-]+)\.csv$', p)): return handler._import_problem_rows_download(m.group(1))
    elif (m := re.match(r'^/import/fee_mapping/([A-Za-z0-9_-]+)\.csv$', p)): return handler._fee_mapping_csv_download(m.group(1))
    elif p == '/audit_logs': return handler._audit_logs(q)
    elif p == '/audit_logs/export.csv': return handler._audit_logs_csv(q)
    elif p == '/backups': return handler._backups(q)
    elif p == '/system_health': return handler._system_health(q)
    elif p == '/system_update': return handler._system_update(q)
    elif p == '/trial_data_reset': return handler._trial_data_reset(q)
    elif p == '/backups/cleanup': return handler._backup_cleanup_preview(q)
    elif (m := re.match(r'^/backups/(.+)/preview$', p)): return handler._backup_preview(m.group(1))
    elif (m := re.match(r'^/backups/(.+)/restore$', p)): return handler._backup_restore_confirm(m.group(1))
    elif (m := re.match(r'^/backups/(.+)/delete$', p)): return handler._backup_delete_confirm(m.group(1))
    elif p == '/closing': return handler._closing()
    elif p == '/closing/reopen': return handler._closing_reopen_confirm(q)
    elif p == '/export/kingdee': return handler._export_kingdee(q)
    elif p == '/reports': return handler._reports(q)
    elif p == '/reports/reconciliation.csv': return handler._reports_reconciliation_csv(q)
    elif p == '/reports/collections.csv': return handler._reports_collections_csv(q)
    elif p == '/reports/tenants.csv': return handler._reports_tenants_csv(q)
    elif p == '/reports/tenant_arrears.csv': return handler._reports_tenant_arrears_csv(q)
    elif p == '/reports/reconciliation/print': return handler._reports_reconciliation_print(q)
    elif (m := re.match(r'^/api/rooms/(\d+)/meter/(\d+)$', p)):
        return handler._api_meter(int(m.group(1)), int(m.group(2)))
    elif (m := re.match(r'^/api/owners/(\d+)/info$', p)): return handler._api_owner_info(int(m.group(1)))
    elif p == '/api/search_rooms': return handler._api_search_rooms(q)
    elif p == '/api/search_owners': return handler._api_search_owners(q)
    elif p.startswith('/static/'): return handler._serve_static(p)
    elif p == '/api/stats': return handler._api_stats()
    else: handler._error(404)

# ── POST routing ───────────────────────────────────────────
def handle_post(handler):
    p = urllib.parse.urlparse(handler.path).path
    if _is_disabled_module_path(p):
        return handler._error(404)
    if p.startswith('/api/v1/'):
        return handler._api_post(p, handler._post())
    if p.startswith('/owner-portal/') or p == '/owner-portal':
        return handler._error(404)
    # 文件上传不经过 _post()（multipart 由 _import_upload 自行解析）
    if p == '/import/upload':
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        if u.get('role') == 'readonly':
            return handler._redirect('/?flash=无权限执行写操作')
        required_role = required_post_role(p)
        if not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限执行该操作')
        return handler._import_upload()
    d = handler._post()
    u = None
    if p not in ('/login', '/register'):
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        if u.get('role') == 'readonly':
            return handler._redirect('/?flash=无权限执行写操作')
        required_role = required_post_role(p)
        if not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限执行该操作')
    if p == '/login': return handler._login_post(d)
    elif p == '/register': return handler._register_post(d)
    elif p == '/rooms/create': return handler._room_create(d)
    elif (m := re.match(r'^/rooms/(\d+)/edit$', p)): return handler._room_edit(int(m.group(1)), d)
    elif p == '/late_fee_config/update': return handler._late_fee_config_update(d)
    elif p == '/rooms/batch_delete': return handler._room_batch_delete(d)
    elif (m := re.match(r'^/rooms/(\d+)/delete$', p)): return handler._room_delete(int(m.group(1)))
    elif p == '/owners/create': return handler._owner_create(d)
    elif (m := re.match(r'^/owners/(\d+)/edit$', p)): return handler._owner_edit(int(m.group(1)), d)
    elif (m := re.match(r'^/owners/(\d+)/delete$', p)): return handler._owner_delete(int(m.group(1)))
    elif p == '/fee_types/create': return handler._fee_type_create(d)
    elif p == '/batch_ops/room_rate': return handler._batch_room_rate(d)
    elif p == '/batch_ops/fee_rate': return handler._batch_fee_rate(d)
    elif p == '/elevator_tiers/update': return handler._elevator_tiers_update(d)
    elif (m := re.match(r'^/fee_types/(\d+)/edit$', p)): return handler._fee_type_edit(int(m.group(1)), d)
    elif (m := re.match(r'^/fee_types/(\d+)/delete$', p)): return handler._fee_type_delete(int(m.group(1)), d)
    elif p == '/meter_readings/create': return handler._meter_create(d)
    elif (m := re.match(r'^/meter_readings/(\d+)/confirm$', p)): return handler._meter_confirm(int(m.group(1)))
    elif (m := re.match(r'^/meter_readings/(\d+)/delete$', p)): return handler._meter_delete(int(m.group(1)))
    elif p == '/invoices/create': return handler._invoice_create(d)
    elif (m := re.match(r'^/invoice_requests/([^/]+)/status$', p)): return handler._invoice_request_status_post(m.group(1), d)
    elif (m := re.match(r'^/invoices/(\d+)/delete$', p)): return handler._invoice_delete(int(m.group(1)))
    elif p == '/deposits/create': return handler._deposit_create(d)
    elif (m := re.match(r'^/deposits/(\d+)/edit$', p)): return handler._deposit_edit(int(m.group(1)), d)
    elif (m := re.match(r'^/deposits/(\d+)/refund$', p)): return handler._deposit_refund_post(int(m.group(1)), d)
    elif (m := re.match(r'^/deposits/(\d+)/delete$', p)): return handler._deposit_delete(int(m.group(1)))
    elif p == '/parking/create': return handler._parking_create(d)
    elif (m := re.match(r'^/parking/(\d+)/edit$', p)): return handler._parking_edit(int(m.group(1)), d)
    elif (m := re.match(r'^/parking/(\d+)/delete$', p)): return handler._parking_delete(int(m.group(1)))
    elif p == '/repairs/create': return handler._repair_create(d)
    elif (m := re.match(r'^/repairs/(\d+)/status$', p)): return handler._repair_status(int(m.group(1)), d)
    elif (m := re.match(r'^/repairs/(\d+)/delete$', p)): return handler._repair_delete(int(m.group(1)))
    elif p == '/billing/calc': return handler._billing_calc(d)
    elif p == '/auto_billing/confirm': return handler._auto_billing_confirm(d)
    elif (m := re.match(r'^/auto_billing/runs/([^/]+)/rollback$', p)): return handler._auto_billing_rollback(m.group(1))
    elif p == '/payments/print': return handler._payments_print(d)
    elif p == '/payments/receipts': return handler._payment_receipts(d)
    elif p == '/shared_expenses/allocate': return handler._shared_expense_allocate(d)
    elif p == '/bills/generate': return handler._bill_generate(d)
    elif p == '/bills/undo_generated': return handler._bill_undo_generated(d)
    elif (m := re.match(r'^/bills/(\d+)/pay$', p)): return handler._bill_pay_post(int(m.group(1)), d)
    elif (m := re.match(r'^/bills/(\d+)/edit$', p)): return handler._bill_edit_post(int(m.group(1)), d)
    elif (m := re.match(r'^/bills/(\d+)/delete$', p)): return handler._bill_delete(int(m.group(1)), d)
    elif p == '/users/create': return handler._user_create(d)
    elif (m := re.match(r'^/users/(\d+)/edit$', p)): return handler._user_edit(int(m.group(1)), d)
    elif (m := re.match(r'^/users/(\d+)/delete$', p)): return handler._user_delete(int(m.group(1)))
    elif p == '/system_health/repair': return handler._system_health_repair(d)
    elif p == '/system_update/check': return handler._system_update_check(d)
    elif p == '/system_update/prepare': return handler._system_update_prepare(d)
    elif p == '/system_update/open_folder': return handler._system_update_open_folder()
    elif p == '/trial_data_reset': return handler._trial_data_reset_post(d)
    elif p == '/audit_logs/delete': return handler._audit_logs_delete(d)
    elif p == '/backups/create': return handler._backup_create()
    elif p == '/backups/cleanup': return handler._backup_cleanup_apply(d)
    elif (m := re.match(r'^/backups/(.+)/restore$', p)): return handler._backup_restore(m.group(1))
    elif (m := re.match(r'^/backups/(.+)/delete$', p)): return handler._backup_delete(m.group(1))
    elif p == '/closing/close': return handler._closing_close(d)
    elif p == '/closing/reopen': return handler._closing_reopen(d)
    elif p == '/bills/batch_pay': return handler._batch_pay(d)
    elif p == '/bills/batch_edit': return handler._bill_batch_edit(d)
    elif p == '/bills/batch_edit/preview': return handler._bill_batch_edit_preview(d)
    elif p == '/bills/batch_edit/apply': return handler._bill_batch_edit_apply(d)
    elif p == '/bills/export_selected': return handler._export_selected(d)
    elif p == '/bills/receipt_by_ids': return handler._receipt_by_ids(d)
    elif p == '/bills/print_selected': return handler._print_selected(d)
    else: handler._error(404)
