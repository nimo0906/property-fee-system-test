#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static commercial edition roadmap pages."""

from server.base import BaseHandler
from server.db import h


class CommercialPlanMixin(BaseHandler):
    def _license_plan(self):
        self._html(self._page("商业授权方案", """
        <div class="page-intro"><div><p class="text-muted mb-1 small">COMMERCIAL LICENSE</p><h4 class="mb-0"><i class="bi bi-key"></i> 正式商业版授权设计</h4><p class="text-muted small mb-0 mt-2">当前阶段先落设计文档和管理入口，不接入真实授权服务器，不影响本地桌面版离线使用。</p></div></div>
        <div class="row g-3">
          <div class="col-md-4"><div class="card h-100"><div class="card-header">1. 授权对象</div><div class="card-body small"><ul><li>客户：物业公司/运营公司</li><li>项目：一个或多个小区/商场</li><li>设备：本地桌面主机指纹</li><li>账号：本机内部操作员</li></ul></div></div></div>
          <div class="col-md-4"><div class="card h-100"><div class="card-header">2. 授权形态</div><div class="card-body small"><ul><li>试用版：30天/限定账单量</li><li>标准版：单项目本地桌面</li><li>专业版：多项目、本地局域网访问</li><li>云端版：按租户/用户数订阅</li></ul></div></div></div>
          <div class="col-md-4"><div class="card h-100"><div class="card-header">3. 校验策略</div><div class="card-body small"><ul><li>本地优先：离线可启动</li><li>定期联网刷新授权</li><li>宽限期避免误锁客户</li><li>授权异常只限制新增/导出等高价值动作</li></ul></div></div></div>
        </div>
        <div class="card mt-3"><div class="card-header">落地阶段</div><div class="card-body"><ol class="mb-0"><li>第1阶段：配置化品牌、版本、收据抬头、授权方案文档。</li><li>第2阶段：本地 license 文件读取和只读状态展示。</li><li>第3阶段：授权服务器、订单后台、设备解绑、审计记录。</li><li>第4阶段：云端租户计费、在线续费、自动开通。</li></ol></div></div>
        """, "license_plan"))

    def _cloud_deployment_plan(self):
        self._html(self._page("云端部署方案", """
        <div class="page-intro"><div><p class="text-muted mb-1 small">CLOUD DEPLOYMENT</p><h4 class="mb-0"><i class="bi bi-cloud-upload"></i> 云端部署方案</h4><p class="text-muted small mb-0 mt-2">当前本地桌面版保持稳定；云端作为商业版后续路线，不和本机 SQLite 直接混用。</p></div></div>
        <div class="row g-3">
          <div class="col-md-6"><div class="card h-100"><div class="card-header">推荐架构</div><div class="card-body small"><ul><li>Web/API：Python 服务拆分为可部署后端</li><li>数据库：PostgreSQL，多租户 tenant_id 隔离</li><li>文件：对象存储保存导入文件、合同附件、导出包</li><li>部署：HTTPS 域名、反向代理、自动备份、监控告警</li></ul></div></div></div>
          <div class="col-md-6"><div class="card h-100"><div class="card-header">迁移原则</div><div class="card-body small"><ul><li>先保留桌面版作为稳定交付物</li><li>云端先做只读迁移演练和数据校验</li><li>账号体系改为租户用户，不沿用本机申请账号逻辑</li><li>金额、账期、回款、收据必须双库对账一致后再上线</li></ul></div></div></div>
        </div>
        <div class="card mt-3"><div class="card-header">分阶段路线</div><div class="card-body"><ol class="mb-0"><li>云端合同：整理 PostgreSQL schema、迁移脚本、租户边界。</li><li>预生产：导入脱敏样例数据，跑账单/收款/报表对账。</li><li>试点客户：只开一个项目，保留桌面回退。</li><li>商业上线：加监控、备份、授权计费、客户支持流程。</li></ol></div></div>
        """, "cloud_deployment_plan"))
