# 物业收费管理系统 v2.0.4 商业版收口发布记录

发布日期：2026-06-18

## 交付目标

- 清理客户定制品牌，统一为通用产品名“物业收费管理系统”。
- 增加本地只读授权状态、商业授权设计、首次使用引导和云端部署方案入口。
- 统一 macOS / Windows 打包产物命名。
- macOS 先生成可试用商业版交付包。
- 清空本机录入数据，避免客户试用时出现历史数据干扰。

## macOS 产物

- App：`dist/物业收费管理系统.app`
- zip：`release/macos/物业收费管理系统-v2.0-macos-20260618-142257.zip`
- SHA256：`52e76d14c9380ac55b62e2283854379c48ca243a0b7b3b2e764de964b3c36678`

## 授权文件

- 示例：`license.example.json`
- 正式客户授权放置路径：`~/Library/Application Support/PropertyFeeSystemData/license/license.json`
- 当前版本只读展示授权状态，不接真实授权服务器。

## 本机数据清空记录

- 已备份并删除旧数据目录：`~/Library/Application Support/PropertyFeeSystemData`
- 备份位置：`~/Desktop/PropertyFeeSystemDataBackups/PropertyFeeSystemData_before_commercial_release_clear_20260618-142810.zip`
- 清空后用打包 App 重新启动，确认业务表为空：`owners=0`、`rooms=0`、`bills=0`、`payments=0`。
- 默认用户保留：`admin`。

## 验证证据

```text
build_macos_app.command: success
codesign --verify --deep --strict: success
packaged serve-only login: success
/ license_status first_run_guide: success
py_compile: success
pytest -q: 492 passed, 4 skipped
scripts/desktop_release_check.py: success
scripts/source_tree_check.py: success
```

## 已知边界

- Windows exe 命名和打包脚本已统一，但本轮未在 Windows 实机重打包。
- 当前授权为本地只读展示，不包含真实云端授权服务器。
- 当前不包含 SaaS 多租户正式上线和真实支付回调。
