"""M4 支付宝/微信账单导入中间层。"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from .family import FamilyError, FamilyService
from .transactions import TransactionService, _money

TASK_STATUSES = ("uploaded", "parsing", "parsed", "reviewing", "completed", "failed")

COLUMN_ALIASES = {
    "time": ("交易时间", "交易日期", "时间", "日期", "交易时间(本地)", "date", "datetime", "time"),
    "merchant": ("交易对方", "对方", "商户", "商户名称", "交易名称", "商品说明", "摘要", "description", "merchant"),
    "amount": ("金额", "金额(元)", "交易金额", "发生金额", "amount", "money"),
    "direction": ("收/支", "收支", "收支类型", "交易类型", "方向", "direction", "type"),
    "account": ("账户", "支付方式", "支付渠道", "资金账户", "account"),
    "source_id": ("交易单号", "交易号", "流水号", "订单号", "交易ID", "transaction_id", "id"),
    "description": ("备注", "描述", "商品说明", "摘要", "description", "note"),
}

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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass
class ImportTask:
    id: str
    family_id: str
    uploader_id: str
    source: str
    file_name: str
    account_id: Optional[str] = None
    status: str = "uploaded"
    total_count: int = 0
    success_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    created_at: datetime = field(default_factory=_now)
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class ImportTransaction:
    id: str
    import_task_id: str
    row_number: int
    raw_data: dict
    transaction_time: Optional[datetime] = None
    merchant: str = ""
    amount: Optional[object] = None
    direction: str = ""
    account_id: Optional[str] = None
    category_id: Optional[str] = None
    description: str = ""
    source_transaction_id: Optional[str] = None
    transaction_hash: str = ""
    duplicate: bool = False
    confidence: float = 0.0
    status: str = "pending"
    error_reason: Optional[str] = None
    transaction_id: Optional[str] = None


class ImportService:
    """解析账单到中间层，确认后才写入正式 Transaction。"""

    def __init__(self, family_service: FamilyService, transaction_service: TransactionService, max_file_size: int = 20 * 1024 * 1024):
        self.family_service = family_service
        self.transaction_service = transaction_service
        self.max_file_size = max_file_size
        self.tasks: Dict[str, ImportTask] = {}
        self.rows: Dict[str, ImportTransaction] = {}

    def create_task(self, actor_user_id: str, family_id: str, path: str | Path, source: str, account_id: Optional[str] = None) -> ImportTask:
        self.family_service._require_member(actor_user_id, family_id)
        if source not in ("alipay", "wechat"):
            raise FamilyError("第7周仅支持 alipay 或 wechat 导入")
        file_path = Path(path)
        if not file_path.is_file():
            raise FamilyError("账单文件不存在")
        if file_path.suffix.lower() not in (".csv", ".xlsx", ".xls", ".xlsm"):
            raise FamilyError("仅支持 CSV/XLS/XLSX/XLSM 文件")
        if file_path.stat().st_size > self.max_file_size:
            raise FamilyError("账单文件超过大小限制")
        if account_id is not None:
            self.family_service.require_active_account(actor_user_id, family_id, account_id)
        task = ImportTask(_id("import"), family_id, actor_user_id, source, file_path.name, account_id)
        self.tasks[task.id] = task
        try:
            task.status = "parsing"
            frame = self._read_file(file_path, source)
            self._parse_rows(task, frame)
            task.status = "reviewing"
            if task.total_count == 0:
                task.status = "failed"
                task.error_message = "账单没有可解析交易"
            return task
        except Exception as error:
            task.status = "failed"
            task.error_message = str(error)
            return task

    def preview(self, actor_user_id: str, task_id: str) -> dict:
        task = self._require_task(task_id)
        self.family_service._require_member(actor_user_id, task.family_id)
        rows = [row for row in self.rows.values() if row.import_task_id == task_id]
        income = sum(1 for row in rows if row.direction == "income")
        expense = sum(1 for row in rows if row.direction == "expense")
        transfer = sum(1 for row in rows if row.direction == "transfer")
        return {"task": task, "rows": rows, "total": len(rows), "income_count": income, "expense_count": expense, "transfer_count": transfer, "duplicate_count": task.duplicate_count, "error_count": task.error_count}

    def confirm(self, actor_user_id: str, task_id: str, row_ids: Optional[List[str]] = None) -> ImportTask:
        task = self._require_task(task_id)
        self.family_service._require_member(actor_user_id, task.family_id)
        selected = set(row_ids) if row_ids is not None else None
        rows = [row for row in self.rows.values() if row.import_task_id == task_id and (selected is None or row.id in selected)]
        for row in rows:
            if row.status in ("confirmed", "skipped"):
                continue
            if row.error_reason or row.duplicate or row.direction == "neutral":
                row.status = "skipped"
                continue
            try:
                transaction = self.transaction_service.create_transaction(
                    actor_user_id, task.family_id, row.direction, row.amount, row.account_id or task.account_id or "",
                    category_id=row.category_id, merchant=row.merchant, description=row.description,
                    transaction_time=row.transaction_time, source=task.source,
                    source_transaction_id=row.source_transaction_id, confidence=row.confidence,
                )
                row.transaction_id = transaction.id
                row.status = "confirmed"
                task.success_count += 1
            except Exception as error:
                row.status = "error"
                row.error_reason = str(error)
                task.error_count += 1
        remaining = [row for row in self.rows.values() if row.import_task_id == task_id and row.status in ("pending", "error")]
        task.status = "completed" if not remaining else "reviewing"
        if task.status == "completed":
            task.finished_at = _now()
        return task

    def retry(self, actor_user_id: str, task_id: str) -> ImportTask:
        task = self._require_task(task_id)
        self.family_service._require_member(actor_user_id, task.family_id)
        for row in self.rows.values():
            if row.import_task_id == task_id and row.status == "error":
                row.status = "pending"
                row.error_reason = None
        task.error_count = 0
        task.status = "reviewing"
        return task

    def _read_file(self, path: Path, source: str) -> pd.DataFrame:
        if path.suffix.lower() == ".csv":
            text = None
            for encoding in ("utf-8-sig", "gb18030", "gbk"):
                try:
                    text = path.read_text(encoding=encoding)
                    lines = text.splitlines()
                    header = next((i for i, line in enumerate(lines) if self._header_score(next(csv.reader([line]))) >= 2), None)
                    if header is not None:
                        return pd.read_csv(io.StringIO(text), header=header, dtype=str, skip_blank_lines=False)
                except (UnicodeDecodeError, pd.errors.ParserError, StopIteration):
                    continue
            if text is None:
                raise FamilyError("无法识别 CSV 编码")
            lines = text.splitlines()
            header = next((i for i, line in enumerate(lines) if self._header_score(next(csv.reader([line]))) >= 2), None)
            if header is None:
                raise FamilyError("未找到账单表头")
            return pd.read_csv(io.StringIO(text), header=header, dtype=str, skip_blank_lines=False)
        raw = pd.read_excel(path, header=None)
        header = next((i for i in raw.index if self._header_score(raw.loc[i].tolist()) >= 2), None)
        if header is None:
            raise FamilyError("未找到 Excel 账单表头")
        return pd.read_excel(path, header=header)

    def _parse_rows(self, task: ImportTask, frame: pd.DataFrame) -> None:
        aliases = {
            "time": ("交易时间", "交易日期", "日期", "时间", "date", "datetime"),
            "merchant": ("交易对方", "对方", "商户", "商户名称", "交易名称", "摘要", "description"),
            "amount": ("金额", "交易金额", "发生金额", "amount", "money"),
            "direction": ("收支", "收支类型", "交易类型", "方向", "direction", "type"),
            "account": ("账户", "支付方式", "支付渠道", "资金账户", "account"),
            "source_id": ("交易单号", "交易号", "流水号", "订单号", "交易ID", "transaction_id", "id"),
            "description": ("备注", "描述", "商品说明", "description", "note"),
        }
        columns = {self._clean(column): column for column in frame.columns}
        selected = {key: self._find_column(list(frame.columns), values) for key, values in COLUMN_ALIASES.items()}
        if any(selected[key] is None for key in ("time", "merchant", "amount")):
            raise FamilyError("账单缺少日期、商户或金额列")
        for index, raw in frame.iterrows():
            values = raw.to_dict()
            row = ImportTransaction(_id("imptx"), task.id, int(index) + 1, values)
            merchant = raw[selected["merchant"]]
            row.merchant = "" if pd.isna(merchant) else str(merchant).strip()
            description = raw[selected["description"]] if selected["description"] else ""
            row.description = "" if pd.isna(description) else str(description).strip()
            row.account_id = task.account_id
            row.source_transaction_id = str(raw[selected["source_id"]]).strip() if selected["source_id"] and pd.notna(raw[selected["source_id"]]) else None
            try:
                row.transaction_time = pd.to_datetime(raw[selected["time"]]).to_pydatetime()
                if row.transaction_time.tzinfo is None:
                    row.transaction_time = row.transaction_time.replace(tzinfo=timezone.utc)
                signed_amount = self._parse_amount(raw[selected["amount"]])
                row.amount = abs(signed_amount)
                direction_value = raw[selected["direction"]] if selected["direction"] else ""
                direction_text = "" if pd.isna(direction_value) else str(direction_value)
                row.direction = self._direction(direction_text, signed_amount)
                row.transaction_hash = self.transaction_service._transaction_hash(task.family_id, task.source, task.account_id or "", row.transaction_time, row.amount, self.transaction_service.normalize_merchant(row.merchant))
                row.duplicate = self._is_duplicate(task, row)
                category, row.confidence = self._classify(row.merchant, row.description, row.direction)
                row.category_id = self._category_id(task.family_id, category)
                if row.duplicate:
                    row.status = "duplicate"
                    task.duplicate_count += 1
            except Exception as error:
                row.status = "error"
                row.error_reason = str(error)
                task.error_count += 1
            self.rows[row.id] = row
        task.total_count = len([row for row in self.rows.values() if row.import_task_id == task.id])

    @classmethod
    def _find_column(cls, columns: List[object], aliases: object) -> Optional[object]:
        normalized = {cls._clean(column): column for column in columns}
        names = [cls._clean(alias) for alias in aliases]
        for alias in names:
            if alias in normalized:
                return normalized[alias]
        for column in columns:
            name = cls._clean(column)
            if any(alias in name or name in alias for alias in names):
                return column
        return None

    def _classify(self, merchant: str, description: str, direction: str) -> tuple[str, float]:
        if direction == "transfer":
            return "转账", 1.0
        if direction == "neutral":
            return "不计收支", 1.0
        if direction == "income":
            if "退款" in merchant or "退款" in description:
                return "退款", 0.99
            return "收入-其他", 0.60
        text = f"{merchant} {description}".lower()
        for rule in DEFAULT_RULES:
            if any(keyword.lower() in text for keyword in rule.keywords):
                return rule.category, 0.95
        return "其他", 0.20

    def _category_id(self, family_id: str, category_name: str) -> Optional[str]:
        for category in self.transaction_service.categories.values():
            if category.status == "active" and category.family_id in ("*", family_id) and category.name == category_name:
                return category.id
        return None

    def _is_duplicate(self, task: ImportTask, row: ImportTransaction) -> bool:
        for existing in self.rows.values():
            if existing.import_task_id == task.id and existing.id != row.id and (row.source_transaction_id and existing.source_transaction_id == row.source_transaction_id):
                return True
        return any(
            transaction.family_id == task.family_id
            and (
                transaction.transaction_hash == row.transaction_hash
                or (
                    row.source_transaction_id
                    and transaction.source == task.source
                    and transaction.account_id == (row.account_id or task.account_id)
                    and transaction.source_transaction_id == row.source_transaction_id
                )
            )
            for transaction in self.transaction_service.transactions.values()
        )

    @staticmethod
    def _clean(value: object) -> str:
        return "".join(str(value).split()).lower()

    @classmethod
    def _header_score(cls, row: List[object]) -> int:
        aliases = ("交易时间", "日期", "商户", "交易对方", "金额", "收支", "amount", "date")
        values = [cls._clean(value) for value in row if not pd.isna(value)]
        return sum(1 for value in values if any(alias in value for alias in aliases))

    @staticmethod
    def _direction(value: str, amount: object) -> str:
        text = value.lower()
        if any(token in text for token in ("不计收支", "中性交易", "neutral")):
            return "neutral"
        if any(token in text for token in ("转入转出", "转入", "转出")):
            return "transfer"
        if any(token in text for token in ("转账", "transfer")):
            return "transfer"
        if any(token in text for token in ("收入", "退款", "收款", "credit", "in")):
            return "income"
        if any(token in text for token in ("支出", "消费", "付款", "debit", "out")):
            return "expense"
        return "expense" if Decimal(str(amount)) < 0 else "income"

    @staticmethod
    def _parse_amount(value: object):
        text = str(value).strip().replace(",", "")
        negative = text.startswith("(") and text.endswith(")")
        text = re.sub(r"[^0-9.\-+]", "", text).strip("()")
        if not text:
            raise FamilyError("金额为空")
        amount = Decimal(text)
        return -abs(amount) if negative else amount

    def _require_task(self, task_id: str) -> ImportTask:
        task = self.tasks.get(task_id)
        if not task:
            raise FamilyError("导入任务不存在")
        return task
