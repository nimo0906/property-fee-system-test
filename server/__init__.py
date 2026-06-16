#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""物业管理收费系统 — 模块化包"""

from server.db import db_init
from server.base import BaseHandler
from server.auth import AuthMixin
from server.index import IndexMixin
from server.index_api import IndexApiMixin
from server.rooms import RoomMixin
from server.commercial_spaces import CommercialSpaceMixin
from server.owners import OwnerMixin
from server.fees import FeeMixin
from server.meter import MeterMixin
from server.meter_ledger import MeterLedgerMixin
from server.bill_list import BillListMixin
from server.bill_detail import BillDetailMixin
from server.bill_generation import BillGenerationMixin
from server.bill_export import BillExportMixin
from server.bill_print import BillPrintMixin
from server.bill_receipt import BillReceiptMixin
from server.payments import PaymentMixin
from server.billing_ui import BillingUiMixin
from server.auto_billing import AutoBillingMixin
from server.repairs import RepairMixin
from server.parking import ParkingMixin
from server.invoices import InvoiceMixin
from server.deposits import DepositMixin
from server.reminders import ReminderMixin
from server.collections import CollectionMixin
from server.closing import ClosingMixin
from server.reports import ReportMixin
from server.import_data import ImportMixin
from server.backups import BackupMixin
from server.data_health import DataHealthMixin
from server.system_update_pages import SystemUpdateMixin
from server.trial_data_reset import TrialDataResetMixin
from server.shared_expenses import SharedExpenseMixin
from server.batch_ops import BatchOpsMixin
from server.api import ApiMixin
from server.alert_pages import AlertCenterMixin
from server.merchant_contracts import MerchantContractMixin
from server.merchant_contract_lifecycle import MerchantContractLifecycleMixin
from server.merchant_contract_attachments import MerchantContractAttachmentMixin
from server.merchant_contract_import import MerchantContractImportMixin
from server.merchant_contract_attachment_workflows import MerchantContractAttachmentWorkflowMixin
from server.tenant_transfer import TenantTransferMixin
from server.merchant_contract_transfer import MerchantContractTransferMixin
from server.delivery_center import DeliveryCenterMixin
from server.delivery_staff_guide import DeliveryStaffGuideMixin
from server.delivery_phase_review import DeliveryPhaseReviewMixin
from server.cloud_pages import CloudPageMixin
from server.cloud_security_pages import CloudSecurityPageMixin
from server.commercial_receivables import CommercialReceivableMixin
from server.contract_amendment_pages import ContractAmendmentMixin


class Handler(
    AuthMixin, IndexMixin, IndexApiMixin, RoomMixin, OwnerMixin,
    FeeMixin, CommercialSpaceMixin, MeterMixin, MeterLedgerMixin,
    BillListMixin, BillDetailMixin, BillGenerationMixin,
    BillExportMixin, BillPrintMixin, BillReceiptMixin,
    PaymentMixin, BillingUiMixin, AutoBillingMixin,
    RepairMixin, ParkingMixin, InvoiceMixin, DepositMixin,
    ReminderMixin, CollectionMixin, ClosingMixin, ReportMixin, SharedExpenseMixin, BatchOpsMixin,
    MerchantContractMixin, MerchantContractLifecycleMixin, MerchantContractTransferMixin, MerchantContractImportMixin, MerchantContractAttachmentMixin, MerchantContractAttachmentWorkflowMixin, TenantTransferMixin, AlertCenterMixin, DeliveryCenterMixin, DeliveryStaffGuideMixin, DeliveryPhaseReviewMixin, CloudPageMixin, CloudSecurityPageMixin, CommercialReceivableMixin, ContractAmendmentMixin, ImportMixin, BackupMixin, DataHealthMixin, SystemUpdateMixin, TrialDataResetMixin, ApiMixin, BaseHandler,
):
    """HTTP handler with all feature mixins."""
    pass
