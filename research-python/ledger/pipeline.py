from __future__ import annotations

import hashlib
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


COLUMN_ALIASES = {
    "transaction_time": ["交易时间", "交易日期", "时间", "日期", "交易时间(本地)", "date", "datetime", "time"],
    "merchant": ["交易对方", "对方", "商户", "商户名称", "交易名称", "商品说明", "摘要", "description", "merchant"],
    "amount": ["金额", "交易金额", "发生金额", "amount", "money"],
    "direction": ["收/支", "收支", "交易类型", "方向", "direction", "type"],
    "account": ["账户", "支付方式", "支付渠道", "资金账户", "account"],
    "source_transaction_id": ["交易单号", "交易号", "流水号", "订单号", "交易ID", "transaction_id", "id"],
    "description": ["备注", "商品说明", "摘要", "描述", "description", "note"],
}
SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".xlsm", ".csv"}


@dataclass(frozen=True)
class CategoryRule:
    category: str
    keywords: tuple[str, ...]


DEFAULT_RULES = (
    CategoryRule("餐饮", ("美团", "外卖", "饿了么", "星巴克", "餐厅", "火锅", "肯德基", "麦当劳")),
    CategoryRule("交通", ("滴滴", "打车", "地铁", "公交", "加油", "高德", "出租车")),
    CategoryRule("购物", ("淘宝", "天猫", "京东", "拼多多", "购物", "盒马", "山姆")),
    CategoryRule("住房", ("房租", "房贷", "物业", "水电")),
    CategoryRule("娱乐", ("电影", "游戏", "旅游", "演出")),
    CategoryRule("医疗", ("医院", "药房", "医疗")),
    CategoryRule("教育", ("学费", "培训", "教育")),
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", "", str(value)).strip().lower()


def _find_column(columns: list[Any], aliases: list[str]) -> Any | None:
    normalized = {_clean(column): column for column in columns}
    for alias in aliases:
        if _clean(alias) in normalized:
            return normalized[_clean(alias)]
    for column in columns:
        name = _clean(column)
        if any(_clean(alias) in name or name in _clean(alias) for alias in aliases):
            return column
    return None


def _header_score(row: Any) -> int:
    values = {_clean(value) for value in row if not pd.isna(value)}
    aliases = {_clean(alias) for names in COLUMN_ALIASES.values() for alias in names}
    return sum(1 for value in values if value in aliases or any(alias in value for alias in aliases))


def _find_header_row(frame: pd.DataFrame) -> int:
    scores = frame.apply(_header_score, axis=1)
    matches = scores[scores >= 2]
    if matches.empty:
        raise ValueError("未找到账单表头；请确认文件包含日期、商户和金额列")
    return int(matches.index[0])


def _read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "gb18030", "gbk"):
        try:
            text = path.read_text(encoding=encoding)
            header_row = next(
                index for index, line in enumerate(text.splitlines())
                if _header_score(next(csv.reader([line]))) >= 2
            )
            return pd.read_csv(io.StringIO(text), header=header_row, dtype=str, skip_blank_lines=False)
        except (UnicodeDecodeError, pd.errors.ParserError, StopIteration):
            continue
    raise ValueError(f"无法解析 CSV 账单或未找到账单表头: {path}")


def _read_excel(path: Path, sheet_name: int | str = 0) -> pd.DataFrame:
    try:
        raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
        header_row = _find_header_row(raw)
        return pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    except ImportError as error:
        raise RuntimeError("读取 Excel 需要安装 openpyxl（.xlsx/.xlsm）或对应 Excel 引擎，请先执行 pip install -r requirements.txt") from error


def _read_bill_file(path: Path, sheet_name: int | str = 0) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return _read_csv(path)
    return _read_excel(path, sheet_name=sheet_name)


