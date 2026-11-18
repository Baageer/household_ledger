"""M2 手动记账、账单列表和分类管理领域服务。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import re
from typing import Dict, List, Optional
from uuid import uuid4

from .family import FamilyError, FamilyService, PermissionDenied

TRANSACTION_TYPES = ("income", "expense", "transfer", "refund")
_UNSET = object()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise FamilyError("金额必须是有效数字")
    if amount <= 0:
        raise FamilyError("金额必须大于 0")
    return amount


@dataclass
class Category:
    id: str
    family_id: str
    name: str
    parent_id: Optional[str] = None
    system: bool = False
    status: str = "active"
    created_at: datetime = field(default_factory=_now)


@dataclass
class Transaction:
    id: str
    family_id: str
    account_id: str
    member_id: str
    type: str
    amount: Decimal
    category_id: Optional[str]
    merchant: str
    description: str
    transaction_time: datetime
    source: str = "manual"
    transfer_to_account_id: Optional[str] = None
    source_transaction_id: Optional[str] = None
    transaction_hash: str = ""
    normalized_merchant: str = ""
    linked_transaction_id: Optional[str] = None
    raw_data_ref: Optional[str] = None
    created_by: str = ""
    confidence: Optional[Decimal] = None
    status: str = "posted"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


class TransactionService:
    """Use ``FamilyService`` for membership and account authorization."""

    def __init__(self, family_service: FamilyService, merchant_rules: Optional[Dict[str, str]] = None):
        self.family_service = family_service
        self.transactions: Dict[str, Transaction] = {}
        self.categories: Dict[str, Category] = {}
        self.merchant_rules = {self._normalize_text(k): v.strip() for k, v in (merchant_rules or {}).items()}
        self.category_rules: Dict[str, Dict[str, str]] = {}
        self._seed_system_categories()

    def _seed_system_categories(self) -> None:
        for name in ("餐饮", "交通", "购物", "住房", "娱乐", "医疗", "教育", "其他", "收入-其他", "退款"):
            category = Category(_id("cat"), "*", name, system=True)
            self.categories[category.id] = category

    def list_categories(self, actor_user_id: str, family_id: str) -> List[Category]:
        self.family_service._require_member(actor_user_id, family_id)
        return [c for c in self.categories.values() if c.status == "active" and c.family_id in ("*", family_id)]

    def create_category(self, actor_user_id: str, family_id: str, name: str, parent_id: Optional[str] = None) -> Category:
        self._require_manager(actor_user_id, family_id)
        if not name or not name.strip():
            raise FamilyError("分类名称不能为空")
        if parent_id is not None:
            parent = self.categories.get(parent_id)
            if not parent or parent.status != "active" or parent.family_id not in ("*", family_id):
                raise FamilyError("父级分类不存在")
        category = Category(_id("cat"), family_id, name.strip(), parent_id=parent_id)
        self.categories[category.id] = category
        return category

    def delete_category(self, actor_user_id: str, family_id: str, category_id: str) -> Category:
        self._require_manager(actor_user_id, family_id)
        category = self.categories.get(category_id)
        if not category or category.family_id not in ("*", family_id):
            raise FamilyError("分类不存在")
        if category.system:
            raise FamilyError("内置分类不可删除")
        if any(t.category_id == category_id and t.status != "deleted" for t in self.transactions.values()):
            raise FamilyError("分类已被交易引用，不能删除")
        category.status = "deleted"
        return category

    def create_transaction(
        self,
        actor_user_id: str,
        family_id: str,
        transaction_type: str,
        amount: object,
        account_id: str,
        category_id: Optional[str] = None,
        member_id: Optional[str] = None,
        merchant: str = "",
        description: str = "",
        transaction_time: Optional[datetime] = None,
        transfer_to_account_id: Optional[str] = None,
        source: str = "manual",
        source_transaction_id: Optional[str] = None,
        raw_data_ref: Optional[str] = None,
        linked_transaction_id: Optional[str] = None,
        confidence: Optional[object] = None,
    ) -> Transaction:
        self.family_service._require_member(actor_user_id, family_id)
        if transaction_type not in TRANSACTION_TYPES:
            raise FamilyError("无效的交易类型")
        account = self.family_service.require_active_account(actor_user_id, family_id, account_id)
        target_member_id = member_id or actor_user_id
        self.family_service._require_member(target_member_id, family_id)
        if target_member_id != actor_user_id:
            self._require_manager(actor_user_id, family_id)
        if transaction_type == "transfer":
            if not transfer_to_account_id or transfer_to_account_id == account_id:
                raise FamilyError("转账必须指定不同的转入账户")
            self.family_service.require_active_account(actor_user_id, family_id, transfer_to_account_id)
            category_id = None
        elif transaction_type == "refund":
            if not linked_transaction_id:
                raise FamilyError("退款必须关联原支出交易")
            original = self._require_transaction(linked_transaction_id, family_id)
            if original.type != "expense":
                raise FamilyError("退款只能关联支出交易")
            if category_id is None:
                category_id = original.category_id
        elif category_id is not None:
            self._require_category(category_id, family_id)
        when = transaction_time or _now()
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        merchant_text = (merchant or "").strip()
        normalized_merchant = self.normalize_merchant(merchant_text)
        transaction_hash = self._transaction_hash(
            family_id, source, account_id, when, _money(amount), normalized_merchant
        )
        duplicate = self._find_duplicate(family_id, account_id, source, source_transaction_id, transaction_hash)
        if duplicate:
            return duplicate
        parsed_confidence = None if confidence is None else Decimal(str(confidence)).quantize(Decimal("0.01"))
        transaction = Transaction(
            id=_id("txn"), family_id=family_id, account_id=account_id, member_id=target_member_id,
            type=transaction_type, amount=_money(amount), category_id=category_id,
            merchant=merchant_text, description=(description or "").strip(),
            transaction_time=when, source=source, transfer_to_account_id=transfer_to_account_id,
            source_transaction_id=source_transaction_id, transaction_hash=transaction_hash,
            normalized_merchant=normalized_merchant, linked_transaction_id=linked_transaction_id,
            raw_data_ref=raw_data_ref, created_by=actor_user_id, confidence=parsed_confidence,
        )
        self.transactions[transaction.id] = transaction
        return transaction

    def normalize_merchant(self, merchant: str) -> str:
        normalized = self._normalize_text(merchant)
        for keyword, standard in self.merchant_rules.items():
            if keyword and keyword in normalized:
                return standard
        return merchant.strip()

    def learn_category_rule(self, family_id: str, merchant: str, category_id: Optional[str]) -> None:
        """记录用户对商户分类的选择，供同一家庭后续导入优先命中。"""
        key = self._normalize_text(self.normalize_merchant(merchant))
        if not key or not category_id:
            return
        category = self.categories.get(category_id)
        if not category or category.status != "active" or category.family_id not in ("*", family_id):
            return
        self.category_rules.setdefault(family_id, {})[key] = category_id

    def match_category_rule(self, family_id: str, merchant: str) -> Optional[str]:
        """返回该家庭为商户学习到的分类；先精确匹配，再按最长关键词匹配相似商户。"""
        rules = self.category_rules.get(family_id)
        key = self._normalize_text(self.normalize_merchant(merchant))
        if not rules or not key:
            return None
        matches = [key] if key in rules else []
        matches.extend(rule_key for rule_key in rules if len(rule_key) >= 2 and rule_key != key and rule_key in key)
        for rule_key in sorted(matches, key=len, reverse=True):
            category = self.categories.get(rules[rule_key])
            if category and category.status == "active":
                return category.id
        return None

    def find_transfer_candidates(
        self, actor_user_id: str, family_id: str, account_id: str,
        amount: object, transaction_time: datetime, window_minutes: int = 24 * 60
    ) -> List[Transaction]:
        self.family_service._require_member(actor_user_id, family_id)
        if window_minutes < 0:
            raise FamilyError("转账匹配时间窗口不能为负数")
        target_amount = _money(amount)
        candidates = []
        for transaction in self.transactions.values():
            if transaction.family_id != family_id or transaction.status == "deleted" or transaction.type != "transfer":
                continue
            if transaction.account_id == account_id or transaction.transfer_to_account_id == account_id:
                if abs(transaction.amount - target_amount) != 0:
                    continue
                delta = abs((transaction.transaction_time - transaction_time).total_seconds())
                if delta <= window_minutes * 60:
                    candidates.append(transaction)
        return sorted(candidates, key=lambda item: abs((item.transaction_time - transaction_time).total_seconds()))

    def link_refund(self, actor_user_id: str, family_id: str, refund_id: str, original_id: str) -> Transaction:
        refund = self._require_transaction(refund_id, family_id)
        original = self._require_transaction(original_id, family_id)
        self._authorize_write(actor_user_id, family_id, refund)
        if refund.type != "refund" or original.type != "expense":
            raise FamilyError("退款只能关联支出交易")
        refund.linked_transaction_id = original.id
        if refund.category_id is None:
            refund.category_id = original.category_id
        refund.updated_at = _now()
        return refund

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", "", (value or "").strip().lower())

    @staticmethod
    def _transaction_hash(family_id: str, source: str, account_id: str, when: datetime, amount: Decimal, merchant: str) -> str:
        payload = "|".join((family_id, source, account_id, when.isoformat(), f"{amount:.2f}", merchant))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _find_duplicate(self, family_id: str, account_id: str, source: str, source_transaction_id: Optional[str], transaction_hash: str) -> Optional[Transaction]:
        for transaction in self.transactions.values():
            if transaction.family_id != family_id or transaction.status == "deleted":
                continue
            if source_transaction_id and transaction.source == source and transaction.account_id == account_id and transaction.source_transaction_id == source_transaction_id:
                return transaction
            if transaction.transaction_hash == transaction_hash:
                return transaction
        return None

    def update_transaction(self, actor_user_id: str, family_id: str, transaction_id: str, **changes: object) -> Transaction:
        transaction = self._require_transaction(transaction_id, family_id)
        self._authorize_write(actor_user_id, family_id, transaction)
        if transaction.status == "deleted":
            raise FamilyError("已删除交易不可编辑")
        if "amount" in changes:
            transaction.amount = _money(changes["amount"])
        if "category_id" in changes:
            category_id = changes["category_id"]
            if category_id is not None:
                self._require_category(str(category_id), family_id)
            transaction.category_id = category_id  # type: ignore[assignment]
        for field_name in ("merchant", "description"):
            if field_name in changes:
                setattr(transaction, field_name, str(changes[field_name] or "").strip())
        if "transaction_time" in changes:
            when = changes["transaction_time"]
            if not isinstance(when, datetime):
                raise FamilyError("交易时间必须是 datetime")
            transaction.transaction_time = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if "category_id" in changes and transaction.category_id:
            self.learn_category_rule(family_id, transaction.merchant, transaction.category_id)
        transaction.updated_at = _now()
        return transaction

    def delete_transaction(self, actor_user_id: str, family_id: str, transaction_id: str) -> Transaction:
        transaction = self._require_transaction(transaction_id, family_id)
        self._authorize_write(actor_user_id, family_id, transaction)
        transaction.status = "deleted"
        transaction.updated_at = _now()
        return transaction

    def list_transactions(
        self, actor_user_id: str, family_id: str, month: Optional[str] = None,
        page: int = 1, page_size: int = 50,
    ) -> dict:
        if page < 1 or page_size < 1 or page_size > 200:
            raise FamilyError("分页参数无效")
        actor = self.family_service._require_member(actor_user_id, family_id)
        rows = [t for t in self.transactions.values() if t.family_id == family_id and t.status != "deleted"]
        visible_accounts = {a.id for a in self.family_service.list_accounts(actor_user_id, family_id)}
        rows = [t for t in rows if t.account_id in visible_accounts]
        if actor.role == "member":
            rows = [t for t in rows if t.member_id == actor_user_id or t.account_id in visible_accounts]
        if month:
            try:
                year, month_number = (int(item) for item in month.split("-", 1))
                rows = [t for t in rows if t.transaction_time.year == year and t.transaction_time.month == month_number]
            except (ValueError, TypeError):
                raise FamilyError("月份格式应为 YYYY-MM")
        rows.sort(key=lambda t: t.transaction_time, reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        items = rows[start:start + page_size]
        groups: Dict[str, List[Transaction]] = {}
        for item in items:
            groups.setdefault(item.transaction_time.date().isoformat(), []).append(item)
        return {"items": items, "total": total, "page": page, "page_size": page_size, "groups": groups}

    def summary(self, actor_user_id: str, family_id: str, month: Optional[str] = None) -> dict:
        result = self.list_transactions(actor_user_id, family_id, month=month, page=1, page_size=200)
        rows = result["items"]
        income = sum((t.amount for t in rows if t.type == "income"), Decimal("0.00"))
        expense = sum((t.amount for t in rows if t.type == "expense"), Decimal("0.00"))
        return {"income": income, "expense": expense, "balance": income - expense}

    def _require_manager(self, actor_user_id: str, family_id: str) -> None:
        actor = self.family_service._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以执行此操作")

    def _authorize_write(self, actor_user_id: str, family_id: str, transaction: Transaction) -> None:
        actor = self.family_service._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin") and transaction.member_id != actor_user_id:
            raise PermissionDenied("不能修改其他成员的交易")

    def _require_category(self, category_id: str, family_id: str) -> Category:
        category = self.categories.get(category_id)
        if not category or category.status != "active" or category.family_id not in ("*", family_id):
            raise FamilyError("分类不存在或已停用")
        return category

    def _require_transaction(self, transaction_id: str, family_id: str) -> Transaction:
        transaction = self.transactions.get(transaction_id)
        if not transaction or transaction.family_id != family_id:
            raise FamilyError("交易不存在")
        return transaction
