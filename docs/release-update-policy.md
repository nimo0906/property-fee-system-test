# 更新与发布规范

本规范用于后续所有 macOS / Windows 内测版更新，目标是避免只更新单端、遗漏 GitHub 发布资产、把本地数据或临时文件混入仓库。

## 必须同步的交付物

每次用户可见功能、安全修复、数据结构或打包逻辑变更后，必须同步处理：

1. macOS 版本
   - 构建 `dist/物业收费管理系统.app`。
   - 更新 `release/macos/物业收费管理系统-v2.0-macos/物业收费管理系统.app`。
   - 重新生成 `release/macos/物业收费管理系统-v2.0-macos.zip`。
2. Windows 版本
   - 确认 Windows 打包脚本和 spec 与源码变更同步。
   - 在 Windows 环境或 GitHub Actions 中构建 `property-billing-system-v2.0-windows.zip`。
   - 不允许只更新 macOS 而遗漏 Windows 发布资产。
3. GitHub 发布
   - commit 后立即 push。
   - GitHub Actions 必须生成并更新 `internal-latest` Release。
   - Release assets 至少包括：
     - `update_manifest.json`
     - `property-billing-system-v2.0-macos.zip`
     - `property-billing-system-v2.0-windows.zip`
   - `update_manifest.json` 中 Mac / Windows 下载地址和 SHA256 必须可验证。

## 发布前验证

每次发布前至少运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server/*.py server.py desktop_app.py desktop_runtime.py
python3 -m pytest -q
python3 scripts/desktop_release_check.py
```

涉及更新器、打包资源、启动器或 Release 的变更，还必须验证：

```bash
python3 -m pytest -q tests/test_system_update.py tests/test_desktop_app.py
```

GitHub Actions 完成后，必须验证：

1. `origin/main` 和 `internal-latest` 指向最新提交。
2. `update_manifest.json` 公网可读取。
3. macOS / Windows zip 公网可下载。
4. 下载文件 SHA256 与 manifest 一致。

## 安全要求

1. 不提交 `.env`、密钥、令牌、真实客户 Excel、`property.db`、`backups/`。
2. 更新器只允许下载 zip，并校验 SHA256 后再准备更新。
3. 解压必须防 zip 路径穿越，不能让压缩包写出目标目录。
4. 更新只替换程序文件，不覆盖用户数据目录、数据库和备份。
5. 默认只监听 `127.0.0.1`，不得为了测试改成公网监听后提交。
6. 新增管理员、备份恢复、系统修复、费率、支付等高风险入口时，必须补权限检查和测试。
7. 不在日志中输出密钥、Cookie、支付凭证、客户隐私字段。

## 代码体积要求

1. 新代码优先拆到独立模块，避免继续扩大已有大文件。
2. Python / JS / TS 单文件目标不超过 300 行；超过时必须优先考虑拆分。
3. 不写无必要的兼容层和抽象层。
4. 公共 API、数据库 schema、更新包结构变更必须有测试覆盖。

## 仓库清洁要求

1. 以下内容只允许本机存在，不进入 Git：
   - `.DS_Store`
   - `.pytest_cache/`
   - `build/`
   - `dist/`
   - `property.db*`
   - `backups/`
   - `真实数据/`
   - 本地日志和临时下载文件
2. 发布 zip 以 GitHub Release assets 为准；源码仓库中只保留必要发布说明和脚本。
3. 删除历史交付文档、发布目录或真实数据前，必须先列清单并确认。
