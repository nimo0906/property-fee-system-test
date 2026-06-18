#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial edition setup and license pages."""

from desktop_runtime import get_app_data_dir
from server.app_version import APP_BUILD, APP_VERSION
from server.base import BaseHandler
from server.brand_config import PRODUCT_NAME
from server.db import h, qs
from server.license_status import read_license_status
from server.commercial_config import read_setup_config, save_setup_config


class CommercialSetupMixin(BaseHandler):
    def _license_status(self):
        data = read_license_status()
        badge = "success" if data["status_label"] == "已授权" else ("danger" if data["status_label"] in ("已过期", "授权异常") else "warning")
        self._html(self._page("授权状态", f"""
        <div class="page-intro"><div><p class="text-muted mb-1 small">LOCAL LICENSE</p><h4 class="mb-0"><i class="bi bi-patch-check"></i> 授权状态</h4><p class="text-muted small mb-0 mt-2">只读展示当前本机授权配置；本阶段不接真实授权服务器，不会上传本机业务数据。</p></div></div>
        <div class="row g-3">
          <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">授权状态</div><strong><span class="badge text-bg-{badge}">{h(data['status_label'])}</span></strong></div></div>
          <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">版本</div><strong>{h(data.get('edition'))}</strong></div></div>
          <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">产品版本</div><strong>{h(APP_VERSION)} / {h(APP_BUILD)}</strong></div></div>
        </div>
        <div class="card mt-3"><div class="card-header">授权信息</div><div class="card-body">
          <div class="table-responsive"><table class="table table-sm align-middle mb-0"><tbody>
            <tr><th style="width:160px">产品名称</th><td>{h(PRODUCT_NAME)}</td></tr>
            <tr><th>客户名称</th><td>{h(data.get('customer_name'))}</td></tr>
            <tr><th>授权方式</th><td>{h(data.get('license_model_label'))}</td></tr>
            <tr><th>项目数</th><td>{h(data.get('projects'))}</td></tr>
            <tr><th>账号数</th><td>{h(data.get('seats'))}</td></tr>
            <tr><th>授权设备数</th><td>{h(data.get('device_limit'))} 台</td></tr>
            <tr><th>离线宽限期</th><td>{h(data.get('offline_grace_days'))} 天</td></tr>
            <tr><th>到期日期</th><td>{h(data.get('expires_at') or '未设置')}</td></tr>
            <tr><th>到期策略</th><td>{'到期后不能进入系统' if data.get('access_blocked') else '授权有效或试用中'}</td></tr>
            <tr><th>授权码</th><td><code>{h(data.get('masked_key'))}</code></td></tr>
            <tr><th>授权文件</th><td><code>{h(data.get('license_file'))}</code></td></tr>
            <tr><th>说明</th><td>{h(data.get('notes'))}</td></tr>
          </tbody></table></div>
        </div></div>
        <div class="alert alert-light border mt-3 small"><i class="bi bi-info-circle"></i> 正式商业版规则：按年授权，默认 3 台设备，离线宽限期 7 天，到期后禁止进入系统；本机不保存云端密钥，不在日志输出敏感授权明文。</div>
        """, "license_status"))

    def _first_run_guide(self):
        data_dir = get_app_data_dir()
        setup = read_setup_config()
        checked_commercial = 'checked' if setup.get('enable_commercial_billing') else ''
        checked_meter = 'checked' if setup.get('enable_meter_reading') else ''
        checked_parking = 'checked' if setup.get('enable_parking') else ''
        cycle_options = ''.join(f'<option value="{v}"{" selected" if setup.get("default_billing_cycle") == v else ""}>{label}</option>' for v, label in (("monthly", "月付"), ("quarterly", "季付"), ("semiannual", "半年付"), ("annual", "年付")))
        status_badge = '<span class="badge text-bg-success">已初始化</span>' if setup.get('initialized') else '<span class="badge text-bg-warning">未初始化</span>'
        self._html(self._page("首次使用引导", f"""
        <div class="page-intro"><div><p class="text-muted mb-1 small">FIRST RUN</p><h4 class="mb-0"><i class="bi bi-flag"></i> 首次使用引导</h4><p class="text-muted small mb-0 mt-2">用于正式交付前检查：先账号安全、再基础资料、再收费流程、最后备份和授权。</p></div></div>
        <div class="card mb-3"><div class="card-header d-flex justify-content-between"><span>初始化配置</span>{status_badge}</div><div class="card-body">
          <form method="POST" action="/first_run_setup" class="row g-3">
            <div class="col-md-6"><label class="form-label">公司名称 *</label><input name="company_name" class="form-control" value="{h(setup.get('company_name'))}" required></div>
            <div class="col-md-6"><label class="form-label">项目名称 *</label><input name="project_name" class="form-control" value="{h(setup.get('project_name'))}" required></div>
            <div class="col-md-4"><label class="form-label">默认收费周期</label><select name="default_billing_cycle" class="form-select">{cycle_options}</select></div>
            <div class="col-md-4"><label class="form-label">默认物业费单价</label><input name="default_property_rate" class="form-control" value="{h(setup.get('default_property_rate'))}" placeholder="例如 3.50"></div>
            <div class="col-md-4"><label class="form-label">功能开关</label><div class="form-check"><input class="form-check-input" type="checkbox" name="enable_commercial_billing" {checked_commercial}> <label class="form-check-label">启用商业收费</label></div><div class="form-check"><input class="form-check-input" type="checkbox" name="enable_meter_reading" {checked_meter}> <label class="form-check-label">启用水电抄表</label></div><div class="form-check"><input class="form-check-input" type="checkbox" name="enable_parking" {checked_parking}> <label class="form-check-label">启用车位/停车</label></div></div>
            <div class="col-12"><button class="btn btn-primary"><i class="bi bi-check2-circle"></i> 保存初始化配置</button><span class="small text-muted ms-2">配置保存到本机数据目录，不写入程序包。</span></div>
          </form>
        </div></div>
        <div class="card"><div class="card-header">正式使用前 8 步</div><div class="card-body"><ol class="mb-0">
          <li>使用 <code>admin / admin123</code> 登录后，立即进入「操作员管理」修改默认管理员密码。</li>
          <li>按岗位创建账号：系统管理员、财务、收费员、客服业务编辑、管理层只读。</li>
          <li>进入「收费项目」核对物业费、水费、电费、垃圾费、押金等单价和计费方式。</li>
          <li>进入「数据导入」下载通用模板，先预览核对，再确认导入真实资料。</li>
          <li>按“收费对象/商户 → 抄表 → 出账 → 收费登记 → 收据/报表”的顺序跑一遍小样本。</li>
          <li>进入「数据备份」创建一次人工备份，并确认备份文件位置。</li>
          <li>进入「授权状态」核对客户名称、版本、到期日期；试用版不影响本地数据。</li>
          <li>正式交付前运行桌面发布检查和全量测试，确认 App/Exe 可启动。</li>
        </ol></div></div>
        <div class="row g-3 mt-1">
          <div class="col-md-6"><div class="card h-100"><div class="card-header">本机数据目录</div><div class="card-body small"><code>{h(str(data_dir))}</code><div class="text-muted mt-2">数据库、备份、导入缓存、导出文件和日志都保存在这里，不写入 App 包。</div></div></div></div>
          <div class="col-md-6"><div class="card h-100"><div class="card-header">推荐入口</div><div class="card-body d-flex gap-2 flex-wrap"><a class="btn btn-sm btn-outline-primary" href="/users">操作员管理</a><a class="btn btn-sm btn-outline-primary" href="/fee_types">收费项目</a><a class="btn btn-sm btn-outline-primary" href="/import">数据导入</a><a class="btn btn-sm btn-outline-primary" href="/backups">数据备份</a><a class="btn btn-sm btn-outline-primary" href="/license_status">授权状态</a></div></div></div>
        </div>
        """, "first_run_guide"))

    def _first_run_setup_post(self, d):
        save_setup_config({
            "company_name": qs(d, "company_name"),
            "project_name": qs(d, "project_name"),
            "default_billing_cycle": qs(d, "default_billing_cycle", "monthly"),
            "default_property_rate": qs(d, "default_property_rate"),
            "enable_commercial_billing": bool(qs(d, "enable_commercial_billing")),
            "enable_meter_reading": bool(qs(d, "enable_meter_reading")),
            "enable_parking": bool(qs(d, "enable_parking")),
        })
        self._audit("first_run_setup", "config", None, None, {"saved": True}, "保存首次初始化配置")
        return self._redirect("/first_run_guide?flash=初始化配置已保存")
