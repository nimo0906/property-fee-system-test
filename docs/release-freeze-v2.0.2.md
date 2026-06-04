# v2.0.2 上线前冻结记录

## 冻结结论

- 冻结版本：v2.0.2
- 冻结日期：2026-06-04
- 冻结分支：feat/commercial-merchant-billing
- 冻结 commit：7a4045a
- 交付状态：macOS 已重打包；Windows 已在用户电脑完成打开测试。

## 本轮用户验收结论

- macOS 交付包已生成并可解压测试。
- Windows 打包链路已跑通，用户反馈已能打开。
- 用户已完成双端测试，反馈暂未发现问题。

## 冻结前验证

- Python 编译：通过。
- 全量测试：355 passed。
- 桌面发布资源检查：通过。
- macOS zip 使用 `ditto` 打包，避免 `.app` 符号链接损坏。
- Windows 打包源码包已校验，不包含本机数据库、备份、`.env`、构建缓存。

## 冻结后的变更规则

上线前只接受以下变更：

1. P0：无法启动、数据丢失、金额错误、账期错误、越权、误删、桌面包不可用。
2. P1：主流程阻塞、筛选/分页明显错误、状态错误、导出/打印明显错误、权限菜单与实际权限不一致。

以下内容进入上线后优化，不再影响本次冻结：

- 发票真实税务平台对接。
- 更深度的经营报表。
- 更细的权限审计可视化。
- 自动更新发布流程增强。
- Windows 正式签名和安装包形态。

## 交付文件

macOS：

```text
release/macos/物业管理收费系统-v2.0-macos.zip
```

Windows：

```text
release/windows/物业管理收费系统-v2.0-windows.zip
```

如当前机器是 macOS，Windows 正式 zip 需在 Windows 电脑上运行：

```text
package_windows_release.bat
```
