#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner portal H5 pages."""

import re

from server.db import h
from server.owner_portal import OwnerPortalError, OwnerPortalService


class OwnerPortalPageMixin:
    def _owner_portal_token_from_cookie(self):
        cookie = self.headers.get('Cookie', '')
        if m := re.search(r'owner_portal_token=([^;]+)', cookie):
            return m.group(1)
        return ''

    def _owner_portal_current_session(self):
        token = self._owner_portal_token_from_cookie()
        if not token:
            raise OwnerPortalError('请先登录')
        return OwnerPortalService().get_session(token)

    def _owner_portal_render(self, title, content):
        html = self._load_template('owner_portal_base.html')
        html = html.replace('{TITLE}', h(title)).replace('{CONTENT}', content)
        self._html(html)

    def _owner_portal_login_page(self):
        self._owner_portal_render('业主自助服务', self._load_template('owner_portal_login.html'))

    def _owner_portal_login_post(self, data):
        phone = data.get('phone', [''])[0]
        code = data.get('code', [''])[0]
        try:
            result = OwnerPortalService().login(phone, code)
        except OwnerPortalError as exc:
            return self._owner_portal_render('业主自助服务', self._load_template('owner_portal_login.html') + f'<div class="alert alert-danger mt-3">{h(str(exc))}</div>')
        token = result.pop('token')
        self.send_response(302)
        self.send_header('Location', '/owner-portal/dashboard')
        self.send_header('Set-Cookie', f'owner_portal_token={token}; HttpOnly; SameSite=Lax; Path=/')
        self.end_headers()

    def _owner_portal_require(self):
        try:
            return self._owner_portal_current_session()
        except OwnerPortalError:
            return None

    def _owner_portal_dashboard(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        service = OwnerPortalService()
        profile = service.profile(session)
        rooms = service.rooms(session)['items']
        bills = service.bills(session, {'status': 'unpaid'})['items']
        unpaid_total = sum(float(b['unpaid_amount']) for b in bills)
        content = f'''
        <section class="hero-card"><div><p class="eyebrow">OWNER PORTAL</p><h1>{h(profile['name'])}，欢迎回来</h1><p>这里可以查看您的房间、待缴账单和缴费记录。</p></div></section>
        <div class="metric-grid">
          <a class="metric" href="/owner-portal/rooms"><span>我的房间</span><strong>{len(rooms)}</strong></a>
          <a class="metric" href="/owner-portal/bills"><span>待缴账单</span><strong>{len(bills)}</strong></a>
          <a class="metric" href="/owner-portal/bills"><span>待缴金额</span><strong>{unpaid_total:.2f}</strong></a>
        </div>
        <div class="action-row"><a class="btn-main" href="/owner-portal/bills">查看待缴账单</a><a class="btn-ghost" href="/owner-portal/payments">缴费记录</a></div>
        '''
        self._owner_portal_render('业主首页', content)

    def _owner_portal_rooms_page(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        rooms = OwnerPortalService().rooms(session)['items']
        rows = ''.join(f'<div class="list-card"><strong>{h(r["building"])} {h(r["unit"])} {h(r["room_number"])}</strong><span>{h(r["category"])} · {r["area"]}㎡</span></div>' for r in rooms)
        self._owner_portal_render('我的房间', f'<h1>我的房间</h1>{rows or "<p>暂无房间</p>"}')

    def _owner_portal_bills_page(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        bills = OwnerPortalService().bills(session, {})['items']
        rows = ''.join(f'<a class="list-card" href="/owner-portal/bills/{b["id"]}"><strong>{h(b["bill_number"] or "账单")} · {h(b["fee_type"])}</strong><span>{h(b["period"])} · 欠费 {b["unpaid_amount"]}</span></a>' for b in bills)
        self._owner_portal_render('我的账单', f'<h1>我的账单</h1>{rows or "<p>暂无账单</p>"}')

    def _owner_portal_bill_detail_page(self, bill_id):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        service = OwnerPortalService()
        bills = [b for b in service.bills(session, {})['items'] if b['id'] == bill_id]
        if not bills:
            return self._error(404)
        b = bills[0]
        content = f'''
        <h1>账单详情</h1>
        <div class="detail-card"><h2>{h(b['bill_number'] or '账单')}</h2><p>{h(b['period'])} · {h(b['fee_type'])}</p>
        <dl><dt>应收</dt><dd>{b['amount']}</dd><dt>已缴</dt><dd>{b['paid_amount']}</dd><dt>欠费</dt><dd>{b['unpaid_amount']}</dd><dt>截止日</dt><dd>{h(b['due_date'] or '-')}</dd></dl></div>
        <div class="pay-panel"><h2>支付前确认</h2><p>当前仅支持本地预览，暂未接真实在线支付。</p><button class="btn-main" disabled>在线支付待接入</button></div>
        '''
        self._owner_portal_render('账单详情', content)

    def _owner_portal_payments_page(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        payments = OwnerPortalService().payments(session)['items']
        rows = ''.join(f'<div class="list-card"><strong>{h(p["bill_number"])} · {p["amount"]}</strong><span>{h(p["payment_date"])} · {h(p["method"])}</span></div>' for p in payments)
        self._owner_portal_render('缴费记录', f'<h1>缴费记录</h1>{rows or "<p>暂无缴费记录</p>"}')
