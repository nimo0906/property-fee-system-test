# SaaS 授权绑定运维交付清单

本文用于正式商业版实施交付，覆盖 SaaS 租户与授权云服务客户编号的授权绑定、备份、恢复、迁移和审计检查。授权绑定属于系统侧配置，不属于客户上传业务数据。

## 1. 授权绑定

- 平台管理员进入 `/backoffice/license-ops`。
- 在“绑定授权客户”区域填写客户公司和授权客户编号。
- 绑定成功后，SaaS 后台授权状态、席位限制、授权运维页均以显式绑定的授权客户编号为准。
- 不得依赖“租户名称等于授权客户编号”的隐式匹配。
- 绑定操作必须写入 `license.tenant_bind` 审计。

## 2. 绑定文件位置

授权绑定文件固定在系统侧路径：

```text
system/license_bindings/tenant_license_bindings.json
```

要求：

- 不得写入客户上传数据目录。
- 不得写入 SaaS 业务表。
- 不得与收费对象、账单、收款、导入文件混放。
- 不得包含生产密钥、数据库密码或客户上传文件内容。

## 3. 备份

上线、迁移、重部署前必须备份授权绑定文件。检查命令：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_license_binding_backup_check.py
```

该检查覆盖导出、manifest、sha256 校验和系统侧路径约束。

## 4. 恢复

恢复授权绑定时必须先校验 manifest 和 sha256，再恢复 `system/license_bindings/tenant_license_bindings.json`。恢复后必须重新打开 `/backoffice/license-ops` 查看每个租户的绑定状态、授权状态、席位使用和超限风险。

## 5. 迁移

服务器迁移或容器重建时，除数据库和系统文件外，必须确认授权绑定文件已经迁移。迁移后执行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_license_tenant_binding_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_license_binding_page_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_license_binding_persistence_check.py
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_license_binding_backup_check.py
```

## 6. 审计检查

绑定和变更后检查审计日志：

- 必须出现 `license.tenant_bind`。
- 审计 detail 只允许记录授权客户编号等必要摘要。
- 审计中不得出现生产密钥、客户上传文件路径、收费明细或业务库连接信息。

## 7. 交付验收口径

交付人员必须确认：

- 新客户已绑定授权客户编号。
- 绑定后授权状态显示正确。
- 授权席位与启用员工数一致。
- 备份包包含授权绑定文件。
- 恢复演练后绑定仍可读取。
- `scripts/saas_release_gate.py` 通过。
