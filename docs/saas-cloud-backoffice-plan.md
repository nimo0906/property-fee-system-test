# SaaS 云端后台实施记录

## 当前阶段

第一批切片只建立云端后台并行骨架，不改桌面 SQLite 主流程。

已包含：

- 多租户 PostgreSQL schema 合同。
- SQLite 到 SaaS PostgreSQL 的迁移校验摘要。
- 内存版 SaaS 领域服务，用于锁定租户隔离、角色权限、出账、收款、报表和导入确认行为。
- 通用 Linux/VPS 部署文件清单：Docker Compose、Nginx、systemd、备份和恢复脚本。

## 当前不包含

- 真实 PostgreSQL 运行时 ORM。
- 真实 FastAPI 页面和登录 session。
- 业主端 H5、在线支付、电子票据。
- 授权云服务后台。

## 后续阶段顺序

1. 接入 SQLAlchemy/Alembic，并把当前 schema 变成可迁移数据库版本。
2. 做 FastAPI 登录、session、租户上下文和角色权限中间件。
3. 逐步替换内存领域服务为 PostgreSQL repository。
4. 补后台页面/API：收费对象、收费项目、出账、收款、报表、导入、审计。
5. 用 Docker Compose 在 Linux/VPS 完成一次空库验收和迁移演练。