def _parse_amount(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip().replace(",", "").replace("¥", "").replace("￥", "")
    text = re.sub(r"[^0-9.()\-+]", "", text)
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    amount = float(text)
    return -abs(amount) if negative else amount


def _direction(value: Any, amount: float) -> str:
    text = str(value).strip().lower() if not pd.isna(value) else ""
    if any(token in text for token in ("不计收支", "中性交易", "neutral")):
        return "neutral"
    if any(token in text for token in ("转账", "transfer", "转入转出")):
        return "transfer"
    if any(token in text for token in ("支出", "消费", "付款", "转出", "expense", "debit", "out")):
        return "expense"
    if any(token in text for token in ("收入", "退款", "收款", "转入", "income", "credit", "in")):
        return "income"
    return "expense" if amount < 0 else "income"


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    selected: dict[str, Any] = {}
    for target, aliases in COLUMN_ALIASES.items():
        column = _find_column(list(frame.columns), aliases)
        if column is not None:
            selected[target] = column
    required = {"transaction_time", "merchant", "amount"}
    missing = required - selected.keys()
    if missing:
        raise ValueError(f"账单缺少必要列: {', '.join(sorted(missing))}；需要日期、商户和金额列")

    result = pd.DataFrame(index=frame.index)
    for target, source in selected.items():
        result[target] = frame[source]
    for optional in ("direction", "account", "source_transaction_id", "description"):
        if optional not in result:
            result[optional] = ""
    result["transaction_time"] = pd.to_datetime(result["transaction_time"], errors="coerce")
    if result["transaction_time"].isna().any():
        raise ValueError("存在无法解析的交易日期，请检查日期格式")
    result["merchant"] = result["merchant"].fillna("").astype(str).str.strip()
    result["description"] = result["description"].fillna("").astype(str).str.strip()
    result["account"] = result["account"].fillna("").astype(str).str.strip()
    result["amount_raw"] = result["amount"]
    result["amount"] = result["amount"].map(_parse_amount)
    result["direction"] = [
        _direction(direction, amount) for direction, amount in zip(result["direction"], result["amount"])
    ]
    result["amount"] = result.apply(
        lambda row: abs(row["amount"]) if row["direction"] in ("income", "expense", "transfer") else row["amount"], axis=1
    )
    result["source_transaction_id"] = result["source_transaction_id"].fillna("").astype(str).str.strip()
    return result.reset_index(drop=True)


def _hash_row(row: pd.Series, source: str) -> str:
    values = "|".join(
        (source, str(row["account"]), row["transaction_time"].isoformat(), f"{row['amount']:.2f}", row["merchant"].lower())
    )
    return hashlib.sha256(values.encode("utf-8")).hexdigest()


def classify_transaction(merchant: str, description: str, direction: str, rules=DEFAULT_RULES) -> tuple[str, float]:
    if direction == "transfer":
        return "转账", 1.0
    if direction == "neutral":
        return "不计收支", 1.0
    if direction == "income":
        if "退款" in merchant or "退款" in description:
            return "退款", 0.99
        return "收入-其他", 0.60
    text = f"{merchant} {description}".lower()
    for rule in rules:
        if any(keyword.lower() in text for keyword in rule.keywords):
            return rule.category, 0.95
    return "其他", 0.20


def _result_from_transactions(transactions: pd.DataFrame) -> dict[str, Any]:
    accepted = transactions[~transactions["duplicate"]].copy()
    accepted["status"] = "posted"
    totals = {
        "income": round(float(accepted.loc[accepted.direction == "income", "amount"].sum()), 2),
        "expense": round(float(accepted.loc[accepted.direction == "expense", "amount"].sum()), 2),
    }
    totals["balance"] = round(totals["income"] - totals["expense"], 2)
    category_summary = (
        accepted[accepted.direction == "expense"].groupby("category", dropna=False)["amount"].agg(["sum", "count"])
        .rename(columns={"sum": "amount"})
        .sort_values("amount", ascending=False)
        .reset_index()
    )
    monthly = accepted.assign(month=accepted["transaction_time"].dt.to_period("M").astype(str)).groupby(
        ["month", "direction"], as_index=False
    )["amount"].sum()
    return {
        "transactions": transactions,
        "posted": accepted,
        "totals": totals,
        "category_summary": category_summary,
        "monthly_summary": monthly,
        "total_count": len(transactions),
        "duplicate_count": int(transactions["duplicate"].sum()),
        "posted_count": len(accepted),
    }


def analyze_dataframe(frame: pd.DataFrame, source: str = "excel", rules=DEFAULT_RULES) -> dict[str, Any]:
    """Parse and analyse a bill DataFrame without writing it to a database."""
    transactions = _normalise_columns(frame)
    transactions["source"] = source
    transactions["transaction_hash"] = transactions.apply(lambda row: _hash_row(row, source), axis=1)
    transactions["duplicate"] = False
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for index, row in transactions.iterrows():
        source_id = row["source_transaction_id"]
        duplicate = (bool(source_id) and source_id in seen_ids) or row["transaction_hash"] in seen_hashes
        transactions.at[index, "duplicate"] = duplicate
        if source_id:
            seen_ids.add(source_id)
        seen_hashes.add(row["transaction_hash"])
    categories = transactions.apply(
        lambda row: classify_transaction(row["merchant"], row["description"], row["direction"], rules), axis=1
    )
    transactions["category"] = [item[0] for item in categories]
    transactions["confidence"] = [item[1] for item in categories]
    transactions["status"] = transactions["duplicate"].map(lambda value: "duplicate" if value else "pending")
    return _result_from_transactions(transactions)


def analyze_file(path: str | Path, source: str | None = None, sheet_name: int | str = 0) -> dict[str, Any]:
    """Read an Excel workbook and run the analysis pipeline."""
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("目前支持 .xlsx、.xls、.xlsm 或 .csv 文件")
    frame = _read_bill_file(path, sheet_name=sheet_name)
    return analyze_dataframe(frame, source=source or path.stem)


def analyze_directory(
    directory: str | Path,
    pattern: str = "*",
    recursive: bool = False,
    sheet_name: int | str = 0,
    rules=DEFAULT_RULES,
) -> dict[str, Any]:
    """Analyse all Excel files in a directory and deduplicate across files."""
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"账单目录不存在或不是文件夹: {directory}")
    patterns = {pattern} if pattern != "*" else {"*.xlsx", "*.xls", "*.xlsm", "*.csv"}
    files: list[Path] = []
    for item in patterns:
        files.extend(directory.rglob(item) if recursive else directory.glob(item))
    files = sorted({file for file in files if file.is_file() and file.suffix.lower() in SUPPORTED_SUFFIXES})
    if not files:
        raise FileNotFoundError(f"目录中没有找到 Excel 账单文件: {directory}")

    results = [analyze_file(file, source=file.stem, sheet_name=sheet_name) for file in files]
    transactions = pd.concat([result["transactions"] for result in results], ignore_index=True)
    transactions["duplicate"] = False
    seen_ids: set[tuple[str, str]] = set()
    seen_hashes: set[str] = set()
    for index, row in transactions.iterrows():
        source_id = row["source_transaction_id"]
        source_key = (row["source"], source_id)
        neutral_hash = _hash_row(row, "")
        duplicate = (bool(source_id) and source_key in seen_ids) or neutral_hash in seen_hashes
        transactions.at[index, "duplicate"] = duplicate
        if source_id:
            seen_ids.add(source_key)
        seen_hashes.add(neutral_hash)
    result = _result_from_transactions(transactions)
    result["files"] = files
    result["file_count"] = len(files)
    return result
