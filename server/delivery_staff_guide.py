#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2 staff operation guide page."""

from server.base import BaseHandler


class DeliveryStaffGuideMixin(BaseHandler):
    def _delivery_staff_guide(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        self._html(self._page("员工操作说明", """
        <div class="alert alert-info border-info">
          <strong><i class="bi bi-journal-text"></i> 员工操作说明</strong>
          <div class="small mt-1">A 阶段交付收口使用：把不同岗位每天怎么用系统说清楚，减少培训时只讲功能、不讲工作流的问题。</div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-primary"><i class="bi bi-calculator"></i> 财务每天怎么操作</div>
            <div class="card-body">
              <ol class="mb-3">
                <li><strong>导入/录入资料</strong>：先补齐业主、收费对象、商户和空间合同档案，合同仅作行政备查。</li>
                <li><strong>抄表</strong>：按收费对象管理对象录入住户、商户和商业对象水表读数。</li>
                <li><strong>物业收费/商业收费</strong>：日常收费进入物业收费或商业收费，按收费项目生成账单。</li>
                <li><strong>账单核对</strong>：确认面积×单价、周期月数、水电读数、公摊分摊和服务期后，再收费登记。</li>
                <li><strong>收费 → 收据/发票 → 报表 → 期末结账</strong>：每天核对缴费记录、打印收据、开具发票、查看对账报表和异常预警，月底再做期末结账。</li>
              </ol>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-primary" href="/import">数据导入</a>
                <a class="btn btn-sm btn-outline-primary" href="/meter_readings">抄表管理</a>
                <a class="btn btn-sm btn-outline-primary" href="/billing">物业收费</a>
                <a class="btn btn-sm btn-outline-primary" href="/commercial_billing">商业收费</a>
                <a class="btn btn-sm btn-outline-primary" href="/merchant_contracts">空间合同档案</a>
                <a class="btn btn-sm btn-outline-primary" href="/bills">账单管理</a>
                <a class="btn btn-sm btn-outline-primary" href="/payments">缴费记录</a>
                <a class="btn btn-sm btn-outline-primary" href="/reports">对账报表</a>
              </div>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-success"><i class="bi bi-cash-coin"></i> 收费员怎么收费</div>
            <div class="card-body">
              <ol class="mb-3">
                <li>从收费工作台搜索房号、业主、商户或铺位。</li>
                <li>选择未收账单，核对金额、费用项目和本次服务期。</li>
                <li>执行<strong>收费登记</strong>，填写收款方式和经手人。</li>
                <li>收款完成后按需要<strong>打印收据</strong>，不要手工改历史收款。</li>
              </ol>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-success" href="/billing">收费工作台</a>
                <a class="btn btn-sm btn-outline-success" href="/payments">缴费记录</a>
                <a class="btn btn-sm btn-outline-success" href="/bills">账单管理</a>
              </div>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-warning"><i class="bi bi-headset"></i> 客服业务编辑怎么维护资料和催缴</div>
            <div class="card-body">
              <ol class="mb-3">
                <li>先在收费对象管理、业主管理或合同档案中维护业主、商户、电话、房号/铺位。</li>
                <li>进入<strong>催缴管理</strong>查看欠费项目、欠费金额和服务期。</li>
                <li>可修正基础资料、合同资料、抄表记录和导入资料；有账单金额争议时交给财务处理。</li>
                <li>关注合同到期、合同欠费和异常资料，必要时通知财务核对账单。</li>
              </ol>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-warning" href="/rooms">收费对象管理</a>
                <a class="btn btn-sm btn-outline-warning" href="/merchant_contracts">合同档案</a>
                <a class="btn btn-sm btn-outline-warning" href="/meter_readings">抄表管理</a>
                <a class="btn btn-sm btn-outline-warning" href="/reminders">催缴管理</a>
              </div>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-info"><i class="bi bi-bar-chart-line"></i> 管理层怎么看报表</div>
            <div class="card-body">
              <ol class="mb-3">
                <li>先看首页待办、欠费预警、合同到期和异常提醒。</li>
                <li>进入<strong>对账报表</strong>查看本月应收、实收、欠费和趋势。</li>
                <li>对商业对象重点看商业收费、合同档案到期风险和费用结构。</li>
                <li>只做经营判断，不直接操作收费、出账和导入写入。</li>
              </ol>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-info" href="/">收费工作台</a>
                <a class="btn btn-sm btn-outline-info" href="/reports">对账报表</a>
                <a class="btn btn-sm btn-outline-info" href="/alert_center">智能预警</a>
              </div>
            </div></div>
          </div>
        </div>
        <div class="alert alert-light border mt-3 small">
          <i class="bi bi-info-circle"></i> 培训口径：员工先按岗位入口操作；管理员再用交付验收清单检查合同、导入、权限、备份和系统健康。
        </div>
        """, "delivery_center"))
