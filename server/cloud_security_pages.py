#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloud deployment security baseline pages."""

from server.base import BaseHandler
from server.ui_components import render_table


class CloudSecurityPageMixin(BaseHandler):
    def _cloud_security_baseline(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        baseline_rows = """
                <tr><td><strong>HTTPS 部署说明</strong></td><td>本地仍走 127.0.0.1，云端部署必须放在 HTTPS 反向代理之后。</td><td>公网域名、TLS 证书、HTTP 跳转 HTTPS、禁止明文公网登录。</td></tr>
                <tr><td><strong>登录会话过期</strong></td><td>Cookie 使用 <code>HttpOnly</code>、<code>SameSite=Lax</code>、<code>Max-Age=86400</code>，并由 <code>cleanup_old_sessions</code> 清理过期会话。</td><td>云端继续保留 1 天会话上限，必要时再加空闲超时。</td></tr>
                <tr><td><strong>安全日志</strong></td><td>已有 <code>audit_logs</code> 表，登录、退出、导入、备份恢复、关键写入会记录操作痕迹。</td><td>云端部署前确认操作日志可检索、可导出、可按账号和时间追溯。</td></tr>
                <tr><td><strong>自动备份/恢复</strong></td><td>系统启动、每日首次使用、导入、收费、出账、恢复前都有自动备份入口。</td><td>云端需要保留自动备份策略，并演练恢复，不只生成备份文件。</td></tr>
                <tr><td><strong>敏感信息不进日志</strong></td><td>页面只展示账号、角色、业务动作和摘要，不能记录密码、密钥、支付回调私密参数。</td><td>未来迁移前检查日志字段，确认不硬编码密钥、不提交 .env、不泄露敏感信息。</td></tr>
        """
        baseline_table = render_table(
            ['检查项', '当前底座', '云端上线要求'],
            baseline_rows,
            table_class='table table-sm align-middle',
        )
        self._html(self._page("云端技术备查安全检查", f"""
        <div class="alert alert-warning border-warning">
          <strong><i class="bi bi-shield-lock"></i> 云端技术备查安全检查</strong>
          <div class="small mt-1">技术备查用于未来迁移前核对：先把 HTTPS、会话、安全日志、备份恢复和敏感信息边界说清楚，再考虑未来云端迁移。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-cloud-lock"></i> 未来迁移前必须检查</div>
          <div class="card-body">
            {baseline_table}
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-success"><i class="bi bi-link-45deg"></i> 检查入口</div>
            <div class="card-body">
              <div class="d-flex flex-wrap gap-2 mb-3">
                <a class="btn btn-sm btn-outline-primary" href="/cloud_schema">云端技术备查</a>
                <a class="btn btn-sm btn-outline-primary" href="/audit_logs">安全日志</a>
                <a class="btn btn-sm btn-outline-primary" href="/backups">备份恢复</a>
                <a class="btn btn-sm btn-outline-primary" href="/system_health">系统健康</a>
              </div>
              <p class="small text-muted mb-0">本轮只做员工后台云端底座，不开放业主端公网支付闭环，不接真实微信/支付宝回调。</p>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-info"><i class="bi bi-terminal"></i> 验证基线</div>
            <div class="card-body">
              <p class="mb-2">技术备查验证基线：</p>
              <div class="p-3 bg-light border rounded small">
                <code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest</code><br>
                <strong>431 passed, 4 skipped</strong>
              </div>
            </div></div>
          </div>
        </div>
        """, "delivery_center"))

    def _cloud_go_live_checklist(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        checklist_rows = """
                <tr><td><strong>PostgreSQL 数据底座</strong></td><td>完成 SQLite → PostgreSQL 迁移校验，业主、房间、账单、收款、欠费金额一致。</td><td><a href="/cloud_schema">云端技术备查</a></td></tr>
                <tr><td><strong>HTTPS 与域名</strong></td><td>公网员工后台必须绑定正式域名和 TLS 证书，禁止明文公网登录。</td><td><a href="/delivery_center/cloud_security">安全底座</a></td></tr>
                <tr><td><strong>登录会话</strong></td><td>保留 HttpOnly、SameSite、会话过期和清理策略，确认账号离职停用流程。</td><td><a href="/delivery_center/cloud_security">安全底座</a></td></tr>
                <tr><td><strong>安全日志</strong></td><td>登录、退出、导入、备份恢复、关键写入可追溯，日志不记录密码和密钥。</td><td><a href="/audit_logs">安全日志</a></td></tr>
                <tr><td><strong>自动备份</strong></td><td>启动、每日、导入、收费、出账、恢复前自动备份策略必须保留。</td><td><a href="/backups">备份恢复</a></td></tr>
                <tr><td><strong>恢复演练</strong></td><td>未来迁移前必须用备份做一次恢复演练，确认可恢复、可核对、可回退。</td><td><a href="/backups">备份恢复</a></td></tr>
                <tr><td><strong>公网访问边界</strong></td><td>只开放员工后台公网访问，不开放业主端公网支付闭环，不接真实微信/支付宝回调。</td><td><a href="/system_health">系统健康</a></td></tr>
        """
        checklist_table = render_table(
            ['门槛', '检查口径', '入口'],
            checklist_rows,
            table_class='table table-sm align-middle',
        )
        self._html(self._page("云端技术备查检查清单", f"""
        <div class="alert alert-primary border-primary">
          <strong><i class="bi bi-cloud-upload"></i> 云端技术备查检查清单</strong>
          <div class="small mt-1">技术备查总检查入口：把 PostgreSQL、HTTPS、会话、安全日志、备份、恢复演练和公网访问边界集中核对。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-list-check"></i> 未来迁移前总门槛</div>
          <div class="card-body">
            {checklist_table}
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-success"><i class="bi bi-playbook"></i> 部署运行手册</div>
            <div class="card-body">
              <ol class="mb-0">
                <li>先导出 PostgreSQL schema 和 seed SQL，并完成迁移后一致性核对。</li>
                <li>再配置 HTTPS 反向代理、域名、证书和访问白名单。</li>
                <li>未来迁移前创建管理员、财务、收费员、客服业务编辑、管理层账号。</li>
                <li>上线当天先做手动备份，再开放员工后台公网访问。</li>
              </ol>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-warning"><i class="bi bi-signpost"></i> 下一阶段规则</div>
            <div class="card-body">
              <p class="mb-2">技术备查当前验证基线：<strong>431 passed, 4 skipped</strong></p>
              <p class="mb-0">云端相关内容仅作技术备查；当前主线继续做桌面稳定版收口。</p>
            </div></div>
          </div>
        </div>
        """, "delivery_center"))


    def _cloud_deployment_drill(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        drill_rows = """
                <tr><td><strong>PostgreSQL 真实导入演练</strong></td><td>创建空 PostgreSQL 库，下载 seed SQL 后用 <code>psql 导入 seed SQL</code>，导入后逐项核对业主、房间、账单、收款和欠费金额。</td><td>保留导入命令、成功日志、金额一致性截图。</td><td><a href="/cloud_migration.sql">seed SQL</a> · <a href="/cloud_schema">迁移核对</a></td></tr>
                <tr><td><strong>备份恢复演练</strong></td><td>未来迁移前先做手动备份，模拟恢复到临时库或临时数据目录，确认恢复后账单和收款仍一致。</td><td>保留恢复前备份、恢复结果截图、恢复后系统健康截图。</td><td><a href="/backups">备份恢复</a></td></tr>
                <tr><td><strong>HTTPS / 域名检查</strong></td><td>正式域名绑定 TLS 证书，HTTP 自动跳转 HTTPS，禁止公网明文登录。</td><td>保留域名、证书到期日、HTTPS 访问截图。</td><td><a href="/delivery_center/cloud_security">安全底座</a></td></tr>
                <tr><td><strong>安全日志与账号检查</strong></td><td>确认管理员、财务、收费员、客服业务编辑、管理层账号可登录，关键写入能进入安全日志。</td><td>保留登录、导入、备份、收费或出账审计记录截图。</td><td><a href="/audit_logs">安全日志</a></td></tr>
                <tr><td><strong>公网访问边界</strong></td><td>只开放员工后台公网访问，不开放业主端公网支付闭环，不接真实微信/支付宝回调。</td><td>保留反向代理路由和开放端口截图。</td><td><a href="/delivery_center/cloud_go_live">上线清单</a></td></tr>
                <tr><td><strong>回退方案</strong></td><td>准备回退到本地桌面版或上一份云端备份的流程，明确负责人和停机窗口。</td><td>保留回退负责人、备份文件名、恢复顺序和验证结果。</td><td><a href="/system_health">系统健康</a></td></tr>
        """
        drill_table = render_table(
            ['步骤', '必须执行', '留存证据', '入口'],
            drill_rows,
            table_class='table table-sm align-middle',
        )
        self._html(self._page("云端技术备查执行单", f"""
        <div class="alert alert-primary border-primary">
          <strong><i class="bi bi-rocket-takeoff"></i> 云端技术备查执行单</strong>
          <div class="small mt-1">用于正式未来迁移前，把 PostgreSQL 真实导入、备份恢复演练、HTTPS / 域名检查和回退方案逐项执行并留证。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-primary"><i class="bi bi-list-ol"></i> 演练步骤与证据 · 演练证据留存</div>
          <div class="card-body">
            {drill_table}
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6"><div class="card h-100"><div class="card-header text-success"><i class="bi bi-check2-circle"></i> 演练通过标准</div>
          <div class="card-body"><ul class="mb-0">
            <li>PostgreSQL 导入后金额、数量与 SQLite 迁移摘要一致。</li>
            <li>备份恢复后可登录、可查账单、可查收款、报表金额一致。</li>
            <li>HTTPS 可访问，HTTP 会跳转 HTTPS，Cookie 仍为 HttpOnly / SameSite。</li>
            <li>安全日志可追溯关键操作，日志不包含密码、密钥或支付私密参数。</li>
          </ul></div></div></div>
          <div class="col-lg-6"><div class="card h-100"><div class="card-header text-warning"><i class="bi bi-exclamation-triangle"></i> 不通过就不能上线</div>
          <div class="card-body"><p class="mb-2">任一项缺证据或金额不一致，都不能开放公网员工后台。</p>
          <p class="mb-0 small text-muted">本执行单只覆盖员工后台云端化；业主端、真实微信/支付宝支付、公摊水电停车等后续能力仍保持独立规划。</p></div></div></div>
        </div>
        """, "delivery_center"))

    def _delivery_b_phase_review(self):
        if not self._delivery_allowed():
            return self._redirect("/?flash=无权限访问该页面")
        review_rows = """
                <tr><td><strong>PostgreSQL 迁移校验已增强</strong></td><td>云端技术备查展示迁移后一致性核对清单，覆盖业主、房间、账单、收款、欠费金额。</td><td><a href="/cloud_schema">云端技术备查</a></td></tr>
                <tr><td><strong>云端技术备查安全已补齐</strong></td><td>HTTPS、登录会话、安全日志、自动备份/恢复、敏感信息日志边界已有检查页。</td><td><a href="/delivery_center/cloud_security">云端技术备查安全</a></td></tr>
                <tr><td><strong>云端技术备查清单已补齐</strong></td><td>PostgreSQL、HTTPS、域名、恢复演练、公网访问边界已集中到未来迁移前清单。</td><td><a href="/delivery_center/cloud_go_live">云端技术备查清单</a></td></tr>
                <tr><td><strong>备份恢复入口已确认</strong></td><td>未来迁移前可检查手动备份、自动备份、恢复演练和清理边界。</td><td><a href="/backups">备份恢复</a></td></tr>
                <tr><td><strong>安全日志入口已确认</strong></td><td>未来迁移前可检查登录、退出、导入、备份恢复和关键写入的审计记录。</td><td><a href="/audit_logs">安全日志</a></td></tr>
        """
        review_table = render_table(
            ['审查项', '当前结论', '证据入口'],
            review_rows,
            table_class='table table-sm align-middle',
        )
        self._html(self._page("技术备查完成审查", f"""
        <div class="alert alert-success border-success">
          <strong><i class="bi bi-cloud-check"></i> 技术备查完成审查</strong>
          <div class="small mt-1">技术备查目标是把云端化底座边界收口：数据迁移可核对，安全底座可检查，未来迁移前清单可执行。</div>
        </div>
        <div class="card mb-3">
          <div class="card-header text-success"><i class="bi bi-patch-check"></i> 技术备查审查结论</div>
          <div class="card-body">
            {review_table}
          </div>
        </div>
        <div class="row g-3">
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-primary"><i class="bi bi-terminal"></i> 底层验证要求</div>
            <div class="card-body">
              <p class="mb-2"><strong>进入稳定版收口前必须保持全量测试通过</strong>，当前 技术备查验证基线：</p>
              <div class="p-3 bg-light border rounded small mb-3">
                <code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest</code><br>
                <strong>431 passed, 4 skipped</strong>
              </div>
              <p class="small text-muted mb-0">后续每完成一个稳定版收口项，都要重新跑专项和全量测试。</p>
            </div></div>
          </div>
          <div class="col-lg-6">
            <div class="card h-100"><div class="card-header text-info"><i class="bi bi-bar-chart-line"></i> 下一阶段边界</div>
            <div class="card-body">
              <p><strong>继续桌面稳定版收口：金额、词汇、流程、窄屏体验</strong></p>
              <ul class="mb-0">
                <li>C 阶段重点做收费率、欠费趋势、商户贡献、费用结构和 B座/商场对比。</li>
                <li>优先增强管理层看板，再增强财务报表分析。</li>
                <li>仍保持 B座现有收费流程稳定，不引入真实支付闭环。</li>
              </ul>
              <a class="btn btn-sm btn-outline-primary mt-3" href="/reports">查看现有报表</a>
            </div></div>
          </div>
        </div>
        """, "delivery_center"))
