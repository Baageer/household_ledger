# 家庭 AI 记账微信小程序——MVP 产品与技术设计

## 1. 项目定位

### 产品名称（暂定）

**家账——家庭 AI 记账助手**

### 核心定位

不是简单的“手动记账工具”，而是：

> **导入支付宝、微信和银行卡账单，AI 自动帮全家整理收支。**

核心价值：

- 家庭成员共同管理家庭收支
- 支持多个资金账户
- 支持支付宝、微信、银行卡账单导入
- 自动去重
- 自动识别账户间转账
- AI 自动分类
- 支持自然语言记账
- 支持 OCR 截图记账
- 提供家庭预算和收支分析

---

# 2. 产品总体目标

用户不需要每天手动记录大量交易，只需要：

```text
支付宝账单
微信账单
银行卡账单
截图
   ↓
导入
   ↓
统一交易模型
   ↓
去重 / 转账识别
   ↓
AI 自动分类
   ↓
用户确认
   ↓
家庭账本
   ↓
统计 / 预算 / 财务分析
```

---

# 3. MVP 产品范围

## 3.1 第一版必须具备

| 模块 | MVP |
|---|---|
| 微信登录 | ✅ |
| 创建家庭 | ✅ |
| 邀请家庭成员 | ✅ |
| 手动记账 | ✅ |
| 多账户 | ✅ |
| 收入/支出 | ✅ |
| 转账 | ✅ |
| 分类 | ✅ |
| 月度统计 | ✅ |
| 预算 | ✅ |
| 支付宝账单导入 | ✅ |
| 微信账单导入 | ✅ |
| 银行账单导入 | ✅ |
| 自动分类 | ✅ |
| AI 自然语言记账 | ⭐ |
| OCR 截图记账 | ⭐ |
| 银行实时同步 | ❌ |
| 支付宝实时同步 | ❌ |
| 微信实时同步 | ❌ |
| 股票/基金 | 第二阶段 |
| 家庭资产负债表 | 第二阶段 |

---

# 4. 数据获取策略

## 4.1 不建议第一版做实时金融账户直连

不要将系统设计成：

```text
小程序
 ↓
支付宝账户 API
 ↓
完整账单
```

或者：

```text
小程序
 ↓
银行卡 API
 ↓
银行卡流水
```

金融数据涉及敏感个人信息，第三方直接读取个人金融账户数据会涉及较高的权限、安全和合规要求。

因此 MVP 优先采用：

```text
手动记账
账单文件导入
账单截图 OCR
自然语言记账
```

未来再根据具体平台开放能力和合规要求评估 API/账户连接。

---

# 5. 账单数据来源

## 5.1 手动记账

用户直接输入：

```text
收入：+10000
支出：-35
分类：餐饮
账户：微信
```

---

## 5.2 支付宝账单导入

推荐流程：

```text
支付宝
 ↓
用户导出账单
 ↓
CSV / Excel
 ↓
上传
 ↓
解析
 ↓
标准化
 ↓
去重
 ↓
AI 分类
 ↓
确认
 ↓
正式入账
```

---

## 5.3 微信账单导入

流程与支付宝类似：

```text
微信账单
 ↓
文件
 ↓
上传
 ↓
解析
 ↓
标准化
 ↓
去重
 ↓
分类
 ↓
确认
```

---

## 5.4 银行账单导入

支持：

- CSV
- Excel
- PDF
- OCR 截图

建议优先支持 CSV / Excel，PDF/OCR 作为增强能力。

---

## 5.5 OCR 截图记账

用户：

```text
支付宝 / 微信 / 银行 APP
 ↓
截图
 ↓
上传
 ↓
OCR / 多模态模型
 ↓
识别：
  时间
  商户
  金额
  收支方向
 ↓
AI 分类
 ↓
用户确认
 ↓
入账
```

这是一个非常适合 AI 的产品能力。

---

# 6. 产品核心页面

底部导航建议只有 4 个：

```text
┌────────┬────────┬────────┬────────┐
│  首页  │ 账单   │ 统计   │ 我的   │
└────────┴────────┴────────┴────────┘
```

