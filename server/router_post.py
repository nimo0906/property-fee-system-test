#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP route dispatch for backend pages."""

import re
import urllib.parse

from server.db import qs
from server.commercial_config import license_block_message, should_block_for_license, should_force_first_run
from server.license_status import read_license_status
from server.permissions import canonical_role, is_readonly_role, required_get_role, required_post_role, role_allows

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

CUSTOMER_SERVICE_GET_ALLOWED = (
    r'^/$',
    r'^/owners(?:/create|/\d+/edit)?$',
    r'^/rooms(?:/create|/\d+/(?:edit|tenant_transfer))?$',
    r'^/bills(?:/.*)?$',
    r'^/collections(?:/.*)?$',
    r'^/reminders(?:/.*)?$',
    r'^/reports(?:/.*)?$',
    r'^/meter_readings(?:/ledger|/create)?$',
    r'^/merchant_contracts(?:$|/create$|/import$|/\d+$|/\d+/(?:edit|renew|deactivate|transfer)$|/\d+/attachments/\d+/download$)',
    r'^/commercial_spaces(?:$|/create$|/\d+/edit$)',
    r'^/import(?:/.*)?$',
    r'^/logout$',
)


OPERATOR_GET_BLOCKED = (
    r'^/backups(?:/.*)?$',
    r'^/audit_logs$',
    r'^/system_health(?:/.*)?$',
    r'^/system_update(?:/.*)?$',
    r'^/trial_data_reset$',
    r'^/users(?:/.*)?$',
    r'^/cloud_schema$',
    r'^/delivery_center(?:/.*)?$',
)


MANAGER_GET_BLOCKED = (
    r'^/backups(?:/.*)?$',
    r'^/audit_logs$',
    r'^/system_health(?:/.*)?$',
    r'^/system_update(?:/.*)?$',
    r'^/trial_data_reset$',
    r'^/cloud_schema$',
)


def _role_blocks_get(role, path):
    role = canonical_role(role)
    if role == 'readonly':
        return not any(re.match(pattern, path) for pattern in READONLY_GET_ALLOWED)
    if role == 'frontdesk':
        return not any(re.match(pattern, path) for pattern in CUSTOMER_SERVICE_GET_ALLOWED)
    if role == 'operator':
        return any(re.match(pattern, path) for pattern in OPERATOR_GET_BLOCKED)
    if role == 'manager':
        return any(re.match(pattern, path) for pattern in MANAGER_GET_BLOCKED)
    return False


