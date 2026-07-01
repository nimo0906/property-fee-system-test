#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP route dispatch for backend pages."""

import re
import urllib.parse

from server.db import qs
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
def handle_get(handler):
    p = urllib.parse.urlparse(handler.path).path
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    if _is_disabled_module_path(p):
        return handler._error(404)
    if p == '/health':
        return handler._json({'ok': True, 'service': 'property-fee-system'})
    if p.startswith('/api/v1/'):
        return handler._api_get(p)
    if p.startswith('/owner-portal/') or p == '/owner-portal':
        return handler._error(404)
    if p not in ('/login', '/logout', '/register') and not p.startswith('/static/'):
        u = handler._get_current_user()
        if not u:
            return handler._redirect('/login')
        required_role = required_get_role(p)
        if required_role and not role_allows(u.get('role'), required_role):
            return handler._redirect('/?flash=无权限访问该页面')
        if _role_blocks_get(u.get('role'), p):
            return handler._redirect('/?flash=无权限访问该页面')
    if p == '/login': return handler._login()
    elif p == '/register': return handler._register()
    elif p == '/logout': return handler._logout()
    elif p == '/': return handler._index()
    elif p == '/rooms': return handler._rooms(q)
    elif p == '/late_fee_config': return handler._late_fee_config()
    elif p == '/rooms/create': return handler._room_form(None)
    elif (m := re.match(r'^/rooms/(\d+)/edit$', p)): return handler._room_form(int(m.group(1)), q)
    elif (m := re.match(r'^/rooms/(\d+)/tenant_transfer$', p)): return handler._room_tenant_transfer_form(int(m.group(1)))
    elif p == '/owners': return handler._owners(q)
    elif p == '/owners/create': return handler._owner_form(None)
    elif (m := re.match(r'^/owners/(\d+)/edit$', p)): return handler._owner_form(int(m.group(1)))
    elif p == '/fee_types': return handler._fee_types()
    elif p == '/batch_ops': return handler._batch_ops(q)
    elif p == '/fee_types/create': return handler._fee_type_form(None, qs(q, 'group'))
    elif p == '/elevator_tiers': return handler._elevator_tiers()
    elif (m := re.match(r'^/fee_types/(\d+)/edit$', p)): return handler._fee_type_form(int(m.group(1)))
    elif p == '/meter_readings': return handler._meter_list(q)
    elif p == '/meter_readings/ledger': return handler._meter_ledger(q)
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
    elif p == '/alert_center': return handler._alert_center(q)
    elif p == '/billing': return handler._billing()
    elif p == '/billing/calc': return handler._redirect('/billing?flash=请从收费页面选择房间和费用后生成账单')
    elif p == '/commercial_billing': return handler._commercial_billing()
    elif p == '/commercial_spaces': return handler._commercial_spaces(q)
    elif p == '/commercial_spaces/create': return handler._commercial_space_form(None)
    elif (m := re.match(r'^/commercial_spaces/(\d+)/edit$', p)): return handler._commercial_space_form(int(m.group(1)))
    elif p == '/merchant_contracts': return handler._merchant_contracts(q)
    elif p == '/merchant_contracts/create': return handler._merchant_contract_form()
    elif p == '/merchant_contracts/import': return handler._merchant_contract_import_form()
    elif (m := re.match(r'^/merchant_contracts/(\d+)$', p)): return handler._merchant_contract_detail(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/edit$', p)): return handler._merchant_contract_edit_form(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/renew$', p)): return handler._merchant_contract_renew_form(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/deactivate$', p)): return handler._merchant_contract_deactivate_form(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/transfer$', p)): return handler._merchant_contract_transfer_form(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/turnover_rent$', p)): return handler._merchant_contract_turnover_rent_form(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/bills$', p)): return handler._merchant_contract_bills(int(m.group(1)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/attachments/(\d+)/download$', p)): return handler._merchant_contract_attachment_download(int(m.group(1)), int(m.group(2)))
    elif (m := re.match(r'^/merchant_contracts/(\d+)/billing$', p)): return handler._merchant_contract_billing_preview(int(m.group(1)), q)
    elif p == '/cloud_schema': return handler._cloud_schema()
    elif p == '/cloud_migration.sql': return handler._cloud_migration_sql()
    elif p == '/delivery_center': return handler._delivery_center()
    elif p == '/delivery_center/contracts': return handler._delivery_contract_acceptance()
    elif p == '/delivery_center/import': return handler._delivery_import_acceptance()
    elif p == '/delivery_center/checklist': return handler._delivery_checklist()
    elif p == '/delivery_center/staff_guide': return handler._delivery_staff_guide()
    elif p == '/delivery_center/a_phase_review': return handler._delivery_a_phase_review()
    elif p == '/delivery_center/cloud_security': return handler._cloud_security_baseline()
    elif p == '/delivery_center/cloud_go_live': return handler._cloud_go_live_checklist()
    elif p == '/delivery_center/cloud_drill': return handler._cloud_deployment_drill()
    elif p == '/delivery_center/b_phase_review': return handler._delivery_b_phase_review()
    elif p == '/delivery_center/c_phase_review': return handler._delivery_c_phase_review()
    elif p == '/commercial_receivables': return handler._commercial_receivables(q)
    elif (m := re.match(r'^/merchant_contracts/(\d+)/amendments/(\d+)$', p)): return handler._contract_amendment_draft(int(m.group(1)), int(m.group(2)))
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
    elif (m := re.match(r'^/bills/(\d+)/pay$', p)): return handler._bill_pay(int(m.group(1)), q)
    elif (m := re.match(r'^/bills/(\d+)/edit$', p)): return handler._bill_edit(int(m.group(1)), q)
    elif p == '/bills/print_batch': return handler._bill_print_batch(q)
    elif p == '/bills/print_selected': return handler._print_selected(q)
    elif p == '/bills/receipt_by_ids': return handler._receipt_by_ids(q)
    elif p == '/bills/receipt': return handler._bill_receipt(q)
    elif p == '/bills/receipt_setup': return handler._receipt_setup(q)
    elif p == '/bills/export_receipt': return handler._export_receipt(q)
    elif p == '/payments': return handler._payments(q)
    elif p == '/payments/export.csv': return handler._payments_csv(q)
    elif p == '/users': return handler._users()
    elif p == '/users/create': return handler._user_form(None)
    elif (m := re.match(r'^/users/(\d+)/edit$', p)): return handler._user_form(int(m.group(1)))
    elif p == '/import': return handler._import_page()
    elif p == '/import/template/basic.csv': return handler._basic_import_template('csv')
    elif p == '/import/template/basic.xlsx': return handler._basic_import_template('xlsx')
    elif (m := re.match(r'^/import/template/(owners|payment_ledger|bills|commercial_contracts|b_tower_contracts)\.xlsx$', p)): return handler._typed_import_template(m.group(1), 'xlsx')
    elif (m := re.match(r'^/import/template/(owners|payment_ledger|bills|commercial_contracts|b_tower_contracts)\.csv$', p)): return handler._typed_import_template(m.group(1), 'csv')
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
    elif p == '/reports/arrears_detail.csv': return handler._reports_arrears_detail_csv(q)
    elif p == '/reports/payment_detail.csv': return handler._reports_payment_detail_csv(q)
    elif p == '/reports/waivers.csv': return handler._reports_waivers_csv(q)
    elif p == '/reports/customer_summary.csv': return handler._reports_customer_summary_csv(q)
    elif p == '/reports/enterprise_analysis.xlsx': return handler._reports_enterprise_analysis_xlsx(q)
    elif p == '/reports/tenants.csv': return handler._reports_tenants_csv(q)
    elif p == '/reports/tenant_arrears.csv': return handler._reports_tenant_arrears_csv(q)
    elif p == '/reports/fee_arrears.csv': return handler._reports_fee_arrears_csv(q)
    elif p == '/reports/reconciliation/print': return handler._reports_reconciliation_print(q)
    elif (m := re.match(r'^/api/rooms/(\d+)/meter/(\d+)$', p)):
        return handler._api_meter(int(m.group(1)), int(m.group(2)))
    elif (m := re.match(r'^/api/commercial_spaces/(\d+)/meter/(\d+)$', p)):
        return handler._api_space_meter(int(m.group(1)), int(m.group(2)))
    elif (m := re.match(r'^/api/owners/(\d+)/info$', p)): return handler._api_owner_info(int(m.group(1)))
    elif p == '/api/search_rooms': return handler._api_search_rooms(q)
    elif p == '/api/search_owners': return handler._api_search_owners(q)
    elif p.startswith('/static/'): return handler._serve_static(p)
    elif p == '/api/stats': return handler._api_stats()
    else: handler._error(404)
