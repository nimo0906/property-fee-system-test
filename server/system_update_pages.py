#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Admin pages for semi-automatic desktop updates."""

from desktop_runtime import get_app_data_dir, open_path
from server.app_version import APP_VERSION
from server.base import BaseHandler
from server.db import h, qs
from server.system_update import SystemUpdateService, UpdateError


class SystemUpdateMixin(BaseHandler):
    def _system_update(self, q=None, result=None, error='', manifest_url=''):
        u = self._get_current_user() or {}
        if u.get('role') != 'admin':
            return self._redirect('/?flash=无权限访问系统更新')
        service = SystemUpdateService(manifest_url=manifest_url or None)
        packaged = service.is_packaged_runtime()
        result_html = ''
        if error:
            result_html = f'<div class="alert alert-warning"><strong>更新检查失败：</strong>{h(error)}</div>'
        elif result:
            if result.get('helper_path'):
                result_html = f'''<div class="alert alert-success"><strong>更新包已准备完成。</strong><br>
                更新助手：<code>{h(result['helper_path'])}</code><br>
                请关闭当前系统后运行该助手完成替换。旧版本会自动备份。</div>'''
            elif result.get('update_available'):
                result_html = f'''<div class="alert alert-info"><strong>发现新版本 {h(result['latest_version'])}</strong><br>
                <div class="mt-2">{h(result.get('notes') or '')}</div>
                <form method="POST" action="/system_update/prepare" class="mt-3">
                    <input type="hidden" name="manifest_url" value="{h(result.get('manifest_url') or service.manifest_url)}">
                    <button class="btn btn-success">下载并准备更新</button>
                </form></div>'''
            else:
                result_html = '<div class="alert alert-success">当前已经是最新版本。</div>'
        packaged_note = '当前为桌面打包版，可以准备半自动更新。' if packaged else '当前是源码运行模式：可检查更新，但自动替换请在打包后的 Mac/Windows 桌面版中执行。'
        status_strip = '''
            <div class="maintenance-role-strip mb-3">
              <div class="maintenance-role-pill"><span>当前版本</span><strong>{}</strong></div>
              <div class="maintenance-role-pill"><span>当前平台</span><strong>{}</strong></div>
              <div class="maintenance-role-pill"><span>运行模式</span><strong>{}</strong></div>
              <div class="maintenance-role-pill muted"><span>更新目录</span><strong>updates/</strong></div>
            </div>
        '''.format(h(APP_VERSION), h(service.platform_key), '桌面版' if packaged else '源码模式')
        self._html(self._page('系统更新', f'''
        <div class="page-intro">
          <div>
            <h2 class="mb-1">系统更新</h2>
          </div>
          <div class="export-actions">
            <a href="/backups" class="btn btn-outline-secondary btn-sm"><i class="bi bi-folder2-open"></i> 备份恢复</a>
          </div>
        </div>
        {status_strip}
        <form method="POST" action="/system_update/check" class="card mb-3 maintenance-console-card"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><strong>更新来源</strong></div><div class="card-body">
            <label class="form-label">更新清单地址</label>
            <input name="manifest_url" class="form-control" value="{h(service.manifest_url)}">
            <button class="btn btn-primary mt-3"><i class="bi bi-arrow-repeat"></i> 检查更新</button>
        </div></form>
        {result_html}
        <div class="d-flex gap-2 flex-wrap">
            <form method="POST" action="/system_update/open_folder"><button class="btn btn-outline-secondary">打开更新目录</button></form>
        </div>
        <div class="card mt-3 maintenance-console-card"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2"><strong>更新步骤</strong><span class="badge status-neutral">5 steps</span></div><div class="card-body small text-muted">
            1. 点击检查更新；2. 下载并准备更新；3. 关闭当前系统；4. 运行生成的更新助手；5. 自动备份旧版本并启动新版。
        </div></div>
        ''', 'system_update'))

    def _system_update_check(self, d):
        try:
            manifest_url = qs(d, 'manifest_url')
            result = SystemUpdateService(manifest_url=manifest_url or None).check_for_update()
            return self._system_update(result=result, manifest_url=manifest_url)
        except UpdateError as exc:
            return self._system_update(error=str(exc), manifest_url=qs(d, 'manifest_url'))

    def _system_update_prepare(self, d):
        try:
            manifest_url = qs(d, 'manifest_url')
            result = SystemUpdateService(manifest_url=manifest_url or None).prepare_from_manifest()
            return self._system_update(result=result, manifest_url=manifest_url)
        except UpdateError as exc:
            return self._system_update(error=str(exc), manifest_url=qs(d, 'manifest_url'))

    def _system_update_open_folder(self):
        folder = get_app_data_dir() / 'updates'
        folder.mkdir(parents=True, exist_ok=True)
        open_path(folder)
        return self._redirect('/system_update?flash=已打开更新目录')
