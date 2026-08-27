# Excel 账单分析原型

该原型用于验证家庭记账的核心数据闭环：Excel 解析、字段标准化、交易去重、规则分类、收支统计，以及生成可正式入账的交易集合。

## 安装

```bash
cd research-python
python -m pip install -r requirements.txt
```

## 命令行使用

```bash
python -m ledger.cli ./账单.xlsx --output ./已分类账单.csv

# 处理文件夹下所有 .xlsx/.xls/.xlsm/.csv 文件
python -m ledger.cli --dir ./账单目录 --output ./已分类账单.csv

# 同时处理子文件夹
python -m ledger.cli --dir ./账单目录 --recursive
```

Excel/CSV 至少需要日期/时间、商户/交易对方、金额三列；收支方向、账户、交易单号和备注为可选列。程序会自动跳过支付宝/微信账单前面的导出说明行，并兼容 GB18030 编码和常见中文列名。

命令行会输出交易总数、重复数、已入账数、收入、支出、结余和支出分类汇总。`--output` 导出已去重、已分类、状态为 `posted` 的交易，作为后续数据库入账的输入。

## Python API

```python
import pandas as pd
from ledger import analyze_dataframe

result = analyze_dataframe(pd.read_excel("账单.xlsx"), source="alipay")
print(result["totals"])
print(result["category_summary"])
posted = result["posted"]

# 目录级分析：跨文件合并、去重和统计
from ledger import analyze_directory
result = analyze_directory("./账单目录", recursive=True)
```

处理规则：

- 有交易单号时优先按“来源 + 交易单号”去重；没有或重复时使用来源、账户、时间、金额、商户计算 SHA-256 指纹。
- 重复记录保留在 `transactions` 中并标记 `duplicate`，不会直接删除；`posted` 只包含待正式入账的数据。
- 商户分类使用本地关键词规则；未知商户分类为“其他”，置信度较低，后续可接入 LLM 或用户确认流程。
- 当前统计把转账排除在家庭收入和支出之外；退款已单独分类，原交易关联和抵消逻辑可在此基础上扩展。

## 测试

```bash
cd research-python
pytest
```
