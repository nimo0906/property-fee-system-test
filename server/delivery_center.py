#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2 delivery center pages."""

from server.base import BaseHandler


class DeliveryCenterMixin(BaseHandler):
    def _delivery_allowed(self):
        user = self._get_current_user() or {}
        return user.get("role") in ("admin", "system_admin")

    def _delivery_center(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        self._html(self._page("2.0 交付中心", """
        <div class="alert alert-info border-info">
          <strong><i class="bi bi-clipboard-check"></i> 2.0 交付中心</strong>
          <div class="small mt-1">2.0 当前业务范围已完成，进入桌面稳定版收口优化；后续停止新增业务板块，优先统一文案、金额口径、权限、防错和打包交付。</div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-primary"><i class="bi bi-person-lock"></i> 岗位权限说明</div>
            <div class="card-body">
              <div class="table-responsive"><table class="table table-sm align-middle">
                <thead><tr><th>岗位</th><th>主要职责</th><th>关键边界</th></tr></thead>
                <tbody>
                  <tr><td><strong>系统管理员</strong></td><td>系统维护、账号、备份、更新、云端技术备查</td><td>保留给内部或客户负责人，不给普通员工</td></tr>
                  <tr><td><strong>财务</strong></td><td>商业收费、物业收费、账单核对、收费、发票、对账、结账</td><td>不能做系统维护和清空试用数据</td></tr>
                  <tr><td><strong>收费员</strong></td><td>日常收费、打印收据、查看缴费记录</td><td>不负责合同规则和高风险删除</td></tr>
                  <tr><td><strong>客服业务编辑</strong></td><td>维护业主、房间、合同、抄表、导入资料并跟进催缴</td><td>不删除资料，不生成账单、不收款、不结账</td></tr>
                  <tr><td><strong>管理层只读</strong></td><td>查看驾驶舱、报表和风险预警</td><td>只看经营结果，不操作业务数据</td></tr>
                </tbody>
              </table></div>
              <a class="btn btn-sm btn-outline-primary" href="/users"><i class="bi bi-people-fill"></i> 去操作员管理</a>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-success"><i class="bi bi-check2-square"></i> 2.0 验收主线</div>
            <div class="card-body">
              <ol class="mb-3">
                <li><strong>空间合同档案</strong>：维护商户编号、店铺、使用方、面积、合同期、续签、停用和附件，作为行政备查。</li>
                <li><strong>商业收费主入口</strong>：商户/商业对象日常出账回到“商业收费 + 收费项目”，合同档案不再作为强制出账入口。</li>
                <li><strong>导入核对与修正</strong>：Excel 导入先预览、修正、确认，不直接写库。</li>
                <li><strong>云端技术备查</strong>：PostgreSQL schema、seed SQL、迁移摘要保留给管理员，不作为当前开发主线。</li>
                <li><strong>桌面稳定版收口</strong>：停止新增业务板块，优先做现有模块统一优化、真实使用防错和交付冻结。</li>
                <li><strong>底层安全检查</strong>：权限、备份、系统健康、全量测试都通过后再交付。</li>
              </ol>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-primary" href="/merchant_contracts">空间合同档案</a>
                <a class="btn btn-sm btn-outline-success" href="/delivery_center/contracts">合同闭环验收</a>
                <a class="btn btn-sm btn-outline-success" href="/delivery_center/import">导入验收</a>
                <a class="btn btn-sm btn-outline-success" href="/delivery_center/checklist">总验收清单</a>
                <a class="btn btn-sm btn-outline-success" href="/delivery_center/staff_guide">员工操作说明</a>
                <a class="btn btn-sm btn-outline-success" href="/delivery_center/a_phase_review">收口审查</a>
                <a class="btn btn-sm btn-outline-success" href="/delivery_center/c_phase_review">稳定版收口建议</a>
                <a class="btn btn-sm btn-outline-primary" href="/import">数据导入</a>
                <a class="btn btn-sm btn-outline-primary" href="/cloud_schema">云端技术备查</a>
                <a class="btn btn-sm btn-outline-primary" href="/system_health">底层安全检查</a>
              </div>
            </div></div>
          </div>
        </div>
        <div class="card mt-3"><div class="card-header"><i class="bi bi-signpost-split"></i> 当前阶段建议：桌面稳定版收口</div>
        <div class="card-body">
          <div class="row g-3">
            <div class="col-md-4"><div class="p-3 border rounded h-100"><strong>1. 现有模块统一优化</strong><div class="small text-muted mt-1">统一商户编号、单价、面积、周期、出账状态等业务词和金额口径。</div></div></div>
            <div class="col-md-4"><div class="p-3 border rounded h-100"><strong>2. 真实使用防错</strong><div class="small text-muted mt-1">按导入/录入、抄表、出账、收费、报表、结账顺序优化员工日常流程。</div></div></div>
            <div class="col-md-4"><div class="p-3 border rounded h-100"><strong>3. 交付冻结</strong><div class="small text-muted mt-1">完成 UI、金额、权限、导入、报表专项 QA 后冻结 2.0 稳定版。<br><a href="/delivery_center/c_phase_review">查看稳定版收口</a></div></div></div>
          </div>
        </div></div>
        """, "delivery_center"))

    def _delivery_contract_acceptance(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        self._html(self._page("空间合同档案验收", """
        <div class="alert alert-success border-success">
          <strong><i class="bi bi-file-earmark-check"></i> 空间合同档案验收</strong>
          <div class="small mt-1">用于稳定版收口：核对空间合同档案是否只承担行政备查，日常收费仍从物业收费或商业收费生成账单。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-diagram-3"></i> 员工操作流程</div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>1. 新增档案</strong><div class="small text-muted mt-1">一次录入商户编号、店铺、使用方、业态、面积、合同期和单价信息。</div></div></div>
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>2. 资料备查</strong><div class="small text-muted mt-1">详情页查看合同、续签、停用、附件和历史账单，不作为员工日常收费入口。</div></div></div>
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>3. 去商业收费</strong><div class="small text-muted mt-1">商户/商业对象日常收费从商业收费选择收费项目后生成账单。</div></div></div>
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>4. 收费登记</strong><div class="small text-muted mt-1">账单生成后进入收费、收据、发票、报表和期末结账流程。</div></div></div>
            </div>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-warning"><i class="bi bi-shield-check"></i> 验收检查点</div>
            <div class="card-body">
              <ul class="mb-3">
                <li><strong>押金单价口径</strong>：押金按面积 × 押金单价展示，员工能核对但不会被强制引导合同出账。</li>
                <li><strong>列表操作降噪</strong>：合同列表只保留详情/编辑，续签、账单、停用放到详情页操作区。</li>
                <li><strong>档案不自动收费</strong>：保存空间合同档案不会自动生成应收账单。</li>
                <li><strong>历史账单</strong>：详情页保留历史合同账单追溯，不删除旧数据。</li>
                <li><strong>到期提醒</strong>：合同到期、停用、续签信息仍进入预警/备查。</li>
              </ul>
              <a class="btn btn-sm btn-outline-primary" href="/merchant_contracts">开始验收空间合同档案</a>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-info"><i class="bi bi-arrow-repeat"></i> 生命周期检查</div>
            <div class="card-body">
              <ul class="mb-3">
                <li><strong>续签合同</strong>：续签后创建新合同，可上传新合同扫描件。</li>
                <li><strong>退租协议</strong>：停用合同时可上传退租协议，历史账单保留。</li>
                <li><strong>附件追溯</strong>：合同详情展示合同附件、续签合同、退租协议。</li>
                <li><strong>停用边界</strong>：停用合同不能继续预览出账。</li>
              </ul>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-primary" href="/alert_center">合同档案预警</a>
                <a class="btn btn-sm btn-outline-primary" href="/bills">账单管理</a>
                <a class="btn btn-sm btn-outline-primary" href="/payments">缴费记录</a>
              </div>
            </div></div>
          </div>
        </div>
        <div class="alert alert-light border mt-3 small">
          <i class="bi bi-info-circle"></i> 交付口径：住宅等基础物业收费流程保持稳定；商户/商业对象日常收费以商业收费为核心；空间合同档案只作行政备查和历史追溯。
        </div>
        """, "delivery_center"))

    def _delivery_checklist(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        self._html(self._page("2.0 交付验收清单", """
        <div class="alert alert-primary border-primary">
          <strong><i class="bi bi-clipboard2-check"></i> 2.0 交付验收清单</strong>
          <div class="small mt-1">2.0 桌面稳定版收口总入口：把合同、导入、权限、云端技术备查、备份、系统健康和全量测试放在同一张清单里核对。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-list-check"></i> 2.0 稳定版必须通过的交付门槛</div>
          <div class="card-body">
            <div class="table-responsive"><table class="table table-sm align-middle">
              <thead><tr><th>验收项</th><th>通过标准</th><th>检查入口</th></tr></thead>
              <tbody>
                <tr><td><strong>合同闭环</strong></td><td>空间合同档案可新增、编辑、续签、停用、附件和历史账单追溯；日常账单从物业收费/商业收费生成。</td><td><a href="/delivery_center/contracts">合同闭环验收</a></td></tr>
                <tr><td><strong>导入闭环</strong></td><td>Excel 上传后先字段识别、调整字段映射、数据核对与修正；确认导入后才写库。</td><td><a href="/delivery_center/import">导入核对验收</a></td></tr>
                <tr><td><strong>权限闭环</strong></td><td>系统管理员、财务、收费员、客服业务编辑、管理层只读按岗位访问；普通岗位不能进入交付中心。</td><td><a href="/users">操作员管理</a></td></tr>
                <tr><td><strong>云端技术备查</strong></td><td>PostgreSQL schema、seed SQL、迁移摘要仅保留给管理员/技术人员查看；当前不作为业务主线。</td><td><a href="/cloud_schema">云端技术备查</a></td></tr>
                <tr><td><strong>备份恢复</strong></td><td>关键写入前自动备份，人工备份/恢复入口可用，交付前不得缺备份。</td><td><a href="/backups">备份恢复</a></td></tr>
                <tr><td><strong>系统健康</strong></td><td>数据库、账单、收款、异常数据、权限边界检查无高风险问题。</td><td><a href="/system_health">系统健康</a></td></tr>
                <tr><td><strong>全量测试</strong></td><td>每完成一个模块都运行底层验证；当前命令：<code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest</code>。</td><td>当前稳定版基线：431 passed, 4 skipped</td></tr>
              </tbody>
            </table></div>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-success"><i class="bi bi-check-circle"></i> 可以交给用户试用前</div>
            <div class="card-body">
              <ol class="mb-0">
                <li>先由管理员按本清单逐项点开检查。</li>
                <li>财务重点验证合同闭环、账单金额、服务期和收款记录。</li>
                <li>客服业务编辑重点验证房间、商户、合同、抄表、导入和欠费查询是否清晰。</li>
                <li>管理层重点验证驾驶舱、预警和对账报表是否能看懂。</li>
              </ol>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-warning"><i class="bi bi-exclamation-triangle"></i> 进入 2.0 桌面稳定版收口</div>
            <div class="card-body">
              <ul class="mb-0">
                <li><strong>停止新增业务板块</strong>：当前只补主流程缺口，不再扩 SaaS、业主端支付、小程序等新范围。</li>
                <li><strong>进入 2.0 桌面稳定版收口</strong>：重点统一现有模块文案、金额口径、权限、防错和打包交付。</li>
                <li><strong>冻结后只做 P0/P1 修复</strong>：启动失败、金额错误、数据丢失、权限绕过、主流程阻塞、打包不可用。</li>
              </ul>
            </div></div>
          </div>
        </div>
        <div class="alert alert-light border mt-3 small">
          <i class="bi bi-info-circle"></i> 交付口径：当前目标是本地桌面 App 正式可用；云端技术备查保留，不继续扩展新业务范围。
        </div>
        """, "delivery_center"))

    def _delivery_import_acceptance(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        self._html(self._page("导入核对与修正验收", """
        <div class="alert alert-success border-success">
          <strong><i class="bi bi-file-spreadsheet"></i> 导入核对与修正验收</strong>
          <div class="small mt-1">用于 A 阶段交付收口：把 Excel 导入说明为“先识别、先核对、先修正，确认后再写入”，避免员工误以为上传后已经入库。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-diagram-3"></i> 员工操作流程</div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>1. 下载导入模板</strong><div class="small text-muted mt-1">模板字段按房间管理口径准备：楼栋、单元/座、房号/铺位、类别、面积、业主/商户、电话、合同日期等。</div></div></div>
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>2. 字段识别</strong><div class="small text-muted mt-1">系统自动识别 Excel 原始列，并在核对表表头显示来源列名。</div></div></div>
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>3. 调整字段映射</strong><div class="small text-muted mt-1">识别不准时展开映射设置，重新生成预览，仍不写入数据库。</div></div></div>
              <div class="col-md-3"><div class="p-3 border rounded h-100"><strong>4. 数据核对与修正</strong><div class="small text-muted mt-1">直接在核对表修正楼栋、房号、面积、业主、电话、合同日期等关键字段。</div></div></div>
            </div>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-warning"><i class="bi bi-shield-check"></i> 验收检查点</div>
            <div class="card-body">
              <ul class="mb-3">
                <li><strong>第一屏就是数据核对与修正</strong>：用户看到的是最终将写入系统的业务字段，不是原始 Excel 杂表。</li>
                <li><strong>预览阶段不写入数据库</strong>：上传、字段识别、调整字段映射、重新生成核对表都只能预览。</li>
                <li><strong>确认导入后才写入</strong>：只有点击“确认导入并生成结果”后，才写入房间、业主或商户基础资料。</li>
                <li><strong>历史金额不会自动入账</strong>：模板里的历史金额只能作为备注/参考，不自动生成应收或收款。</li>
                <li><strong>问题行/重复数据提示</strong>：楼栋房号缺失、面积异常、电话异常、疑似重复必须提示给员工核对。</li>
              </ul>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-primary" href="/import">开始导入验收</a>
                <a class="btn btn-sm btn-outline-success" href="/import/template/basic.xlsx">下载导入模板</a>
              </div>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-info"><i class="bi bi-list-check"></i> 核对口径</div>
            <div class="card-body">
              <ul class="mb-3">
                <li><strong>房间管理表头一致</strong>：导入核对表应覆盖楼栋、单元/座、房号/铺位、类别、面积、业主/商户、电话、合同日期、备注。</li>
                <li><strong>映射效果可见</strong>：每个业务字段下显示“来自：Excel 原始列名”，调整映射后预览内容要变化。</li>
                <li><strong>编辑停留本页</strong>：修正单元格或行数据时，不跳转到房间管理页面。</li>
                <li><strong>确认后可追溯</strong>：导入结果页要能说明新增、更新、跳过、问题行数量。</li>
              </ul>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-sm btn-outline-primary" href="/rooms">房间管理核对</a>
                <a class="btn btn-sm btn-outline-primary" href="/system_health">底层安全检查</a>
              </div>
            </div></div>
          </div>
        </div>
        <div class="alert alert-light border mt-3 small">
          <i class="bi bi-info-circle"></i> 交付口径：导入功能只做基础资料核对写入；收款明细、历史欠费、账单生成仍走独立收费或出账流程，避免金额被误导入。
        </div>
        """, "delivery_center"))
