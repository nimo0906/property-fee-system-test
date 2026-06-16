# 2.0 收费系统最终总结

## 一、最终状态

截至 2026-06-17，本次 2.0 收费系统升级已经完成源码同步、旧仓库清理、验证和 GitHub 推送。

- GitHub 仓库：`nimo0906/property-fee-system-test`
- 分支：`feat/commercial-merchant-billing`
- 最新提交：`a35eb6e chore: 同步2.0版本并清理旧交付产物`
- 远端确认：GitHub 已能读取该提交和关键文件。
- 本地旧仓库：`/Users/nimo/Documents/物业管理系统测试版本/测试版本`
- 2.0 来源目录：`/Users/nimo/Documents/物业管理系统测试版本/版本升级2.0`

## 二、本次 2.0 完成的核心成果

### 1. 从功能开发转为交付收口

2.0 不再只是增加功能，而是把收费系统推进到可以内部验收和交付试用的状态。重点从“能不能跑”转为：

- 能否作为桌面 App 使用。
- 能否在 macOS / Windows 两端交付。
- 能否保护真实数据和本地数据库。
- 能否让员工按真实工作顺序操作。
- 能否在冻结后只修高优先级问题。

### 2. 桌面 App 优先

本次继续明确：后续优化默认以桌面 App / EXE 交付为目标，而不是只满足网页预览。

已保留和强化的交付入口包括：

- `desktop_app.py`
- `desktop_runtime.py`
- `build_macos_app.command`
- `build_windows_exe.bat`
- `property_fee_system_macos.spec`
- `property_fee_system.spec`
- `scripts/desktop_release_check.py`

### 3. 数据和源码分离

本次同步时明确移出旧仓库中的运行数据：

- `property.db`
- `property.db-wal`
- `property.db-shm`
- `backups/`
- `真实数据/`

这些内容已备份到：

```text
/Users/nimo/Documents/物业管理系统测试版本/测试版本-backup-before-v2-sync-20260616-222759/_moved_runtime_data/
```

源码仓库不再保留本地运行数据库、备份和真实客户资料。

### 4. 源码清洁和旧产物清理

本次把 2.0 成果同步回原 Git 仓库，同时清理旧的构建、缓存、解包发布目录和临时产物。仓库保留重点转为：

- 源码
- 测试
- 文档
- 打包脚本
- 必要 release zip
- 发布检查脚本

不再把 `build/`、`dist/`、`.pytest_cache/`、旧解包 release 目录长期放入仓库。

### 5. 版本冻结和发布纪律

2.0 已形成清晰冻结纪律：

- 冻结后只接受 P0/P1。
- P0：无法启动、数据丢失、金额/账期错误、权限绕过、桌面包不可用。
- P1：主流程阻塞、筛选/分页明显错误、状态错误、导出/打印明显错误。
- P2/P3 进入后续 backlog，不继续挤进本次交付。

相关文档：

- `docs/release-freeze-v2.0.2.md`
- `docs/release-freeze-v2.0.3.md`
- `docs/release-freeze-v2.0.4.md`
- `docs/release-update-policy.md`

## 三、验证结果

本次同步和清理后已运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server/*.py server.py desktop_app.py desktop_runtime.py scripts/*.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/desktop_release_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/source_tree_check.py
```

结果：

```text
py_compile：通过
pytest：487 passed, 4 skipped in 58.10s
desktop_release_check.py：PASS
source_tree_check.py：PASS
```

`source_tree_check.py` 对部分测试文件超过 300 行给出 WARN，但不阻塞交付。

## 四、GitHub 推送结论

最终 GitHub 推送成功：

```text
62b202a..a35eb6e  feat/commercial-merchant-billing -> feat/commercial-merchant-billing
```

过程中确认的经验：

- 原仓库确实曾经成功推送过 GitHub。
- 本机 GitHub SSH key 已配置在 GitHub，且具备读写权限。
- 中间失败不是仓库不存在，也不是 key 被删除，而是当前网络/代理把 GitHub SSH 流量导向 `198.18.x.x` 并拦截。
- HTTPS push 需要 Personal Access Token，且 token 必须有足够权限；否则会返回 403。
- 最终恢复 SSH 网络后，直接用原 SSH remote 推送成功。

当前推荐 remote：

```text
git@github.com:nimo0906/property-fee-system-test.git
```

## 五、这次和 1.0 的区别

### 1.0 阶段

1.0 更像是验证系统可行性：

- 核心收费流程能跑。
- 本地服务能打开。
- 桌面 App 初步打包。
- 判断项目是否值得继续投入。

关键词是：

```text
能跑、能验证、能继续做
```

### 2.0 阶段

2.0 更像是交付工程：

- 业务主流程收口。
- macOS / Windows 打包链路。
- GitHub 同步。
- release / manifest / 更新策略。
- 数据目录隔离。
- 源码卫生。
- 权限与隐藏模块治理。
- 内部验收冻结。
- Windows 服务器共享部署说明。

关键词是：

```text
能交付、能部署、能维护、能给真实用户试用
```

## 六、用户做事风格变化

本次最明显的变化是：用户从“需求提出者”逐步变成“产品负责人 + 业务验收人”。

体现为：

- 更关注真实业务边界，而不是抽象功能。
- 更关注员工和客户怎么实际打开、部署、使用。
- 更关注数据安全、金额准确、版本冻结和交付物。
- 更能接受先做内部稳定版，再把云端、支付、移动端等放入后续路线。
- 对形式化流程不执着，但对结果、验证和可交付性要求更高。

## 七、后续建议

1. 当前 2.0 先保持稳定，不再轻易加大模块。
2. 真实试用阶段只记录 P0/P1，其他先进入 backlog。
3. Windows 正式 EXE 仍应在 Windows 环境实际打包并验收。
4. 后续若做云端、支付、业主端，应先做独立方案，不要直接打乱当前桌面稳定版。
5. 每次发布前继续执行固定验证命令，不能只靠手感判断完成。
