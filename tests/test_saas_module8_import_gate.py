#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 8 import preview, confirm and error-row gate tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]


def _login(client, role_code='finance'):
    response = client.post('/api/auth/login', json={
        'tenant_name': '模块八物业',
        'project_name': '模块八项目',
        'username': f'{role_code}_user',
        'role_code': role_code,
    })
    assert response.status_code == 200


def test_module8_gate_script_exists_and_is_registered():
    script = ROOT / 'scripts/saas_module8_import_review_gate.py'
    assert script.exists(), 'missing module 8 import review gate script'
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_module8_import_review_gate.py' in gate


def test_module8_gate_script_documents_import_preview_confirm_error_rows_scope():
    text = (ROOT / 'scripts/saas_module8_import_review_gate.py').read_text(encoding='utf-8')
    for keyword in [
        'import preview',
        'confirm import',
        'error rows',
        'legacy desktop aliases',
        'tenant isolation',
        'release gate registration',
    ]:
        assert keyword in text


def test_import_flow_aligns_desktop_aliases_and_exports_error_rows_without_internal_scope():
    client = TestClient(create_app())
    _login(client)

    csv_text = '\n'.join([
        '业主姓名,联系电话,楼栋/区域,单元/分区,房号/铺位号,对象类型,面积㎡,物业费单价,店铺名称,缴费周期',
        '张三,13800000000,1栋,1单元,101,居民,80,,便利店,monthly',
        '错误户,13900000000,1栋,1单元,,居民,60,,错误店,monthly',
    ])
    preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
    assert preview.status_code == 200
    assert '有效 1 行，错误 1 行' in preview.text
    assert '便利店' in preview.text
    assert '错误行' in preview.text

    import_id = preview.text.split('name="import_id" value="', 1)[1].split('"', 1)[0]
    errors = client.get(f'/api/imports/{import_id}/errors.csv')
    assert errors.status_code == 200
    assert '错误户' in errors.text
    assert 'tenant_id' not in errors.text
    assert 'project_id' not in errors.text
    assert '.env' not in errors.text

    confirmed = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})
    assert confirmed.status_code == 200
    for text in ['导入结果', '成功导入：1', '错误跳过：1', '总跳过：1']:
        assert text in confirmed.text
    targets = client.get('/api/charge-targets').json()['items']
    assert [item['room_number'] for item in targets] == ['101']


def test_non_import_role_cannot_preview_confirm_or_download_error_rows():
    finance = TestClient(create_app())
    _login(finance, 'finance')
    preview = finance.post('/api/imports/charge-targets/preview', json={'rows': [
        {'building': '1栋', 'unit': '1单元', 'room_number': '', 'category': '居民', 'area': '80'},
    ]})
    assert preview.status_code == 200
    import_id = preview.json()['import_id']

    cashier = TestClient(finance.app)
    _login(cashier, 'cashier')
    assert cashier.post('/api/imports/charge-targets/preview', json={'rows': []}).status_code == 403
    assert cashier.get(f'/api/imports/{import_id}/review').status_code == 403
    assert cashier.post('/api/imports/charge-targets/confirm', json={'import_id': import_id}).status_code == 403
    assert cashier.get(f'/api/imports/{import_id}/errors.csv').status_code == 403