---

# 7. 首页

首页解决：

> **这个月家庭财务怎么样？**

示例：

```text
本月家庭收支

收入
¥28,600

支出
¥12,860

结余
¥15,740

----------------

支出排行

住房       ¥4,500
餐饮       ¥2,360
购物       ¥1,820
交通         ¥620
娱乐         ¥480

----------------

预算使用

餐饮   ███████░░░ 72%
购物   █████████░ 91%
```

---

# 8. 账单页面

显示：

```text
2026年8月

收入 ¥28,600
支出 ¥12,860
```

交易：

```text
今天

19:32   美团外卖       -¥56
18:20   滴滴           -¥32
12:15   星巴克         -¥36

昨天

09:00   工资          +¥28,000
```

右下角提供：

```text
＋ 记一笔
```

---

# 9. 手动记账

用户点击“记一笔”：

```text
支出 / 收入 / 转账

¥128

分类：餐饮
账户：微信
成员：爸爸

备注：晚饭

[保存]
```

---

# 10. AI 自然语言记账

用户输入：

> 今天晚上和老婆吃火锅花了328，用微信支付

AI 解析：

```json
{
  "type": "expense",
  "amount": 328,
  "category": "餐饮",
  "subcategory": "聚餐",
  "account": "微信",
  "member": "我",
  "date": "2026-08-27"
}
```

然后要求用户确认：

```text
确认记账？

餐饮 / 聚餐
微信
¥328

[确认]
```

原则：

> AI 只负责解析和建议，正式入账必须经过用户确认。

---

# 11. 统计页面

MVP 只做四类核心统计。

## 11.1 收支趋势

按日 / 周 / 月查看收入和支出趋势。

## 11.2 支出分类

```text
住房       35%
餐饮       18%
购物       14%
交通        8%
娱乐        5%
其他       20%
```

## 11.3 家庭成员

```text
爸爸    ¥4,820
妈妈    ¥5,630
孩子      ¥620
家庭    ¥1,790
```

## 11.4 预算

```text
餐饮
预算 ¥2,500
已用 ¥2,360
剩余 ¥140
```

---

# 12. 我的页面

建议包含：

```text
我的

家庭
  我的家庭

账户
  支付宝
  微信
  招商银行
  现金

账单导入
  支付宝
  微信
  银行卡

分类管理

预算管理

家庭成员

数据安全

导出账本
```

---

# 13. 家庭账户模型

家庭示例：

```text
家庭
├── 爸爸
│   ├── 微信
│   └── 招商银行
│
├── 妈妈
│   ├── 支付宝
│   └── 工商银行
│
└── 家庭公共账户
    ├── 现金
    └── 其他
```

---

# 14. 数据库 ER 模型

核心实体：

```text
User
 │
 ├──────────────┐
 ↓              ↓
FamilyMember   Account
 │              │
 ↓              ↓
Family ────── Transaction
 │              │
 │              ↓
 │          Category
 │
 └────────── Budget
```

进一步：

```text
User
 └──< FamilyMember >── Family
                            │
                            ├──< Account
                            │
                            ├──< Transaction
                            │
                            ├──< Budget
                            │
                            └──< ImportTask
```

---

# 15. User 表

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

原则：

> 不要把微信 OpenID 直接作为业务主键。

内部统一使用：

```text
user_id
```

---

# 16. Family 表

```text
families

id
name
owner_id
created_at
updated_at
```

---

# 17. FamilyMember 表

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

角色：

```text
owner
admin
member
```

---

# 18. Account 表

账户类型：

```text
cash
bank
alipay
wechat
credit_card
other
```

表结构：

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

示例：

```text
支付宝
owner = 妈妈

微信
owner = 爸爸

招商银行
owner = 爸爸

现金
owner = 家庭
```

---

# 19. Transaction 表

核心交易模型：

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

type：

```text
income
expense
transfer
refund
```

---

# 20. source 数据来源

支持：

```text
manual
alipay
wechat
bank
ocr
ai
```

