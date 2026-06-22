#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backoffice batch bill preview tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '批量预览物业', 'project_name': '批量预览项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client

def test_backoffice_batch_generate_preview_does_not_write_until_confirmed():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url)
        client.post('/api/charge-targets', json={'building': '预览区', 'unit': '一层', 'room_number': 'P-101', 'category': '商户', 'area': 40})
        client.post('/api/charge-targets', json={'building': '预览区', 'unit': '一层', 'room_number': 'P-102', 'category': '商户', 'area': 60})
        fee = client.post('/api/fee-types', json={'name': '预览物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
        first = client.post('/api/bills/batch-generate', json={
            'fee_type_id': fee['id'], 'billing_period': '2028-02',
            'service_start': '2028-02-01', 'service_end': '2028-02-29',
            'category': '商户', 'building': '预览区', 'unit': '一层',
        })
        assert first.status_code == 200
        assert first.json()['created_count'] == 2
        client.post('/api/charge-targets', json={'building': '预览区', 'unit': '一层', 'room_number': 'P-103', 'category': '商户', 'area': 70})

        preview = client.post('/backoffice/bills/batch-generate-preview', data={
            'fee_type_id': str(fee['id']), 'billing_period': '2028-02',
            'service_start': '2028-02-01', 'service_end': '2028-02-29',
            'category': '商户', 'building': '预览区', 'unit': '一层',
        })

        assert preview.status_code == 200
        assert '批量出账预览' in preview.text
        assert '预计出账1张' in preview.text
        assert '跳过2张' in preview.text
        assert '金额合计140.0元' in preview.text
        assert 'P-103 2028-02-01~2028-02-29 140.0元' in preview.text
        assert 'P-101 已存在账单，确认导入将跳过' in preview.text
        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        assert len(repo.list_bills(tenant['id'], project['id'], '2028-02')) == 2
        repo.close()

        confirmed = client.post('/backoffice/bills/batch-generate-confirm', data={
            'fee_type_id': str(fee['id']), 'billing_period': '2028-02',
            'service_start': '2028-02-01', 'service_end': '2028-02-29',
            'category': '商户', 'building': '预览区', 'unit': '一层',
        }, follow_redirects=False)

        assert confirmed.status_code == 303
        page = client.get(confirmed.headers['location'])
        assert '批量出账1张，跳过2张，金额合计140.0元' in page.text
        repo = create_saas_repository(db_url)
        assert len(repo.list_bills(tenant['id'], project['id'], '2028-02')) == 3
        repo.close()



def test_batch_generate_preview_explains_amount_rules_and_payment_cycle():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url)
        client.post('/api/charge-targets', json={
            'building': '规则区', 'unit': '一层', 'room_number': 'R-101', 'category': '商户',
            'area': 40, 'shop_name': '覆盖店', 'unit_price_override': 5, 'payment_cycle': 'quarterly',
        })
        client.post('/api/charge-targets', json={
            'building': '规则区', 'unit': '一层', 'room_number': 'R-102', 'category': '商户',
            'area': 30, 'shop_name': '固定店', 'payment_cycle': 'monthly',
        })
        area_fee = client.post('/api/fee-types', json={'name': '商户物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
        fixed_fee = client.post('/api/fee-types', json={'name': '商户服务费', 'unit_price': 80, 'billing_mode': 'fixed'}).json()['item']

        area_preview = client.post('/backoffice/bills/batch-generate-preview', data={
            'fee_type_id': str(area_fee['id']), 'billing_period': '2028-03',
            'service_start': '2028-03-01', 'service_end': '',
            'category': '商户', 'building': '规则区', 'unit': '一层', 'use_payment_cycle': '1',
        })
        fixed_preview = client.post('/backoffice/bills/batch-generate-preview', data={
            'fee_type_id': str(fixed_fee['id']), 'billing_period': '2028-03',
            'service_start': '2028-03-01', 'service_end': '2028-03-31',
            'category': '商户', 'building': '规则区', 'unit': '一层',
        })

        assert area_preview.status_code == 200
        for text in [
            '金额规则说明', '面积计费：面积 × 单价', '独立单价覆盖', '周期规则：按收费对象缴费周期计算服务期',
            'R-101', '2028-03-01~2028-05-31', '面积40.0 × 单价5.0 × 3个月 = 600.0',
            'R-102', '2028-03-01~2028-03-31', '面积30.0 × 单价2.0 × 1个月 = 60.0',
        ]:
            assert text in area_preview.text
        assert fixed_preview.status_code == 200
        for text in ['固定金额：每户/每铺固定金额', 'R-101', '固定金额 80.0', 'R-102', '金额合计160.0元']:
            assert text in fixed_preview.text
        assert '固定金额 5.0' not in fixed_preview.text
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            assert hidden not in area_preview.text
            assert hidden not in fixed_preview.text


def test_batch_generate_preview_shows_formal_target_fee_period_columns_for_commercial_scope():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url)
        client.post('/api/charge-targets', json={
            'building': '商场A区', 'unit': '一层', 'room_number': 'M-101', 'category': '商户',
            'area': 40, 'shop_name': '品牌店', 'tenant_name': '张商户', 'unit_price_override': 5,
        })
        client.post('/api/charge-targets', json={
            'building': '商场A区', 'unit': '二层', 'room_number': 'C-201', 'category': '商业',
            'area': 30, 'shop_name': '餐饮店', 'tenant_name': '李商户', 'unit_price_override': 6,
        })
        client.post('/api/charge-targets', json={
            'building': '住宅楼', 'unit': '一单元', 'room_number': '101', 'category': '居民', 'area': 80,
        })
        fee = client.post('/api/fee-types', json={'name': '物业费(商业)', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']

        bill_page = client.get('/backoffice/bills')
        preview = client.post('/backoffice/bills/batch-generate-preview', data={
            'fee_type_id': str(fee['id']), 'billing_period': '2028-04',
            'service_start': '2028-04-01', 'service_end': '2028-04-30',
            'category': '商业', 'building': '商场A区', 'unit': '',
        })

        assert bill_page.status_code == 200
        assert '<option value="商业">商业/商户</option>' in bill_page.text
        assert preview.status_code == 200
        for text in [
            '出账明细核对', '跳过明细', '收费项目', '账期', '楼栋 / 区域', '单元 / 分区',
            '房号 / 铺位号', '类型', '店名 / 承租人', '服务期', '金额', '计算规则',
            '物业费(商业)', '2028-04', '商场A区', '一层', 'M-101', '商户', '品牌店 / 张商户',
            '二层', 'C-201', '商业', '餐饮店 / 李商户', '200.0', '180.0', '金额合计380.0元',
        ]:
            assert text in preview.text
        assert '住宅楼' not in preview.text
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            assert hidden not in preview.text
