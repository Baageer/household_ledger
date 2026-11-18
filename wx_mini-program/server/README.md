# M1 后端原型

`server/ledger/family.py` 是第 2 周“微信登录与家庭基础”的领域服务，负责：

- 微信 `code` 到内部 `user_id` 的幂等映射（通过 `openid_resolver` 接入真实 `code2Session`）。
- 家庭创建、成员邀请令牌和 `owner/admin/member` 角色权限。
- 成员列表、角色变更、成员禁用和邀请状态流转。
- 个人账户、家庭公共账户及普通成员的账户可见范围。
- 账户编辑、停用、初始余额定点数处理，以及停用账户交易前校验。

`server/ledger/transactions.py` 提供第 4 周 M2 手动记账能力：收入、支出和转账新增，交易编辑/软删除，月份筛选、日期分组、分页列表，以及家庭自定义分类和引用保护。金额统一使用两位小数 `Decimal`；转账不进入收入/支出汇总。

同一家庭下的来源交易号和交易指纹具备幂等保护；交易记录保留来源、原始引用、创建人、标准商户和更新时间等审计字段，并支持转账候选匹配和退款关联。

`server/ledger/statistics.py` 提供 M3 统计、预算和首页聚合：月度收支结余、日/周/月趋势、分类排行、成员/家庭账户支出、分类预算使用率和超预算状态，以及首页所需的组合数据。

`server/ledger/imports.py` 提供 M4 第 7 周导入中间层：支付宝 GB18030 CSV、微信多行表头 Excel 解析，ImportTask/ImportTransaction 状态、导入预览、错误行隔离、重复标记和确认入账幂等。文件当前从本地路径读取，OSS/COS 上传和银行适配器在后续阶段接入。

```python
from ledger.transactions import TransactionService

ledger = TransactionService(service)
transaction = ledger.create_transaction(
    user.id, family.id, "expense", "56.00", account.id,
    merchant="美团外卖", description="晚餐",
)
ledger.list_transactions(user.id, family.id, month="2026-08")
```

当前领域服务仍支持进程内存模式，用于本地测试；生产环境可通过 `DATABASE_URL` 启用 PostgreSQL 数据层。

## PostgreSQL

安装依赖后，在 `server` 目录配置连接串并创建数据库 schema：

```powershell
$env:DATABASE_URL = "postgresql+psycopg://ledger:secret@localhost:5432/ledger"
D:\Anaconda3\envs\llm\python.exe -m pip install -r requirements.txt
D:\Anaconda3\envs\llm\python.exe create_database.py
```

生产环境建议先使用 Alembic 创建 schema，再启动 API：

```powershell
D:\Anaconda3\envs\llm\python.exe -m alembic upgrade head
```

本地联调也可以设置 `AUTO_CREATE_DB=true`，在启动阶段自动创建缺失表：

```powershell
$env:DATABASE_URL = "postgresql+psycopg://ledger:secret@localhost:5432/ledger"
$env:AUTO_CREATE_DB = "true"
$env:PYTHONPATH = "."
D:\Anaconda3\envs\llm\python.exe -m uvicorn main:app
```

`GET /health` 会返回 `database` 状态：`not_configured`、`ok` 或 `error`；`GET /health/database` 提供独立数据库探活。表模型位于 `ledger/database.py`，覆盖用户、家庭、成员、账户、分类、交易、预算、导入任务、导入明细、会话和审计日志。`LedgerRepository` 在服务启动时恢复领域状态，并在请求完成后将领域对象同步到数据库；金额使用 `NUMERIC(18,2)`，导入原始行使用 PostgreSQL `JSONB`，交易 hash 和导入任务具备幂等约束。

## FastAPI 联调

最小 HTTP 应用位于 `main.py`，包含 `/health`、微信登录、家庭、账户、交易和统计首页接口。启动方式：

```powershell
Set-Location server
$env:PYTHONPATH = "."
$env:DATABASE_URL = "sqlite:///./ledger.db"
$env:AUTO_CREATE_DB = "true"
D:\ProgramData\miniconda3\envs\llm\python.exe -m uvicorn main:app --reload
```

`DATABASE_URL` 未设置时使用进程内存储，重启后数据会清空。设置 `sqlite:///./ledger.db` 后，用户、家庭、账户、交易、预算、导入数据和登录会话会写入 `server/ledger.db`，重启服务后自动恢复；删除该文件即可重置本地数据。

前端页面位于 `../miniprogram`，使用微信开发者工具打开 `wx_mini-program` 目录即可预览。部署联调前，将 `miniprogram/app.js` 中的 `apiBaseUrl` 替换为实际 HTTPS API 地址。

如果登录页点击后无法跳转，请先启动本地 API，并在开发者工具中勾选“**不校验合法域名**”。本机开发环境使用 `http://127.0.0.1:8000`；真机调试时需改为同一局域网内可访问的 HTTPS 地址。

```powershell
Set-Location server
$env:PYTHONPATH = "."
D:\Anaconda3\envs\llm\python.exe -m pytest -q
```
