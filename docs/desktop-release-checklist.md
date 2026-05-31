# 桌面端发布验收清单

本清单用于 v2.0 桌面 app 发布前检查，覆盖 macOS 和 Windows。目标是保证本地服务、数据库、打包脚本、启动入口和回归测试在两个系统上都有明确验收步骤。

## 通用验收

1. 代码验证
   - `python3 -m pytest -q`
   - `python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py`
2. 启动验证
   - 桌面端启动后可以打开本地服务。
   - 默认优先端口为 `127.0.0.1:5001`，端口占用时允许 fallback。
   - 桌面窗口内“重启服务”可用。
3. 数据验证
   - `property.db` 可正常创建和访问。
   - `backups/` 可写。
   - 不提交 `.env`，不硬编码密钥。
4. 业务验收
   - 后台登录、账单、缴费、支付订单、业主端 H5、通知、电子票据请求页面可打开。

## macOS 验收

1. 打包脚本
   - 使用 `build_macos_app.command`。
   - 确认脚本有执行权限：`chmod +x build_macos_app.command`。
2. 启动方式
   - 双击 `.app` 后能启动桌面窗口。
   - 如被系统拦截，按 macOS 安全策略允许本地应用。
3. 网络与权限
   - 仅监听本机地址 `127.0.0.1`。
   - 首次启动后可访问后台和业主端页面。
4. 文件位置
   - 数据库、备份目录随打包资源或运行目录可写。

## Windows 验收

1. 依赖安装
   - 使用 `install_windows_dependencies.bat`。
2. 打包脚本
   - 使用 `build_windows_exe.bat`。
   - 如失败，先运行 `diagnose_windows.bat`。
3. 启动方式
   - 双击 `.exe` 后能启动桌面窗口。
   - Windows Defender 或 SmartScreen 拦截时按内部发布流程放行。
4. 路径兼容
   - 中文路径、空格路径下可启动。
   - 数据库、备份目录可写。

## 发布前命令

```bash
python3 scripts/desktop_release_check.py
python3 -m pytest -q
python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py
```

全部通过后，才允许制作 macOS / Windows 发布包。
