#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 16."""

from tests.integration_base import *


class TestIntegration16(IntegrationTestBase):
    def test_room_form_allows_underground_negative_floor(self):
        status, body = http_get('/rooms/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="floor" type="number"', body)
        self.assertNotIn('name="floor" type="number" class="form-control" value="7" min="1"', body)
        self.assertIn('min="-99"', body)

        status, _, loc = http_post('/rooms/create', {
            'building': '地下测试', 'unit': '商场', 'room_number': 'B3-001',
            'floor': '-3', 'category': '商户', 'area': '30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/rooms?flash=', loc)

        _, list_body = http_get('/rooms?keyword=B3-001', self.cookie, TEST_PORT)
        self.assertIn('B3-001', list_body)
        self.assertIn('-3F', list_body)


    def test_room_edit_form(self):
        # First create a room
        http_post('/rooms/create', {
            'building': 'X栋', 'unit': 'A座', 'room_number': '666',
            'floor': '6', 'category': '居民', 'area': '80',
        }, self.cookie, TEST_PORT)
        # Then request edit form for room id 1
        status, body = http_get('/rooms/1/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('编辑房间', body)
        self.assertIn('租户姓名', body)
        self.assertIn('name="tenant_name"', body)
        self.assertIn('href="/rooms" class="btn btn-outline-secondary">返回</a>', body)


    def test_room_edit_from_import_stays_on_edit_page_after_save(self):
        status, _, loc = http_post('/rooms/create', {
            'building': '导入编辑', 'unit': '商场', 'room_number': 'IMP-STAY-1',
            'floor': '1', 'category': '商户', 'area': '55',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        _, body = http_get('/rooms?keyword=IMP-STAY-1', self.cookie, TEST_PORT)
        room_id = re.search(r'/rooms/(\d+)/edit', body).group(1)

        status, body = http_get(f'/rooms/{room_id}/edit?source=import', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('导入核对编辑', body)
        self.assertIn('name="source" value="import"', body)

        status, _, loc = http_post(f'/rooms/{room_id}/edit', {
            'source': 'import',
            'building': '导入编辑', 'unit': '商场', 'room_number': 'IMP-STAY-1',
            'floor': '1', 'category': '商户', 'area': '56',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn(f'/rooms/{room_id}/edit?source=import', loc)
        self.assertNotIn('/rooms?flash=', loc)


    def test_room_create_and_edit_tenant_name(self):
        status, _, loc = http_post('/rooms/create', {
            'building': 'T栋', 'unit': '商场', 'room_number': '1F-101',
            'floor': '1', 'category': '商户', 'area': '88',
            'tenant_name': '测试租户A',
            'tenant_phone': '13800138001',
            'tenant_id_card': '610101199001011234',
            'tenant_id_card_front': 'front-data',
            'tenant_id_card_back': 'back-data',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/rooms?flash=', loc)

        _, body = http_get('/rooms?keyword=%E6%B5%8B%E8%AF%95%E7%A7%9F%E6%88%B7A', self.cookie, TEST_PORT)
        self.assertIn('测试租户A', body)

        room_id = re.search(r'/rooms/(\d+)/edit', body).group(1)
        status, body = http_get(f'/rooms/{room_id}/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="测试租户A"', body)
        self.assertIn('租户电话', body)
        self.assertIn('value="13800138001"', body)
        self.assertIn('租户身份证号', body)
        self.assertIn('value="610101199001011234"', body)
        self.assertIn('租户身份证正面', body)
        self.assertIn('value="front-data"', body)
        self.assertIn('租户身份证反面', body)
        self.assertIn('value="back-data"', body)

        status, _, loc = http_post(f'/rooms/{room_id}/edit', {
            'building': 'T栋', 'unit': '商场', 'room_number': '1F-101',
            'floor': '1', 'category': '商户', 'area': '88',
            'tenant_name': '测试租户B',
            'tenant_phone': '13800138002',
            'tenant_id_card': '610101199002022345',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/rooms?flash=', loc)

        _, body = http_get('/rooms?keyword=%E6%B5%8B%E8%AF%95%E7%A7%9F%E6%88%B7B', self.cookie, TEST_PORT)
        self.assertIn('测试租户B', body)

        status, body = http_get(f'/rooms/{room_id}/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="13800138002"', body)
        self.assertIn('value="610101199002022345"', body)


    def test_owner_create_and_list(self):
        status, body, loc = http_post('/owners/create', {
            'name': '张三', 'phone': '13900001111',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/owners?flash=', loc)

        _, body = http_get('/owners', self.cookie, TEST_PORT)
        self.assertIn('张三', body)


    def test_fee_type_list_has_presets(self):
        _, body = http_get('/fee_types', self.cookie, TEST_PORT)
        for name in ['物业费(居民)', '电梯费', '水费(非居民)']:
            with self.subTest(fee=name):
                self.assertIn(name, body)