例如：

```text
source = alipay
```

代表：

> 数据来自支付宝账单。

```text
source = ocr
```

代表：

> 数据来自截图 OCR。

---

# 21. ImportTask 表

账单导入不能直接写入 Transaction。

增加中间任务：

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

状态：

```text
uploaded
parsing
parsed
reviewing
completed
failed
```

---

# 22. ImportTransaction 表

导入交易中间层：

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

处理流程：

```text
Excel / CSV / PDF / OCR
 ↓
ImportTask
 ↓
ImportTransaction
 ↓
用户确认
 ↓
Transaction
```

这样可以避免错误数据直接进入正式账本。

---

# 23. 交易去重

## 23.1 第一层：平台交易 ID

如果账单存在唯一交易号：

```text
source_transaction_id
```

直接使用。

---

## 23.2 第二层：交易指纹

没有唯一 ID 时：

```text
transaction_hash = SHA256(
    source
    + account_id
    + transaction_time
    + amount
    + merchant
)
```

---

## 23.3 第三层：模糊匹配

例如：

```text
时间 ± 5 分钟
金额相同
商户名称相似
```

发现：

```text
2026-08-20 19:32
美团
56

2026-08-20 19:33
美团外卖
56
```

判定：

```text
可能重复
```

不要直接删除，而是进入人工确认。

---

# 24. 转账识别

必须把“转账”与“收入/支出”分开。

例如：

```text
招商银行 -5000
支付宝 +5000
```

系统识别：

```text
from = 招商银行
to = 支付宝
amount = 5000
type = transfer
```

最终：

```text
家庭收入 = 0
家庭支出 = 0
账户之间发生 ¥5000 转移
```

否则会产生错误统计。

---

# 25. 退款识别

例如：

```text
美团
-128
```

之后：

```text
美团退款
+128
```

不能简单统计为：

```text
支出 128
收入 128
```

而应该建立退款关系：

```text
原交易
  ↓
退款
  ↓
抵消原支出
```

交易模型未来可以增加：

```text
related_transaction_id
```

用于关联原交易和退款。

---

# 26. AI 自动分类架构

不要让大模型承担所有分类。

推荐：

```text
Transaction
     ↓
Merchant Normalize
     ↓
本地规则
     ↓
是否高置信度？
   /       \
 Yes        No
 ↓           ↓
自动分类     AI分类
              ↓
          Confidence
              ↓
        用户确认 / 自动接受
```

例如：

```text
滴滴出行
```

直接：

```text
交通 / 打车
```

而：

```text
深圳市某某生活服务有限公司
```

交给 AI。

---

# 27. AI 分类输出

LLM 应返回结构化数据：

```json
{
  "category": "food",
  "subcategory": "takeout",
  "confidence": 0.94,
  "reason": "商户名称包含外卖服务"
}
```

后端必须校验：

- category 是否存在
- subcategory 是否存在
- confidence 是否在 0~1
- 数据格式是否合法

通过验证以后才能进入后续流程。

---

# 28. 分类体系

## 收入

```text
工资
奖金
投资收入
兼职
红包
退款
其他
```

## 支出

```text
住房
  房贷
  房租
  物业
  水电

餐饮
  早餐
  午餐
  晚餐
  外卖
  聚餐

交通
  公交
  地铁
  打车
  加油

购物
  日用品
  服装
  数码

娱乐
  电影
  游戏
  旅游

教育
医疗
保险
通讯
其他
```

第一版不建议设计几百个分类。

---

# 29. AI 个性化分类

记录用户修改行为：

```text
盒马 → 食品
山姆 → 食品
京东 → 家居
淘宝 → 日用品
滴滴 → 交通
```

建立：

```text
merchant → category
```

用户长期使用后，可以形成：

```text
默认分类
+
用户历史
+
交易描述
+
金额
+
时间
```

综合判断。

---

# 30. 未来自有分类模型

积累大量用户确认数据以后，可以训练轻量分类模型：

```text
Merchant
+
Description
+
Amount
+
Time
 ↓
Classifier
 ↓
Category
```

