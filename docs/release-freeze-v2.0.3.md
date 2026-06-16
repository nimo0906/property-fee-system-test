# 2.0.3 稳定版冻结记录（源码验收，不含桌面打包）

## 冻结日期

2026-06-14

## 冻结口径

本次冻结目标是完成 2.0 桌面稳定版源码层面的收口验收：

- 保持当前业务范围，不继续扩展新业务模块。
- 桌面 App 打包暂不执行，等待用户确认后再做。
- 本次只确认源码服务、核心页面、数据路径隔离、源码卫生、测试和发布检查。

## 本次已完成

- 源码目录残留清理：运行数据库、WAL/SHM、runtime data、缓存、日志不留在源码目录。
- 隐藏模块策略固化：`docs/hidden-module-policy.md` 已纳入发布检查。
- 结构加固：Python 单文件不超过 300 行；大型 CSS/test/server 文件已拆分。
- CSS 拆分：`static/app.css` 保留为轻入口，实际样式拆到多个小文件。
- 测试拆分：大型集成测试拆分为多个小文件，测试恢复通过。
- 源码卫生守卫：`scripts/source_tree_check.py` 已加入，并纳入 `scripts/desktop_release_check.py`。
- 统一导入工作台、合同档案、商业收费等前序 2.0 收口改动保留。

## 源码服务验收

使用临时干净运行数据目录启动，避免污染用户真实数据：

```bash
PM_PORT=5014 PM_DATA_DIR=/tmp/property_2_0_3_smoke PYTHONUNBUFFERED=1 python3 server.py
```

启动结果：

- 服务地址：`http://127.0.0.1:5014`
- 登录账号：`admin / admin123`（临时干净数据目录内默认账号）
- 自动备份创建成功

核心页面 HTTP 验收均返回 200：

- `/`
- `/rooms`
- `/billing`
- `/commercial_billing`
- `/merchant_contracts`
- `/import`
- `/bills`
- `/payments`
- `/reports`
- `/backups`
- `/system_health`

浏览器人工验收：

- 登录页可打开。
- 收费工作台可打开。
- 左侧菜单、经营看板、默认密码提醒、主操作按钮和核心区块正常显示。

## 数据路径隔离验收

临时验收数据目录：

```text
/tmp/property_2_0_3_smoke
```

运行时目录结构：

```text
/tmp/property_2_0_3_smoke/database/property.db
/tmp/property_2_0_3_smoke/backups/
/tmp/property_2_0_3_smoke/imports/
/tmp/property_2_0_3_smoke/exports/
/tmp/property_2_0_3_smoke/updates/
/tmp/property_2_0_3_smoke/logs/
```

桌面运行诊断显示：

```text
Data directory: /tmp/property_2_0_3_smoke
Database: /tmp/property_2_0_3_smoke/database/property.db
Backup directory: /tmp/property_2_0_3_smoke/backups
Import cache: /tmp/property_2_0_3_smoke/imports
Export directory: /tmp/property_2_0_3_smoke/exports
Update directory: /tmp/property_2_0_3_smoke/updates
Log directory: /tmp/property_2_0_3_smoke/logs
Missing dependencies: none
```

源码目录卫生检查：

```bash
python3 scripts/source_tree_check.py
```

结果：

```text
PASS source tree hygiene
```

## 自动化验证

### Python 编译检查

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server/*.py server.py desktop_app.py desktop_runtime.py scripts/*.py
```

结果：通过。

### 全量测试

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q
```

结果：

```text
413 passed, 4 skipped in 50.16s
```

### 桌面发布资源检查

```bash
python3 scripts/desktop_release_check.py
```

结果：通过，包含：

- desktop app entry
- desktop runtime
- macOS build script/spec
- Windows build script/spec
- desktop icons
- release checklist
- hidden module policy
- source tree hygiene guard

### 源码卫生检查

```bash
python3 scripts/source_tree_check.py
```

结果：

```text
PASS source tree hygiene
```

## 当前明确未做

- 未重打包 macOS `.app`。
- 未打包 Windows `.exe`。
- 未生成新的客户发布 zip。

原因：用户明确要求“打包桌面 app 先不要做，等确认”。

## 冻结后规则

在用户确认进入打包前，源码层面只建议接受 P0/P1：

- 启动失败
- 数据丢失风险
- 金额/账期错误
- 权限绕过
- 主流程阻塞
- 导入确认写库异常
- 桌面运行路径污染源码目录

P2/P3 新功能继续进入后续 backlog，不进入本次冻结范围。
