# 2.0.4 内部验收冻结记录

## 冻结日期

2026-06-15

## 冻结结论

- 冻结版本：v2.0.4 内部验收版
- 冻结目标：完成 macOS 桌面 App 重新打包、全盘检查和内部验收包输出。
- 当前主线：冻结后只接受 P0/P1 修复，不再继续扩展新功能。
- 交付口径：以本地桌面 App 为准，云端技术备查仅保留为参考，不作为当前主交付。

## 本次收口内容

- 上线前数据卫生收口：源码根目录运行数据库已备份后移出。
- 代码体积收口：生产大文件已拆分，测试大文件仅保留 WARN，不阻塞交付。
- 权限收口：2.0 交付中心仅 `admin/system_admin` 可见且可访问。
- 版本口径收口：程序内版本号与更新清单已同步到 `2.0.4`。
- 打包收口：macOS `.app` 已重建，内部验收 zip 已生成并验证可启动。

## 已验证结果

- `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/desktop_release_check.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/source_tree_check.py`
- `codesign --verify --deep --strict --verbose=1 dist/物业管理收费系统.app`
- 解压后的内部验收包可启动，`/login`、静态资源、首页、房间、账单、缴费、报表可用。

## 交付物

- macOS App：`dist/物业管理收费系统.app`
- 内部验收包：`release_packages/物业管理收费系统-macOS-内部验收包-20260615-234338.zip`

## 冻结后规则

只接受以下问题：

- 无法启动
- 数据丢失
- 金额/账期错误
- 权限绕过
- 主流程阻塞
- 打包产物不可用

P2/P3 继续进入后续 backlog，不进入本次冻结范围。