最终可以形成：

```text
90% 简单交易 → 本地规则 / 本地模型
9% 复杂交易 → 分类模型
1% 疑难交易 → LLM
```

降低 AI API 成本和延迟。

---

# 31. 账单导入页面

用户点击：

```text
导入账单
```

选择：

```text
支付宝
微信
银行卡
截图识别
```

导入后显示：

```text
正在分析账单...

交易 1,382 条
收入 26 条
支出 1,241 条
转账 115 条

重复交易 328 条

AI分类完成 1,006 条
需要确认 48 条
```

---

# 32. 导入确认页面

例如：

```text
发现 48 条需要确认

美团生活费
¥128

AI分类：
餐饮 / 外卖

[正确] [修改]
```

提供：

```text
[全部确认]
```

---

# 33. 后端技术架构

推荐：

```text
微信小程序
     │
     ↓
REST API
     │
     ↓
Python FastAPI
     │
 ┌───┼───────────┐
 ↓   ↓           ↓
PostgreSQL Redis AI Service
                 │
          ┌──────┴──────┐
          ↓             ↓
         OCR           LLM
```

文件存储：

```text
OSS / COS
```

异步任务：

```text
Redis
Celery / RQ
```

数据库：

```text
PostgreSQL
```

---

# 34. 后端项目结构

```text
server/
│
├── app/
│   ├── api/
│   │   ├── auth.py
│   │   ├── family.py
│   │   ├── account.py
│   │   ├── transaction.py
│   │   ├── import_task.py
│   │   ├── statistics.py
│   │   └── ai.py
│   │
│   ├── models/
│   │
│   ├── schemas/
│   │
│   ├── services/
│   │   ├── transaction_service.py
│   │   ├── import_service.py
│   │   ├── dedup_service.py
│   │   ├── transfer_service.py
│   │   ├── category_service.py
│   │   └── ai_service.py
│   │
│   ├── parsers/
│   │   ├── alipay.py
│   │   ├── wechat.py
│   │   ├── bank_csv.py
│   │   └── bank_pdf.py
│   │
│   └── core/
│
├── tests/
│
└── main.py
```

---

# 35. 小程序代码结构

```text
miniprogram/
│
├── pages/
│   ├── home/
│   ├── transactions/
│   ├── statistics/
│   ├── profile/
│   ├── add-transaction/
│   ├── import/
│   └── import-review/
│
├── components/
│   ├── transaction-item/
│   ├── category-picker/
│   ├── account-picker/
│   └── budget-card/
│
├── services/
│   ├── api.js
│   ├── auth.js
│   └── transaction.js
│
├── utils/
│
└── app.js
```

---

# 36. API 第一版

```text
POST /auth/wechat-login

GET  /families
POST /families
POST /families/{id}/members
GET  /families/{id}/members
PUT  /families/{id}/members/{member_id}
DELETE /families/{id}/members/{member_id}

GET  /accounts
POST /accounts
PUT  /accounts/{id}
DELETE /accounts/{id}

GET  /transactions
GET  /transactions/{id}
POST /transactions
PUT  /transactions/{id}
DELETE /transactions/{id}

GET  /categories
POST /categories
DELETE /categories/{id}

POST /imports
GET  /imports/{id}
GET  /imports/{id}/transactions
POST /imports/{id}/confirm

POST /ai/classify
POST /ai/parse-text

GET  /statistics/monthly
GET  /statistics/category
GET  /statistics/members
GET  /statistics/trend
GET  /statistics/home

GET  /budgets
POST /budgets
PUT  /budgets/{id}
```

---

# 37. 家庭权限

不要默认所有家庭成员看到所有账户明细。

建议：

```text
家庭管理员
├── 查看家庭总账
├── 查看成员账单
├── 添加交易
├── 修改交易
├── 删除交易
└── 管理成员

普通成员
├── 查看家庭统计
├── 查看自己的账单
├── 添加自己的交易
└── 修改自己的交易
```

具体权限可以在后续根据产品需求进一步细化。

