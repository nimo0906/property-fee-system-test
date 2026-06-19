# SaaS 样例客户验收演练

## 1. 用途

本文档用于正式商业云端后台的样例客户验收演练。演练只使用脱敏样例数据，不使用客户真实资料、手机号、合同、收款流水或上传文件。

样例物业公司用于证明 SaaS 第一阶段员工后台闭环可以从空租户跑通，并验证不同公司之间的数据不会混在一起。

## 2. 样例数据边界

- 租户：样例物业公司。
- 项目：样例云端项目。
- 收费对象：住宅房号和商业铺位号混合样例。
- 收费项目：物业费、商业物业费。
- 账期：2026-07。
- 客户上传数据与系统自身数据隔离：导入预览和确认结果属于租户业务域；部署脚本、日志、备份元数据和运维检查属于系统域。
- 租户隔离：样例物业公司B不能读取样例物业公司的收费对象、账单、收款和报表。

## 3. 演练流程

```text
创建项目
→ 导入收费对象
→ 配置收费项目
→ 账单生成
→ 账单审核
→ 收款登记
→ 对账报表
→ 导出账单和收款流水
→ 备份恢复演练
→ 租户隔离复核
```

## 4. 执行命令

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_demo_tenant_drill.py
```

成功时应看到：

```text
PASS demo tenant login
PASS demo charge targets
PASS demo fee types
PASS demo bill generation
PASS demo bill approval
PASS demo payments
PASS demo report totals
PASS demo exports
PASS demo backup restore drill
PASS demo tenant isolation
saas_demo_tenant_drill: PASS
```

## 5. 验收重点

- 收费对象必须落在当前租户和当前项目内。
- 收费项目只影响当前租户和当前项目。
- 账单生成金额必须按面积乘单价计算。
- 账单审核前不能作为正式收款闭环。
- 收款登记必须生成收据号。
- 对账报表必须能核对应收、实收和欠费。
- 导出内容只包含当前租户和当前账期。
- 备份恢复演练只记录演练证据，不直接覆盖生产库。
- 第二个样例租户不能读取第一个样例租户的数据。
