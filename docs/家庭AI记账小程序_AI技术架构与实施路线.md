# 家庭 AI 记账微信小程序——AI、技术架构与实施路线

## 1. AI 自动分类架构

不要让大模型承担所有分类，推荐分层处理：

```text
Transaction
    ↓
Merchant Normalize
    ↓
本地规则
    ↓
高置信度？
  /       \\
是         否
↓           ↓
自动分类   AI 分类
             ↓
         Confidence
             ↓
       用户确认/自动接受
```

例如“滴滴出行”可由本地规则直接归类为“交通/打车”；复杂或陌生的商户再交给 AI。

LLM 返回结构化结果：

```json
{
  "category": "food",
  "subcategory": "takeout",
  "confidence": 0.94,
  "reason": "商户名称包含外卖服务"
}
```

后端必须校验分类是否存在、子分类是否匹配、置信度是否在 0～1 以及 JSON 是否符合 Schema。低置信度结果必须让用户确认。

## 2. 个性化分类与模型演进

记录用户的分类修改行为，建立家庭级或用户级映射：

```text
盒马 → 食品
山姆 → 食品
京东 → 家居
淘宝 → 日用品
滴滴 → 交通
```

最终分类可综合默认规则、用户历史、交易描述、金额和时间。积累确认数据后，可训练轻量分类模型：

```text
Merchant + Description + Amount + Time
                    ↓
                Classifier
                    ↓
                 Category
```

长期目标是约 90% 由本地规则/本地模型处理，9% 由分类模型处理，1% 疑难交易调用 LLM，以降低成本和延迟。

## 3. 后端技术架构

推荐架构：

```text
微信小程序 → REST API → Python FastAPI
                              │
             ┌────────────────┼────────────────┐
             ↓                ↓                ↓
         PostgreSQL          Redis          AI Service
                                               │
                                         OCR / LLM
```

- PostgreSQL：用户、家庭、账户、交易、分类、预算和导入任务。
- Redis：缓存、幂等控制、任务队列和短期状态。
- Celery/RQ：账单解析、OCR、批量分类等异步任务。
- OSS/COS：上传账单和截图的对象存储，使用临时授权 URL。
- AI Service：封装 OCR、多模态模型和 LLM，统一超时、重试、限流和审计。

### 后端目录建议

```text
server/
├── app/
│   ├── api/       # auth、family、account、transaction、import、statistics、ai
│   ├── models/    # ORM 数据模型
│   ├── schemas/   # API 输入输出 Schema
│   ├── services/  # transaction、import、dedup、transfer、category、ai
│   ├── parsers/   # alipay、wechat、bank_csv、bank_pdf
│   └── core/      # 配置、鉴权、日志、异常
├── tests/
└── main.py
```

### 小程序目录建议

```text
miniprogram/
├── pages/       # home、transactions、statistics、profile、add-transaction、import、import-review
├── components/  # transaction-item、category-picker、account-picker、budget-card
├── services/    # api、auth、transaction
├── utils/
└── app.js
```

## 4. 第一版 API

```text
POST /auth/wechat-login

GET  /families
POST /families
POST /families/{id}/members

GET  /accounts
POST /accounts
PUT  /accounts/{id}

GET  /transactions
POST /transactions
PUT  /transactions/{id}
DELETE /transactions/{id}

GET  /categories

POST /imports
GET  /imports/{id}
GET  /imports/{id}/transactions
POST /imports/{id}/confirm

POST /ai/classify
POST /ai/parse-text

GET  /statistics/monthly
GET  /statistics/category

GET  /budgets
POST /budgets
PUT  /budgets/{id}
```

## 5. 家庭权限与隐私安全

### 权限模型

不要默认所有成员都能看到所有账户明细。

- 家庭管理员：查看家庭总账、成员账单，增改删交易，管理成员和账户。
- 普通成员：查看家庭统计和自己的账单，添加或修改自己的交易。
- `owner`、`admin`、`member` 权限由后端按家庭成员关系校验，不能只依赖前端隐藏按钮。

### 数据最小化

系统会处理收入、支出、银行卡、支付宝、微信、家庭成员、消费习惯、资产和负债等敏感信息。不得保存银行卡密码、支付宝密码或微信支付密码；银行卡非必要不保存完整卡号，可仅保存“招商银行 ****1234”。

### 安全措施

- 全链路 HTTPS、API 鉴权和服务端家庭数据权限校验
- 敏感字段加密、数据库访问控制和去标识化
- 文件使用临时授权、病毒/恶意文件检查和自动过期删除
- 操作日志、定期备份、数据导出与彻底删除机制
- AI 请求脱敏、供应商访问控制、超时重试和调用审计

## 6. MVP 开发阶段

### Sprint 1：基础账户

微信登录、家庭、成员、账户。

### Sprint 2：手动记账

收入、支出、转账、分类和账单列表。

### Sprint 3：统计

月度收支、分类统计、成员统计和预算。

### Sprint 4：账单导入

支付宝、微信、银行卡，优先 CSV/Excel。

### Sprint 5：智能处理

去重、转账识别、退款识别和商户标准化。

### Sprint 6：AI 能力

自然语言记账、OCR 截图记账和 AI 分类。

## 7. 核心指标

- 账单导入率：注册用户中实际导入账单的比例。
- 自动分类准确率：自动分类后无需修改的交易比例。
- 月度留存：用户是否持续回来使用。
- 自动化节省时间：从每天手工记账到每月导入所节省的时间。

## 8. 推荐开发优先级与下一步

推荐顺序：

```text
微信登录 → 家庭 → 成员 → 账户
→ 手动记账 → 收入/支出/转账 → 分类 → 账单列表
→ 月度统计 → 分类统计 → 预算
→ 支付宝/微信/银行卡账单导入
→ 标准化 → 去重 → 转账识别 → 退款识别 → 商户标准化
→ AI 分类 → 自然语言记账 → OCR 截图记账
→ 家庭资产负债 → AI 财务分析 → 个性化财务助手
```

实际开发前优先完成：

1. 统一 `Transaction Schema`。
2. 支付宝、微信、银行卡 CSV/Excel 字段映射。
3. 银行 PDF 解析和 OCR 识别方案。
4. 交易去重、转账匹配、退款关联和商户标准化算法。
5. AI 分类 Prompt、输出 Schema 和评测集。
6. PostgreSQL 建表 SQL、FastAPI Schema 和小程序页面原型。

其中最关键的是统一交易模型、多来源账单解析器和去重/转账识别，它们决定后续数据质量并最容易形成技术债务。

## 9. 第二阶段技术方向

- 家庭资产负债：计算总资产、总负债和家庭净资产。
- 智能预算：根据收入、固定支出和历史消费自动建议各分类预算。
- AI 财务分析：比较近三个月趋势，预测预算超支并解释变化原因。
