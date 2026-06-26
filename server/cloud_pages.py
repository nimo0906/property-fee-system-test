#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloud migration and PostgreSQL schema pages."""

from server.base import BaseHandler
from server.cloud_migration import build_migration_summary, export_postgres_seed_sql
from server.cloud_schema import build_postgres_schema
from server.db import h, m
from server.ui_components import render_table


class CloudPageMixin(BaseHandler):
    def _cloud_schema(self):
        sql = h(build_postgres_schema())
        summary = build_migration_summary()
        table_cards = "".join(
            f'<div class="col-md-3 col-6"><div class="summary-tile"><div class="label">{h(name)}</div><strong>{count}</strong><span class="text-muted small"> 行</span></div></div>'
            for name, count in summary["tables"].items()
        )
        check_rows = "".join(
            f"<tr><td><strong>{h(item['name'])}</strong><div class='small text-muted'>{h(item['description'])}</div></td>"
            f"<td>{h(item['sqlite_value'])}</td><td>{h(item['postgres_expected'])}</td>"
            f"<td><span class='badge status-warning'>{h(item['status'])}</span></td></tr>"
            for item in summary.get("validation_checks", [])
        )
        check_table = render_table(
            ['核对项', 'SQLite 当前值', 'PostgreSQL 导入后应一致', '状态'],
            check_rows,
            table_class='table table-sm align-middle',
        )
        money = summary["money"]
        scope = summary["scope"]
        self._html(self._page("云端技术备查", f"""
        <div class="alert alert-warning"><i class="bi bi-cloud-check"></i>
        这里是 2.0 云端 PostgreSQL 第一版 schema 合同和 SQLite 迁移校验摘要；当前仅作管理员/技术人员备查，不作为当前开发主线，本地桌面系统仍可继续运行。</div>
        <div class="metric-grid">
          <div class="metric-card primary"><div class="metric-label">账单总额</div><div class="metric-value money">¥{m(money['bill_amount_total'])}</div></div>
          <div class="metric-card success"><div class="metric-label">已收总额</div><div class="metric-value money">¥{m(money['payment_amount_total'])}</div></div>
          <div class="metric-card danger"><div class="metric-label">未收差额</div><div class="metric-value money">¥{m(money['unpaid_amount_total'])}</div></div>
          <div class="metric-card primary"><div class="metric-label">B座 / 商场房间</div><div class="metric-value">{scope['b_tower_rooms']} / {scope['mall_rooms']}</div></div>
        </div>
        <div class="card mb-3"><div class="card-header d-flex justify-content-between align-items-center">
          <span><i class="bi bi-database-check"></i> 迁移表行数校验</span>
          <a class="btn btn-sm btn-outline-success" href="/cloud_migration.sql"><i class="bi bi-download"></i> 下载 PostgreSQL seed SQL</a>
        </div><div class="card-body"><div class="row g-2">{table_cards}</div></div></div>
        <div class="card mb-3"><div class="card-header text-primary"><i class="bi bi-check2-square"></i> 迁移后一致性核对清单</div>
        <div class="card-body">
          <div class="alert alert-light border small mb-3">SQLite 当前值是本地导出前基准；PostgreSQL 导入后应一致。导入云端后逐项核对，状态先保持“待导入后核对”。</div>
          {check_table}
        </div></div>
        <pre class="cloud-schema-panel"><code>{sql}</code></pre>
        """, "cloud_schema"))

    def _cloud_migration_sql(self):
        raw = export_postgres_seed_sql().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=property_v2_postgres_seed.sql")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