---

# 38. 隐私与安全

系统处理的数据包括：

```text
收入
支出
银行卡
支付宝
微信
家庭成员
消费习惯
资产
负债
```

这些数据需要按照敏感个人信息和金融数据相关要求进行保护。

## 不应该保存

```text
银行卡密码
支付宝密码
微信支付密码
```

银行卡如果不是业务必需，也不保存完整卡号。

可以保存：

```text
招商银行
****1234
```

## 数据安全措施

建议：

- HTTPS
- 数据库访问控制
- 敏感字段加密
- 数据最小化
- 去标识化
- 文件访问权限控制
- 临时文件自动删除
- API 鉴权
- 家庭数据权限校验
- 操作日志
- 导入文件病毒/恶意文件检查
- 定期备份
- 数据删除机制

---

# 39. MVP 开发阶段

## Sprint 1：基础账户

```text
微信登录
家庭
成员
账户
```

## Sprint 2：手动记账

```text
收入
支出
转账
分类
账单列表
```

## Sprint 3：统计

```text
月度收支
分类统计
成员统计
预算
```

完成后已经可以形成一个最小可用产品。

## Sprint 4：账单导入

```text
支付宝
微信
银行卡
```

优先支持 CSV / Excel。

## Sprint 5：智能处理

```text
去重
转账识别
退款识别
商户标准化
自动分类
```

## Sprint 6：AI

```text
自然语言记账
OCR 截图记账
AI 分类
```

---

# 40. MVP 核心指标

不要只关注注册用户数量。

## 指标 1：账单导入率

注册用户中，有多少人真正导入账单。

这是核心指标之一。

## 指标 2：自动分类准确率

例如：

```text
1000 条交易

自动正确分类：850
需要修改：150

准确率 = 85%
```

## 指标 3：月度留存

用户是否持续回来使用。

## 指标 4：自动化节省时间

例如：

```text
传统记账：
每天 5 分钟

本产品：
每月导入一次
耗时 2 分钟
```

这才是产品真正的价值。

---

# 41. 第一版暂时不要做

```text
❌ 股票实时行情
❌ 基金分析
❌ 理财推荐
❌ 投资建议
❌ 贷款
❌ 信用评分
❌ 银行账户直连
❌ 支付宝账户直连
❌ 微信支付账户直连
❌ 复杂社交功能
```

避免 MVP 过度膨胀。

---

# 42. 第二阶段功能

当 MVP 验证完成以后，可以增加：

## 42.1 家庭资产负债

资产：

```text
现金
银行卡
支付宝
微信
基金
股票
房产
车辆
```

负债：

```text
信用卡
房贷
车贷
借款
```

计算：

```text
家庭总资产
-
家庭总负债
=
家庭净资产
```

---

## 42.2 智能预算

例如：

```text
家庭月收入：¥30,000

房贷：¥8,000
车贷：¥3,000
保险：¥1,500

可支配：¥17,500
```

自动设置：

```text
餐饮预算：¥2,000
购物预算：¥1,500
娱乐预算：¥800
交通预算：¥1,000
```

---

## 42.3 AI 财务分析

例如：

```text
过去3个月家庭餐饮支出：
平均 ¥2,860

本月：
¥3,450

比平均水平：
+20.6%
```

进一步：

```text
按照当前消费速度，

预计本月将超出家庭预算：
¥1,280
```

---

# 43. 产品竞争力

单纯：

> 家庭记账

竞争力较弱。

更好的定位：

> **AI 自动整理家庭财务**

核心闭环：

```text
支付宝账单
微信账单
银行账单
截图
自然语言
      ↓
统一交易数据
      ↓
自动去重
      ↓
自动识别转账
      ↓
AI 分类
      ↓
家庭账本
      ↓
预算
      ↓
财务分析
```

---

# 44. 推荐的核心技术壁垒

长期来看，产品真正可以形成壁垒的不是小程序 UI，而是：

## ① 多来源账单解析

```text
支付宝
微信
银行A
银行B
银行C
...
```

