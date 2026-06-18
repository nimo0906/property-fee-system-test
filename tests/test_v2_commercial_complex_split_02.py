#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split tests from tests/test_v2_commercial_complex.py chunk 02."""

from tests.test_v2_commercial_complex_split_base import *


class TestCommercialComplexCloudV202(V2CommercialComplexTestBase):
    def test_enterprise_dashboard_counts_commercial_space_contract_bills(self):
        from server.commercial_spaces import create_commercial_space
        space_id = create_commercial_space({
            "space_no": "3F-301", "shop_name": "分析商户", "merchant_name": "分析商户",
            "business_type": "零售", "area": 100, "water_rate_type": "非居民",
        })
        contract_id = create_merchant_contract({
            "commercial_space_id": space_id,
            "contract_no": "HT-ANALYSIS-SPACE",
            "merchant_name": "分析商户",
            "shop_name": "分析商户",
            "rent_amount": 5000,
            "property_rate": 5,
            "deposit_amount": 0,
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
        })
        confirm_contract_billing(contract_id, build_contract_billing_preview(contract_id, "2026-06-01")["items"])
        metrics = get_enterprise_dashboard_metrics("2026-06", today=date(2026, 6, 11))
        self.assertEqual(metrics["segments"]["商业空间"]["due"], 5500.0)
        self.assertEqual(metrics["merchant_contribution"][0]["merchant"], "分析商户")
        self.assertEqual(metrics["merchant_contribution"][0]["due"], 5500.0)


