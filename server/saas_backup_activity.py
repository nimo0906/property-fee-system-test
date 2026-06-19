#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup and restore drill rendering helpers for SaaS backoffice."""

from server.saas_user_pages import _h


def render_backup_activity(records=None, drills=None, can_manage=False):
    return _render_restore_drills(drills or []) + _render_boundary_card(can_manage)


def _render_restore_drills(drills):
    rows = ''.join(_drill_row(row) for row in drills[-5:]) or '<tr><td colspan="4">暂无恢复演练记录</td></tr>'
    return f'''<section class="card" style="margin-top:18px"><div class="card-h">恢复演练记录</div><div class="card-b"><table><thead><tr><th>备份ID</th><th>范围</th><th>状态</th><th>创建时间</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''


def _drill_row(row):
    return f'''<tr><td>{_h(row.get('backup_id'))}</td><td>{_h(row.get('scope'))}</td><td>{_h(row.get('status'))}</td><td>{_h(row.get('created_at', ''))}</td></tr>'''


def _render_boundary_card(can_manage=False):
    permission = '只有租户管理员或平台管理员可以执行备份和提交恢复演练，普通财务、收费员和只读角色只能查看。' if can_manage else '当前角色只能查看备份和恢复演练记录，不能执行备份或恢复演练操作。'
    return f'''<section class="card" style="margin-top:18px"><div class="card-h">租户隔离与安全边界</div><div class="card-b"><p class="sub">只显示当前公司和当前项目的备份与演练，其他客户公司的备份记录不可见、不可用于恢复演练。</p><p class="sub">客户业务备份与系统配置、日志、密钥分开保存；页面只显示备份编号和演练结果，不展示真实服务器路径、数据库密码或应用密钥。</p><p class="sub">{permission}</p><a class="ghost-link" href="/backoffice/audit-logs">查看备份恢复审计</a></div></section>'''
