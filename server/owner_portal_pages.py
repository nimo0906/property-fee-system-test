#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner portal H5 pages."""

import re

from server.db import get_db, h
from server.notifications import NotificationService
from server.owner_portal import OwnerPortalError, OwnerPortalService
from server.invoice_requests import InvoiceRequestService
from server.payment_orders import PaymentOrderError, PaymentOrderService


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
        self._owner_portal_render('业主自助服务', self._load_template('owner_portal_login.html').replace('{PHONE}', ''))

    def _owner_portal_send_code_post(self, data):
        phone = data.get('phone', [''])[0]
        try:
            result = OwnerPortalService().send_code(phone)
            message = f'<div class="alert alert-success mt-3">验证码已生成，测试验证码：<strong>{h(result["debug_code"])}</strong></div>'
        except OwnerPortalError as exc:
            message = f'<div class="alert alert-danger mt-3">{h(str(exc))}</div>'
        content = self._load_template('owner_portal_login.html').replace('{PHONE}', h(phone)) + message
        self._owner_portal_render('业主自助服务', content)

    def _owner_portal_logout(self):
        self.send_response(302)
        self.send_header('Location', '/owner-portal/login')
        self.send_header('Set-Cookie', 'owner_portal_token=; Max-Age=0; HttpOnly; SameSite=Lax; Path=/')
        self.end_headers()

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
        <div class="action-row"><a class="btn-main" href="/owner-portal/bills">查看待缴账单</a><a class="btn-ghost" href="/owner-portal/payments">缴费记录</a><a class="btn-ghost" href="/owner-portal/payment-orders">支付订单</a><a class="btn-ghost" href="/owner-portal/notifications">消息中心</a><a class="btn-ghost" href="/owner-portal/invoice-requests">电子票据</a></div>
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

    def _owner_portal_bill_detail_page(self, bill_id, preview=None, error=''):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        service = OwnerPortalService()
        bills = [b for b in service.bills(session, {})['items'] if b['id'] == bill_id]
        if not bills:
            return self._error(404)
        b = bills[0]
        result_html = ''
        if preview:
            result_html = f'''<div class="detail-card"><h2>支付前确认结果</h2>
            <dl><dt>当前欠费</dt><dd>{preview['unpaid_before']}</dd><dt>本次确认金额</dt><dd>{preview['amount']}</dd>
            <dt>支付后剩余欠费</dt><dd>{preview['unpaid_after']}</dd><dt>是否结清</dt><dd>{'是' if preview['will_mark_paid'] else '否'}</dd></dl></div>'''
        if error:
            result_html = f'<div class="alert alert-danger">{h(error)}</div>'
        payment_html = self._owner_portal_bill_recent_activity(bill_id)
        unpaid_amount = float(b['unpaid_amount'] or 0)
        if unpaid_amount <= 0.005:
            pay_html = '<div class="pay-panel"><h2>账单已结清</h2><p>本账单无需继续创建支付订单。</p></div>'
        else:
            pay_html = f'''<div class="pay-panel"><h2>支付前确认</h2><p>当前仅支持本地预览，暂未接真实在线支付。</p>
        <form method="POST" action="/owner-portal/bills/{bill_id}/preview-payment">
        <label>确认支付金额</label><input name="amount" value="{b['unpaid_amount']}" inputmode="decimal">
        <button class="btn-main" type="submit">确认金额</button></form><form method="POST" action="/owner-portal/bills/{bill_id}/create-order" style="margin-top:12px"><input type="hidden" name="amount" value="{b['unpaid_amount']}"><button class="btn-ghost" type="submit">创建模拟支付订单</button></form></div>'''
        content = f'''
        <h1>账单详情</h1>
        <div class="detail-card"><h2>{h(b['bill_number'] or '账单')}</h2><p>{h(b['period'])} · {h(b['fee_type'])}</p>
        <dl><dt>应收</dt><dd>{b['amount']}</dd><dt>已缴</dt><dd>{b['paid_amount']}</dd><dt>欠费</dt><dd>{b['unpaid_amount']}</dd><dt>截止日</dt><dd>{h(b['due_date'] or '-')}</dd></dl></div>
        {pay_html}
        {result_html}
        {payment_html}
        '''
        self._owner_portal_render('账单详情', content)

    def _owner_portal_bill_recent_activity(self, bill_id):
        db = get_db()
        try:
            orders = db.execute(
                'SELECT order_no, amount, status, created_at, paid_at FROM payment_orders '
                'WHERE bill_id=? ORDER BY id DESC LIMIT 3',
                (bill_id,),
            ).fetchall()
            payments = db.execute(
                'SELECT amount_paid, payment_method, payment_date FROM payments '
                'WHERE bill_id=? ORDER BY payment_date DESC, id DESC LIMIT 3',
                (bill_id,),
            ).fetchall()
        finally:
            db.close()
        order_rows = ''.join(
            f'<a class="list-card" href="/owner-portal/payment-orders/{h(o["order_no"])}">'
            f'<strong>{h(o["order_no"])} · {h(o["status"])}</strong>'
            f'<span>{float(o["amount"] or 0):.2f} · {h(o["paid_at"] or o["created_at"] or "")}</span></a>'
            for o in orders
        )
        payment_rows = ''.join(
            f'<div class="list-card"><strong>{float(p["amount_paid"] or 0):.2f} · {h(p["payment_method"] or "")}</strong>'
            f'<span>{h(p["payment_date"] or "")}</span></div>'
            for p in payments
        )
        sections = []
        if order_rows:
            sections.append(f'<div class="detail-card"><h2>最近支付订单</h2>{order_rows}</div>')
        if payment_rows:
            sections.append(f'<div class="detail-card"><h2>最近缴费记录</h2>{payment_rows}</div>')
        return ''.join(sections)

    def _owner_portal_bill_preview_payment_post(self, bill_id, data):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        amount = data.get('amount', [''])[0]
        try:
            preview = OwnerPortalService().preview_payment(session, {'bill_id': str(bill_id), 'amount': amount})
            return self._owner_portal_bill_detail_page(bill_id, preview=preview)
        except Exception as exc:
            return self._owner_portal_bill_detail_page(bill_id, error=str(exc))

    def _owner_portal_create_order_post(self, bill_id, data):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        amount = data.get('amount', [''])[0]
        try:
            order = PaymentOrderService().create_order(session, {'bill_id': str(bill_id), 'amount': amount, 'channel': 'mock'})
            order_no = h(order['order_no'])
            content = f'''<h1>模拟支付订单</h1><div class="detail-card"><h2>{order_no}</h2>
            <dl><dt>账单</dt><dd>{bill_id}</dd><dt>金额</dt><dd>{order['amount']}</dd><dt>状态</dt><dd>{h(order['status'])}</dd></dl></div>
            <form method="POST" action="/owner-portal/payment-orders/{order_no}/mock-paid"><button class="btn-main" type="submit">立即模拟支付成功</button></form>'''
            return self._owner_portal_render('模拟支付订单', content)
        except PaymentOrderError as exc:
            return self._owner_portal_bill_detail_page(bill_id, error=str(exc))

    def _owner_portal_mock_paid_post(self, order_no):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        try:
            paid = PaymentOrderService().mark_mock_paid(session, order_no)
            content = f'''<h1>模拟支付成功</h1><div class="detail-card"><h2>{h(order_no)}</h2>
            <p>订单已入账，缴费记录已更新。</p><dl><dt>金额</dt><dd>{paid['amount']}</dd><dt>状态</dt><dd>{h(paid['status'])}</dd></dl></div>
            <div class="action-row"><a class="btn-main" href="/owner-portal/payments">缴费记录</a><a class="btn-ghost" href="/owner-portal/bills">返回账单</a></div>'''
            return self._owner_portal_render('模拟支付成功', content)
        except PaymentOrderError as exc:
            return self._owner_portal_render('模拟支付失败', f'<div class="alert alert-danger">{h(str(exc))}</div>')



    def _owner_portal_invoice_requests_page(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        requests = InvoiceRequestService().list_requests({'owner_id': session['owner_id']})['items']
        rows = ''.join(
            f'<div class="list-card"><strong>{h(r["request_no"])} · {h(r["status"])}</strong>'
            f'<span>{h(r.get("amount") or "")} · {h(r.get("buyer_name") or "")}</span></div>'
            for r in requests
        )
        content = '<h1>电子票据</h1>' + (rows or '<p>暂无电子票据申请</p>')
        self._owner_portal_render('电子票据', content)

    def _owner_portal_notifications_page(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        events = NotificationService().list_events(owner_id=session['owner_id'])['items']
        rows = ''.join(
            f'<div class="list-card"><strong>{h(e["event_type"])} · {h(e["status"])}</strong>'
            f'<span>{h(e.get("created_at") or "")} · {h(e.get("payload") or "")}</span></div>'
            for e in events
        )
        self._owner_portal_render('消息中心', f'<h1>消息中心</h1>{rows or "<p>暂无消息</p>"}')

    def _owner_portal_payment_orders_page(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        orders = PaymentOrderService().list_orders(session)['items']
        rows = ''.join(
            f'<a class="list-card" href="/owner-portal/payment-orders/{h(o["order_no"])}">'
            f'<strong>{h(o["order_no"])} · {h(o["status"])}</strong>'
            f'<span>{h(o["bill_number"])} · {h(o["period"])} · {o["amount"]}</span></a>'
            for o in orders
        )
        self._owner_portal_render('支付订单', f'<h1>支付订单</h1>{rows or "<p>暂无支付订单</p>"}')

    def _owner_portal_payment_order_detail_page(self, order_no):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        try:
            order = PaymentOrderService().get_order(session, order_no)
        except PaymentOrderError as exc:
            return self._owner_portal_render('订单详情', f'<div class="alert alert-danger">{h(str(exc))}</div>')
        action = ''
        if order['status'] in ('created', 'pending'):
            action = f'<form method="POST" action="/owner-portal/payment-orders/{h(order_no)}/mock-paid"><button class="btn-main" type="submit">立即模拟支付成功</button></form>'
        content = f'''<h1>订单详情</h1><div class="detail-card"><h2>{h(order['order_no'])}</h2>
        <dl><dt>账单</dt><dd>{h(order['bill_number'])}</dd><dt>房间</dt><dd>{h(order['room_number'])}</dd>
        <dt>期间</dt><dd>{h(order['period'])}</dd><dt>金额</dt><dd>{order['amount']}</dd>
        <dt>渠道</dt><dd>{h(order['channel'])}</dd><dt>状态</dt><dd>{h(order['status'])}</dd>
        <dt>支付时间</dt><dd>{h(order['paid_at'] or '-')}</dd></dl></div>{action}
        <div class="action-row"><a class="btn-ghost" href="/owner-portal/payment-orders">返回支付订单</a><a class="btn-ghost" href="/owner-portal/bills/{order['bill_id']}">查看账单</a></div>'''
        self._owner_portal_render('订单详情', content)

    def _owner_portal_payments_page(self):
        session = self._owner_portal_require()
        if not session:
            return self._redirect('/owner-portal/login')
        payments = OwnerPortalService().payments(session)['items']
        rows = ''.join(f'<div class="list-card"><strong>{h(p["bill_number"])} · {p["amount"]}</strong><span>{h(p["payment_date"])} · {h(p["method"])}</span></div>' for p in payments)
        self._owner_portal_render('缴费记录', f'<h1>缴费记录</h1>{rows or "<p>暂无缴费记录</p>"}')
