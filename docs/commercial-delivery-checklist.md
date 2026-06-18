# 物业收费管理系统商业版交付清单

## 1. 交付产物

- macOS App：`dist/物业收费管理系统.app`
- Windows 文件夹：`dist\PropertyBillingSystem\PropertyBillingSystem.exe`
- Windows zip：`release\windows\物业收费管理系统-v2.0-windows.zip`
- 文档：`使用说明.md`、`用户快速开始.md`、`客户试用说明.md`、`Windows客户试用说明.md`、`正式交付清单.md`
- 示例授权：`license.example.json`

## 2. 授权文件放置

正式客户授权文件命名为：

```text
license.json
```

放置位置：

- macOS：`~/Library/Application Support/PropertyFeeSystemData/license/license.json`
- Windows：`%APPDATA%\PropertyFeeSystemData\license\license.json`

注意：

- `license.example.json` 只用于说明格式，不代表正式授权。
- 不要把真实 `license.json`、密钥、客户授权码提交到仓库。
- 系统当前只读展示授权状态，不联网校验，不影响本机已有业务数据。

## 3. 首次交付核对

- 修改默认管理员密码。
- 创建岗位账号：系统管理员、财务、收费员、客服业务编辑、管理层只读。
- 进入「首次使用引导」完成 8 步核对。
- 进入「授权状态」核对客户名、版本、到期日期和授权文件路径。
- 进入「收费项目」核对单价和计费方式。
- 先导入小样本数据并跑通出账、收费、收据、报表。
- 创建一次人工备份。

## 4. 打包前验证

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server/*.py server.py desktop_app.py desktop_runtime.py scripts/*.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q
python3 scripts/desktop_release_check.py
python3 scripts/source_tree_check.py
```

## 5. 当前不包含

- 不包含真实云端授权服务器。
- 不包含在线支付回调。
- 不包含多租户 SaaS 正式上线。
- 不包含真实客户业务数据库。