统一成标准交易模型。

## ② 交易去重

解决重复导入问题。

## ③ 转账识别

解决账户间资金转移导致的错误统计。

## ④ 商户标准化

例如：

```text
美团
美团外卖
美团支付
某某美团商户
```

统一到：

```text
美团
```

## ⑤ 个性化 AI 分类

学习每个家庭的分类习惯。

## ⑥ 家庭财务分析

从“记录数据”进一步变成“理解数据”。

---

# 45. 推荐最终产品架构

```text
                         微信小程序
                              │
          ┌───────────────────┼──────────────────┐
          ↓                   ↓                  ↓
        首页                 账单                统计
          │                   │                  │
          └───────────────────┼──────────────────┘
                              ↓
                           API Server
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
    用户/家庭服务          账务服务              AI服务
        │                     │                     │
        │             ┌───────┼───────┐             │
        │             ↓       ↓       ↓             │
        │           导入     去重    转账识别       │
        │             │       │       │             │
        │             └───────┼───────┘             │
        │                     ↓                     │
        │                 Transaction              │
        │                     │                     │
        │                     ↓                     │
        │                  AI分类 ←─────────────────┘
        │                     │
        └─────────────────────┼─────────────────────
                              ↓
                          PostgreSQL
                              │
                         Object Storage
```

---

# 46. 推荐开发优先级

最终按照以下顺序开发：

```text
第一阶段
微信登录
 ↓
家庭
 ↓
成员
 ↓
账户

第二阶段
手动记账
 ↓
收入 / 支出 / 转账
 ↓
分类
 ↓
账单列表

第三阶段
月度统计
 ↓
分类统计
 ↓
预算

第四阶段
支付宝账单导入
 ↓
微信账单导入
 ↓
银行卡账单导入

第五阶段
交易标准化
 ↓
去重
 ↓
转账识别
 ↓
退款识别
 ↓
商户标准化

第六阶段
AI自动分类
 ↓
自然语言记账
 ↓
OCR截图记账

第七阶段
家庭资产负债
 ↓
AI财务分析
 ↓
个性化财务助手
```

---

# 47. 下一步技术工作

进入实际开发前，建议优先完成以下设计：

1. **统一 Transaction Schema**
2. **支付宝账单字段映射**
3. **微信账单字段映射**
4. **银行卡 CSV/Excel 字段映射**
5. **银行卡 PDF 解析方案**
6. **OCR 交易识别方案**
7. **交易去重算法**
8. **转账匹配算法**
9. **退款关联算法**
10. **商户标准化算法**
11. **AI 分类 Prompt / Schema**
12. **PostgreSQL 完整建表 SQL**
13. **FastAPI API Schema**
14. **微信小程序页面原型**

其中优先级最高的是：

> **统一 Transaction Schema + 多来源账单解析器 + 去重/转账识别。**

这三个模块决定了整个产品的数据基础，也是后续最容易产生技术债务的地方。

---

# 48. 微信小程序页面开发设计

本节将前面的产品页面和后端 API 约定转换为可实施的小程序页面方案。当前仓库已完成 `wx_mini-program/server` 领域服务，并已创建 `wx_mini-program/miniprogram` 前端目录骨架与核心页面；页面开发按本节目录和接口契约执行。

## 48.1 页面范围与路由

底部 TabBar 固定为四项，页面路径和职责如下：

