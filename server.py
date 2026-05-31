#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物业管理收费系统 v2.0 — 模块化版
多模型独立开票：物业费、水费、电费、生活垃圾费、公摊费各自独立出账。

使用:
    python3 server.py
    浏览器打开 http://127.0.0.1:5001
    默认账号: admin / admin123 (可通过环境变量 PM_ADMIN_PASSWORD 自定义)
    环境变量: PM_HOST (默认127.0.0.1), PM_PORT (默认5001), PM_DB_PATH
"""

import http.server

from server import Handler, db_init
from server.db import HOST, PORT
from server.backups import ensure_startup_backups


if __name__ == '__main__':
    print("=" * 50)
    print("  物业管理收费系统 v2.0 (模块化版)")
    print("  多模型独立开票解决方案")
    print("=" * 50)
    print()
    db_init()
    backups = ensure_startup_backups()
    if backups:
        print("  💾 自动备份: " + ", ".join(backups))
    server = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"  🌐 系统已启动！请在浏览器中打开：")
    print(f"     http://{HOST}:{PORT}")
    print()
    print(f"  📋 按 Ctrl+C 停止服务器")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭...")
        server.server_close()
