# 家庭 AI 记账微信小程序——数据模型与账务处理

## 1. 家庭与账户模型

家庭示例：

```text
家庭
├── 爸爸
│   ├── 微信
│   └── 招商银行
├── 妈妈
│   ├── 支付宝
│   └── 工商银行
└── 家庭公共账户
    ├── 现金
    └── 其他
```

数据库关系可抽象为：

```text
User ──< FamilyMember >── Family
                              ├──< Account
                              ├──< Transaction
                              ├──< Budget
                              └──< ImportTask ──< ImportTransaction
```

## 2. 核心实体

### User

```text
users
id
openid
unionid
nickname
avatar
created_at
updated_at
```

微信 `openid` 只作为外部身份标识，业务内部统一使用 `user_id`，不要直接将 `openid` 作为业务主键。

### Family

```text
families
id
name
owner_id
created_at
updated_at
```

### FamilyMember

```text
family_members
id
family_id
user_id
role
nickname
status
created_at
```

角色包括 `owner`、`admin`、`member`。

### Account

账户类型包括 `cash`、`bank`、`alipay`、`wechat`、`credit_card`、`other`。

```text
accounts
id
family_id
owner_id
name
type
currency
initial_balance
status
created_at
updated_at
```

账户属于家庭，可绑定具体成员，也可标记为家庭公共账户。

### Transaction

```text
transactions
id
family_id
account_id
member_id
type
amount
category_id
merchant
description
transaction_time
source
source_transaction_id
transaction_hash
status
created_at
updated_at
```

交易类型：`income`、`expense`、`transfer`、`refund`。数据来源：`manual`、`alipay`、`wechat`、`bank`、`ocr`、`ai`。

建议后续增加 `related_transaction_id`，用于关联退款和原交易，或关联转账的两个账户流水。

### ImportTask

导入账单不能直接写入 `transactions`，先创建任务：

```text
import_tasks
id
family_id
account_id
source
file_name
file_url
status
total_count
success_count
duplicate_count
error_count
created_at
finished_at
```

任务状态：`uploaded`、`parsing`、`parsed`、`reviewing`、`completed`、`failed`。

### ImportTransaction

```text
import_transactions
id
import_task_id
raw_data
transaction_time
merchant
amount
direction
category
description
transaction_hash
duplicate
confidence
status
```

导入处理流程：

```text
CSV / Excel / PDF / OCR
          ↓
      ImportTask
          ↓
  ImportTransaction
          ↓
      用户确认
          ↓
      Transaction
```

这样可以隔离原始数据，避免解析错误直接污染正式账本。

## 3. 统一交易处理流程

所有手动输入、文件导入和 AI/OCR 结果都应转换为统一的 Transaction Schema。标准化步骤包括：

1. 解析来源字段并统一时间、金额、方向和商户字段。
2. 将账户和家庭成员映射到内部 ID。
3. 商户名称标准化。
4. 去重、转账和退款识别。
5. 分类并计算置信度。
6. 将需要人工确认的数据留在导入中间层。
7. 用户确认后以事务方式写入正式交易。

## 4. 交易去重

### 第一层：平台交易 ID

如果账单存在唯一交易号，保存到 `source_transaction_id`，按来源和账户建立唯一约束。

### 第二层：交易指纹

没有平台 ID 时，计算：

```text
transaction_hash = SHA256(
    source + account_id + transaction_time + amount + merchant
)
```

### 第三层：模糊匹配

使用时间 ±5 分钟、金额相同、商户名称相似等条件识别候选重复。例如“美团”和“美团外卖”同金额、相近时间的交易应标记为“可能重复”。模糊匹配不得直接删除，应进入人工确认。

## 5. 转账识别

必须将账户间转账和家庭收入/支出分开。例如：

```text
招商银行 -5000
支付宝   +5000
```

应识别为：

```text
from = 招商银行
to = 支付宝
amount = 5000
type = transfer
```

统计时家庭收入和支出均为 0，只记录账户余额发生转移。匹配可结合金额、时间窗口、账户方向和成员关系，并保留待确认状态处理不确定结果。

## 6. 退款识别

退款不能简单作为一笔独立收入。例如消费 -128 后出现美团退款 +128，应通过 `related_transaction_id` 关联原交易，使原支出被抵消，而不是同时计入收入和支出。

## 7. 商户标准化与分类数据

将“美团”“美团外卖”“美团支付”等原始名称归一为“美团”，再进行规则或 AI 分类。应保留原始商户字段，标准化名称单独存储，便于审计和重新处理。

分类建议采用收入/支出两级结构，第一版只保留有限分类（住房、餐饮、交通、购物、娱乐、教育、医疗、保险、通讯、其他等），避免分类过度细化。

## 8. 账务一致性要求

- 金额使用定点数或最小货币单位存储，避免浮点误差。
- 交易写入、退款关联和转账配对应支持事务处理。
- 正式交易保留来源、原始数据引用和处理状态，保证可追溯。
- 删除、修改和批量确认应记录操作日志。
- 重复导入必须具备幂等性，同一来源交易重复提交不能产生重复账目。
- 统计查询需明确是否排除 `transfer`、被退款抵消和待确认交易。