| 页面 | 路径 | 类型 | 核心职责 | 主要接口 |
| --- | --- | --- | --- | --- |
| 首页 | `pages/home/index` | TabBar | 本月收支、分类排行、预算卡片和快捷记账 | `GET /statistics/home` |
| 账单 | `pages/transactions/index` | TabBar | 月份筛选、日期分组、账单分页和详情入口 | `GET /transactions` |
| 统计 | `pages/statistics/index` | TabBar | 趋势、分类、成员和预算统计 | `GET /statistics/monthly`、`/statistics/category` |
| 我的 | `pages/profile/index` | TabBar | 当前家庭、账户、成员、分类、预算和导入入口 | `GET /families`、`GET /accounts` |
| 登录 | `pages/auth/login` | 普通页 | 微信授权、登录态初始化 | `POST /auth/wechat-login` |
| 家庭选择 | `pages/family/select` | 普通页 | 创建家庭、切换当前家庭 | `GET/POST /families` |
| 成员管理 | `pages/family/members` | 普通页 | 查看成员、邀请、角色变更和禁用 | `POST /families/{id}/members` |
| 账户管理 | `pages/accounts/index` | 普通页 | 账户列表、新增、编辑和停用 | `GET/POST /accounts`、`PUT /accounts/{id}` |
| 记一笔 | `pages/transactions/edit` | 普通页 | 新增/编辑收入、支出和转账 | `POST/PUT /transactions` |
| 交易详情 | `pages/transactions/detail` | 普通页 | 查看审计字段、编辑或删除交易 | `GET/PUT/DELETE /transactions/{id}` |
| 分类管理 | `pages/categories/index` | 普通页 | 查看内置分类、新增和删除家庭分类 | `GET/POST /categories` |
| 预算管理 | `pages/budgets/index` | 普通页 | 分类预算新增、修改、停用和使用率 | `GET/POST/PUT /budgets` |
| 导入账单 | `pages/imports/index` | 普通页 | 选择支付宝/微信文件并创建导入任务 | `POST /imports` |
| 导入审核 | `pages/imports/review` | 普通页 | 预览错误、重复、低置信度行并确认入账 | `GET /imports/{id}/transactions`、`POST /imports/{id}/confirm` |
| AI 记账 | `pages/ai/parse` | 普通页 | 输入自然语言并确认 AI 建议 | `POST /ai/parse-text`、`POST /transactions` |

页面跳转规则：未登录先进入 `pages/auth/login`；登录后没有家庭进入 `pages/family/select`；存在当前家庭才允许进入账单、统计和账户页面。所有普通页从全局状态读取 `currentFamilyId`，禁止从客户端传入任意家庭 ID 绕过服务端权限校验。

## 48.2 前端目录结构

```text
wx_mini-program/miniprogram/
├── app.js                 # 应用启动、登录态和当前家庭初始化
├── app.json               # pages、tabBar、window 配置
├── app.wxss               # 颜色、间距、字体等全局样式变量
├── pages/
│   ├── auth/login/
│   ├── family/select/
│   ├── family/members/
│   ├── home/index/
│   ├── transactions/index/
│   ├── transactions/edit/
│   ├── transactions/detail/
│   ├── statistics/index/
│   ├── profile/index/
│   ├── accounts/index/
│   ├── categories/index/
│   ├── budgets/index/
│   ├── imports/index/
│   ├── imports/review/
│   └── ai/parse/
├── components/
│   ├── transaction-item/  # 交易行，收入/支出颜色和状态标签
│   ├── amount-card/       # 收入、支出、结余卡片
│   ├── category-picker/   # 一级/二级分类选择
│   ├── account-picker/    # 仅展示当前用户可见且 active 的账户
│   ├── member-picker/     # owner/admin 可选择成员
│   ├── budget-card/       # 预算进度和超支状态
│   ├── empty-state/       # 空数据和错误重试
│   └── family-switcher/   # 当前家庭切换
├── services/
│   ├── api.js             # request 封装、鉴权头、错误码转换
│   ├── auth.js            # wx.login、token 持久化和刷新
│   ├── family.js          # 家庭/成员/账户 API
│   ├── transaction.js     # 交易 API
│   ├── statistics.js      # 统计/预算 API
│   └── import.js          # 文件选择、上传和导入任务 API
├── store/
│   └── app-store.js       # token、user、families、currentFamilyId
└── utils/
    ├── format.js          # 金额、日期、百分比格式化
    ├── permission.js      # 仅用于按钮展示，最终权限以后端为准
    └── validate.js        # 表单和分页参数校验
```

## 48.3 全局状态与请求约定

`app-store` 至少维护以下状态：

```js
{
  token: null,
  user: null,
  families: [],
  currentFamilyId: null,
  currentMember: null
}
```

