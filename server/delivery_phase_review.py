#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2 phase review pages."""

from server.base import BaseHandler


class DeliveryPhaseReviewMixin(BaseHandler):
    def _delivery_a_phase_review(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        self._html(self._page("A 阶段完成审查", """
        <div class="alert alert-success border-success">
          <strong><i class="bi bi-check2-circle"></i> A 阶段完成审查</strong>
          <div class="small mt-1">当前目标是把本地 2.0 员工后台交付收口跑稳。以下项目全部可检查后，进入 2.0 桌面稳定版收口，不继续新增业务板块。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-success"><i class="bi bi-patch-check"></i> A 阶段审查结论</div>
          <div class="card-body">
            <div class="table-responsive"><table class="table table-sm align-middle">
              <thead><tr><th>审查项</th><th>当前结论</th><th>证据入口</th></tr></thead>
              <tbody>
                <tr><td><strong>合同闭环已验收</strong></td><td>商户合同、预览出账、确认生成、押金一次、重复去重、续签/停用/附件已形成闭环。</td><td><a href="/delivery_center/contracts">合同闭环验收</a></td></tr>
                <tr><td><strong>导入闭环已验收</strong></td><td>导入先识别、映射、核对、修正，确认后才写库，历史金额不会自动入账。</td><td><a href="/delivery_center/import">导入闭环验收</a></td></tr>
                <tr><td><strong>岗位权限已验收</strong></td><td>交付中心仅管理员和管理层可进入，普通财务/收费员/客服前台不能进入。</td><td><a href="/users">操作员管理</a></td></tr>
                <tr><td><strong>总验收清单已补齐</strong></td><td>合同、导入、权限、云端技术备查、备份恢复、系统健康和全量测试集中核对。</td><td><a href="/delivery_center/checklist">总验收清单</a></td></tr>
                <tr><td><strong>员工操作说明已补齐</strong></td><td>财务、收费员、客服业务编辑、管理层都有日常操作入口说明。</td><td><a href="/delivery_center/staff_guide">员工操作说明</a></td></tr>
                <tr><td><strong>云端技术备查入口已保留</strong></td><td>PostgreSQL schema、seed SQL 和迁移摘要入口保留给管理员/技术人员；当前不作为业务主线。</td><td><a href="/cloud_schema">云端技术备查</a></td></tr>
                <tr><td><strong>备份恢复入口已准备</strong></td><td>交付前可从备份页检查手动备份、自动备份、恢复入口和清理边界。</td><td><a href="/backups">备份恢复</a></td></tr>
                <tr><td><strong>系统健康检查入口已准备</strong></td><td>交付前可检查数据库、账单、收款、异常数据和权限边界风险。</td><td><a href="/system_health">系统健康检查</a></td></tr>
              </tbody>
            </table></div>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-primary"><i class="bi bi-terminal"></i> 底层验证要求</div>
            <div class="card-body">
              <p class="mb-2"><strong>进入稳定版收口前必须保持全量测试通过</strong>，当前稳定版验证基线：</p>
              <div class="p-3 bg-light border rounded small mb-3">
                <code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest</code><br>
                <strong>431 passed, 4 skipped</strong>
              </div>
              <p class="small text-muted mb-0">后续只补当前主流程缺口；每次修改都要重新跑专项测试和全量测试，再更新交付验收基线。</p>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-warning"><i class="bi bi-box-seam"></i> 稳定版收口边界</div>
            <div class="card-body">
              <p><strong>可以进入 2.0 桌面稳定版收口</strong></p>
              <ul class="mb-0">
                <li>停止新增业务板块，只补现有主流程缺口。</li>
                <li>优先统一文案、金额口径、权限、防错、导入、报表和桌面打包交付。</li>
                <li>云端技术备查保留为技术备查，不开放业主端公网支付闭环。</li>
              </ul>
            </div></div>
          </div>
        </div>
        <div class="alert alert-light border mt-3 small">
          <i class="bi bi-info-circle"></i> A 阶段审查口径：本页不是替代人工验收，而是把可以被检查的入口和底层测试证据集中起来，避免没有收口就进入云端化。
        </div>
        """, "delivery_center"))


    def _delivery_c_phase_review(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        self._html(self._page("C 阶段完成审查", """
        <div class="alert alert-success border-success">
          <strong><i class="bi bi-bar-chart-line"></i> C 阶段完成审查</strong>
          <div class="small mt-1">2.0 当前业务范围已完成，进入桌面稳定版收口优化；本页用于确认后续停止扩业务，转为现有模块统一优化和交付冻结。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-success"><i class="bi bi-patch-check"></i> C 阶段审查结论</div>
          <div class="card-body">
            <div class="table-responsive"><table class="table table-sm align-middle">
              <thead><tr><th>审查项</th><th>当前结论</th><th>证据入口</th></tr></thead>
              <tbody>
                <tr><td><strong>首页经营驾驶舱已增强</strong></td><td>首页已展示本月应收、实收率、区域 / 业态对比、欠费趋势、商户贡献和费用结构。</td><td><a href="/">收费工作台</a></td></tr>
                <tr><td><strong>报表分析看板已增强</strong></td><td>对账报表页已接入经营分析看板，财务可按自然日期范围查看收缴率、欠费趋势、商户贡献和费用结构。</td><td><a href="/reports">对账报表</a></td></tr>
                <tr><td><strong>A/B/C 阶段验收链路</strong></td><td>交付收口、云端技术备查、经营分析均有独立审查入口，可逐项回看；当前主线转为桌面稳定版收口。</td><td><a href="/delivery_center">2.0交付中心</a></td></tr>
                <tr><td><strong>底层安全运行验证</strong></td><td>稳定版收口前已重新运行专项测试和全量回归，确认账单、收款、导入、权限、云端技术备查和报表未被破坏。</td><td><a href="/system_health">系统健康检查</a></td></tr>
              </tbody>
            </table></div>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-primary"><i class="bi bi-terminal"></i> 底层验证基线</div>
            <div class="card-body">
              <p class="mb-2"><strong>2.0 当前业务范围已完成，进入桌面稳定版收口优化</strong>，C 阶段完成后的验证基线：</p>
              <div class="p-3 bg-light border rounded small mb-3">
                <code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest</code><br>
                <strong>431 passed, 4 skipped</strong>
              </div>
              <p class="small text-muted mb-0">后续停止新增业务板块；只允许补齐当前主流程缺口，并且每次修改都要先跑专项测试，再跑全量测试。</p>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-info"><i class="bi bi-signpost"></i> 稳定版收口建议</div>
            <div class="card-body">
              <ul class="mb-3">
                <li>统一现有模块业务词和金额口径：商户编号、租金单价、押金单价、物业费单价、面积和周期。</li>
                <li>按真实使用流程做防错：导入/录入、抄表、出账、收费、收据/发票、报表、期末结账。</li>
                <li>完成 UI、金额、权限、导入、报表专项 QA 后冻结 2.0 稳定版。</li>
              </ul>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-primary" href="/delivery_center/a_phase_review">A阶段审查</a>
                <a class="btn btn-sm btn-outline-primary" href="/delivery_center/b_phase_review">技术备查审查</a>
                <a class="btn btn-sm btn-outline-primary" href="/reports">查看报表分析</a>
              </div>
            </div></div>
          </div>
        </div>
        <div class="alert alert-light border mt-3 small">
          <i class="bi bi-info-circle"></i> 稳定版收口口径：本页用于确认当前 2.0 业务范围已经形成；不代表已开放业主端公网支付，也不代表已完成通用 SaaS 化或云端上线。
        </div>
        """, "delivery_center"))