# ── GET routing ────────────────────────────────────────────
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
        license_status = read_license_status()
        if should_block_for_license(p, u, license_status):
            return handler._redirect('/license_status?flash=' + license_block_message(license_status))
        if should_force_first_run(p, u):
            return handler._redirect('/first_run_guide?flash=请先完成首次初始化配置')
        if is_readonly_role(u.get('role')):
            return handler._redirect('/?flash=无权限执行写操作')
        required_role = required_post_role(p)
        if not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限执行该操作')
        return handler._import_upload()
    if p == '/merchant_contracts/import':
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        license_status = read_license_status()
        if should_block_for_license(p, u, license_status):
            return handler._redirect('/license_status?flash=' + license_block_message(license_status))
        if should_force_first_run(p, u):
            return handler._redirect('/first_run_guide?flash=请先完成首次初始化配置')
        if is_readonly_role(u.get('role')):
            return handler._redirect('/?flash=无权限执行写操作')
        required_role = required_post_role(p)
        if not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限执行该操作')
        return handler._merchant_contract_import_preview()
    if (m := re.match(r'^/merchant_contracts/(\d+)/attachments$', p)):
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        license_status = read_license_status()
        if should_block_for_license(p, u, license_status):
            return handler._redirect('/license_status?flash=' + license_block_message(license_status))
        if should_force_first_run(p, u):
            return handler._redirect('/first_run_guide?flash=请先完成首次初始化配置')
        if is_readonly_role(u.get('role')):
            return handler._redirect('/?flash=无权限执行写操作')
        required_role = required_post_role(p)
        if not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限执行该操作')
        return handler._merchant_contract_attachment_upload(int(m.group(1)))
    if (m := re.match(r'^/merchant_contracts/(\d+)/(renew|deactivate)$', p)) and handler.headers.get('Content-Type', '').startswith('multipart/form-data'):
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        license_status = read_license_status()
        if should_block_for_license(p, u, license_status):
            return handler._redirect('/license_status?flash=' + license_block_message(license_status))
        if should_force_first_run(p, u):
            return handler._redirect('/first_run_guide?flash=请先完成首次初始化配置')
        if is_readonly_role(u.get('role')):
            return handler._redirect('/?flash=无权限执行写操作')
        required_role = required_post_role(p)
        if not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限执行该操作')
        if m.group(2) == 'renew':
            return handler._merchant_contract_renew_post_multipart(int(m.group(1)))
        return handler._merchant_contract_deactivate_multipart(int(m.group(1)))
    d = handler._post()
    u = None
    if p not in ('/login', '/register'):
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        license_status = read_license_status()
        if should_block_for_license(p, u, license_status):
            return handler._redirect('/license_status?flash=' + license_block_message(license_status))
        if should_force_first_run(p, u):
            return handler._redirect('/first_run_guide?flash=请先完成首次初始化配置')
        if is_readonly_role(u.get('role')):
            return handler._redirect('/?flash=无权限执行写操作')
        required_role = required_post_role(p)
        if not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限执行该操作')
    if p == '/login': return handler._login_post(d)
    elif p == '/register': return handler._register_post(d)
    elif p == '/first_run_setup': return handler._first_run_setup_post(d)
    elif p == '/rooms/create': return handler._room_create(d)
    elif (m := re.match(r'^/rooms/(\d+)/edit$', p)): return handler._room_edit(int(m.group(1)), d)
    elif (m := re.match(r'^/rooms/(\d+)/tenant_transfer$', p)): return handler._room_tenant_transfer_post(int(m.group(1)), d)
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
    elif p == '/meter_readings/ledger/save': return handler._meter_ledger_save(d)
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
    elif p == '/commercial_spaces/create': return handler._commercial_space_create(d)
    elif (m := re.match(r'^/commercial_spaces/(\d+)/edit$', p)): return handler._commercial_space_edit(int(m.group(1)), d)
    elif p == '/commercial_receivables/confirm': return handler._commercial_receivables_confirm(d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/attachments/(\d+)/recognize$', p)): return handler._contract_amendment_recognize(int(m.group(1)), int(m.group(2)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/amendments/(\d+)/confirm$', p)): return handler._contract_amendment_confirm(int(m.group(1)), int(m.group(2)), d)
    elif p == '/merchant_contracts/create': return handler._merchant_contract_create(d)
    elif p == '/merchant_contracts/import/confirm': return handler._merchant_contract_import_confirm(d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/edit$', p)): return handler._merchant_contract_edit_post(int(m.group(1)), d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/delete$', p)): return handler._merchant_contract_delete(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/renew$', p)): return handler._merchant_contract_renew_post(int(m.group(1)), d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/deactivate$', p)): return handler._merchant_contract_deactivate(int(m.group(1)), d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/transfer$', p)): return handler._merchant_contract_transfer_post(int(m.group(1)), d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/turnover_rent$', p)): return handler._merchant_contract_turnover_rent_post(int(m.group(1)), d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/billing/confirm$', p)): return handler._merchant_contract_billing_confirm(int(m.group(1)), d)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/generate$', p)): return handler._merchant_contract_generate(int(m.group(1)), d)
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
    elif (m := re.match(r'^/backups/(.+)/restore$', p)): return handler._backup_restore(m.group(1), d)
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
