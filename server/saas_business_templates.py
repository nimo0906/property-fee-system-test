#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant business templates for SaaS onboarding."""

TEMPLATES = {
    'residential': {
        'name': '住宅物业', 'fields': ['楼栋', '单元', '房号', '业主姓名', '面积'],
        'fees': ['物业费', '水费', '停车费'], 'cycle': '月度',
        'sample': '住宅楼,1单元,101,居民,80',
    },
    'commercial': {
        'name': '商业/商铺', 'fields': ['区域', '楼层/分区', '商铺号', '商户名称', '面积'],
        'fees': ['物业费', '租金', '水电费'], 'cycle': '月度',
        'sample': '商业区,一层,A-001,商户,56.5',
    },
    'office': {
        'name': '园区/办公', 'fields': ['园区', '办公楼', '楼层/分区', '工位/房号', '面积'],
        'fees': ['物业费', '能耗费', '停车费'], 'cycle': '月度',
        'sample': '园区A,办公楼,501,办公,120',
    },
    'mixed': {
        'name': '混合项目', 'fields': ['区域', '楼栋/楼层', '房号/铺位号', '客户类型', '面积'],
        'fees': ['物业费', '水电费', '停车费', '租金'], 'cycle': '月度/季度',
        'sample': '混合区,商住楼,201,居民,90',
    },
}

CHARGE_TARGET_TEMPLATE_HEADERS = [
    '项目', '楼栋/区域', '单元/分区', '房号/铺位号', '楼层', '对象类型', '面积㎡', '物业费单价', '水费标准',
    '业主姓名', '业主电话', '身份证号', '租户姓名', '租户电话', '租户身份证号', '合同开始日期', '合同结束日期',
    '缴费周期', '店铺名称', '业态/商户类别', '备注',
]


def business_template(code='residential'):
    return TEMPLATES.get(code or 'residential', TEMPLATES['residential'])


def template_options(selected='residential'):
    return ''.join(
        f'<option value="{code}"{" selected" if code == selected else ""}>{item["name"]}</option>'
        for code, item in TEMPLATES.items()
    )


def render_template_summary(selected='residential'):
    cards = []
    for code, item in TEMPLATES.items():
        mark = ' · 当前选择' if code == selected else ''
        cards.append(
            f'<div class="card"><div class="card-h">{item["name"]}{mark}</div><div class="card-b">'
            f'<p class="sub"><strong>收费对象字段：</strong>{"、".join(item["fields"])}</p>'
            f'<p class="sub"><strong>推荐收费项目：</strong>{"、".join(item["fees"])}</p>'
            f'<p class="sub"><strong>账单周期：</strong>{item["cycle"]}</p>'
            f'<p class="sub"><strong>导入样例：</strong><code>{item["sample"]}</code></p></div></div>'
        )
    return '<section class="card" style="margin-top:18px"><div class="card-h">业务模板字段建议</div><div class="card-b"><p class="sub">不同公司业务不同，先选模板再导入；模板只提供字段和收费建议，不写入内部编号。</p></div></section><section class="grid" style="margin-top:18px">' + ''.join(cards) + '</section>'


def template_csv(code='residential'):
    item = business_template(code)
    sample = _full_sample(item['sample'])
    return (
        ','.join(CHARGE_TARGET_TEMPLATE_HEADERS) + '\n'
        + ','.join(sample) + '\n'
        + f'# compact legacy sample: {item["sample"]}\n'
        + '# canonical fields: owner_name,owner_phone,owner_type,building,unit,room_number,floor,shop_name,tenant_name,tenant_phone,category,area,unit_price_override,payment_cycle,notes\n'
        + '# legacy aliases: 业主姓名,联系电话,楼栋/区域,单元/分区,房号/铺位号,面积\n'
    )


def _full_sample(sample):
    parts = [part.strip() for part in sample.split(',')]
    building, unit, room_number, category, area = (parts + [''] * 5)[:5]
    cycle = '季付' if category == '商户' else '月付'
    return [
        '默认项目', building, unit, room_number, '', category, area, '', '非居民',
        '示例业主', '13800000000', '', '', '', '', '2026-01-01', '2026-12-31',
        cycle, '示例店名' if category == '商户' else '', category if category == '商户' else '', '模板示例',
    ]