请求流程统一为：

```text
页面 onLoad/onShow
  ↓
读取 currentFamilyId
  ↓
services/*.js 发起请求（Authorization + X-Family-Id）
  ↓
200：更新页面数据
401：清除 token，跳转登录
403：提示无权限并刷新家庭上下文
422：展示字段级校验错误
5xx/网络错误：保留页面输入，显示重试按钮
```

金额在页面显示为两位小数；提交时以字符串传给 API，避免 JavaScript 浮点误差。列表请求默认 `page_size=20`，触底加载下一页；月份参数统一使用 `YYYY-MM`。

## 48.4 核心页面交互设计

### 首页

1. `onShow` 请求首页聚合数据，显示收入、支出、结余三张卡片。
2. 分类排行最多展示 5 项，点击进入统计页并带上分类筛选。
3. 预算卡片显示已用/预算、百分比和超预算颜色；点击进入预算管理。
4. 右下角“记一笔”打开 `transactions/edit`，默认类型为支出。
5. 无交易时展示空状态和“导入账单/记一笔”两个动作。

### 账单列表

1. 顶部月份选择器默认当前月，切换后重置分页。
2. 按日期分组显示交易，收入使用正向颜色、支出使用负向颜色，转账显示中性标签。
3. 下拉刷新重新加载汇总和第一页，触底加载下一页。
4. 点击交易进入详情；删除采用二次确认，成功后刷新当前分组。
5. 普通成员只渲染后端返回的可见账户和交易，不能通过修改页面参数查看其他账户。

### 记一笔

表单字段为类型、金额、分类、账户、成员、时间、商户和备注。转账类型额外显示转入账户并隐藏分类；成员只能选择自己，owner/admin 可选择家庭成员。保存按钮在请求期间禁用，成功后返回来源页面并刷新列表/首页。

### 统计页

提供“日/周/月”趋势切换和月份选择；分类、成员统计使用排行列表，预算使用进度条。图表组件只接收后端聚合后的数据，不在前端重复计算金额，避免和账本口径不一致。

### 导入审核页

显示任务状态、总数、收入/支出/转账、重复数和错误数。错误行展示错误原因，重复行默认跳过，低置信度行允许编辑分类和账户；“全部确认”提交后按钮锁定，任务完成后显示已入账数量。AI/OCR 结果同样必须经过用户确认，不能自动写入交易。

## 48.5 权限与状态展示

| 角色 | 可见页面/操作 | 前端展示策略 |
| --- | --- | --- |
| owner | 全部页面；管理成员、账户、分类和预算 | 显示全部管理入口 |
| admin | 家庭统计；管理成员（不能修改 owner）；管理账户、分类和预算 | 根据接口返回的权限隐藏 owner 专属操作 |
| member | 首页、账单、统计、记一笔；只能编辑自己的交易 | 隐藏成员/账户/预算管理入口 |

隐藏按钮只改善体验，不构成安全边界。服务端返回 `403` 时统一提示“暂无权限”，并重新拉取当前家庭成员关系。

## 48.6 页面开发顺序与验收

1. **基础壳**：`app.js/app.json`、登录、家庭选择、TabBar、请求封装和全局状态。
2. **M1 页面**：我的、家庭成员、账户管理，先打通真实登录态和家庭上下文。
3. **M2 页面**：记一笔、账单列表、交易详情、分类管理，接入交易权限和分页。
4. **M3 页面**：首页、统计、预算管理，核对页面汇总与服务端统计一致。
5. **M4 页面**：导入账单、导入审核，覆盖上传进度、任务失败、重复和确认幂等。

每个页面完成时至少验收：

- 首次进入、返回、下拉刷新和网络失败均有明确状态。
- 加载态不会重复提交，空态提供下一步操作，错误态提供重试。
- 页面金额、日期和分类显示与 API 返回一致。
- 普通成员无法通过页面参数越权读取或修改家庭数据。
- 真机验证窄屏布局、长文本商户名、键盘输入和安全区域适配。
