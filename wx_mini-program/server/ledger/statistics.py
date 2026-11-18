"""M3 统计、预算与首页聚合服务。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Optional
from uuid import uuid4

from .family import FamilyError, FamilyService, PermissionDenied
from .transactions import Transaction, TransactionService


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise FamilyError("预算金额必须是有效数字")
    if amount <= 0:
        raise FamilyError("预算金额必须大于 0")
    return amount


@dataclass
class Budget:
    id: str
    family_id: str
    category_id: str
    amount: Decimal
    status: str = "active"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


class StatisticsService:
    """提供 M3 查询和预算管理，数据源为进程内 M2 服务。"""

    def __init__(self, family_service: FamilyService, transaction_service: TransactionService):
        self.family_service = family_service
        self.transaction_service = transaction_service
        self.budgets: Dict[str, Budget] = {}

    def monthly_summary(self, actor_user_id: str, family_id: str, month: Optional[str] = None) -> dict:
        rows = self._visible_rows(actor_user_id, family_id, month)
        income = sum((row.amount for row in rows if row.type == "income"), Decimal("0.00"))
        expense = sum((row.amount for row in rows if row.type == "expense"), Decimal("0.00"))
        count = sum(1 for row in rows if row.type in ("income", "expense"))
        return {"month": month, "income": income, "expense": expense, "balance": income - expense, "count": count}

    def trend(self, actor_user_id: str, family_id: str, granularity: str = "day", month: Optional[str] = None) -> List[dict]:
        if granularity not in ("day", "week", "month"):
            raise FamilyError("趋势粒度只能是 day、week 或 month")
        rows = self._visible_rows(actor_user_id, family_id, month)
        grouped: Dict[str, Dict[str, Decimal]] = defaultdict(lambda: {"income": Decimal("0.00"), "expense": Decimal("0.00")})
        for row in rows:
            if granularity == "day":
                period = row.transaction_time.date().isoformat()
            elif granularity == "week":
                iso = row.transaction_time.isocalendar()
                period = f"{iso.year}-W{iso.week:02d}"
            else:
                period = row.transaction_time.strftime("%Y-%m")
            if row.type in ("income", "expense"):
                grouped[period][row.type] += row.amount
        return [{"period": period, **grouped[period]} for period in sorted(grouped)]

    def category_summary(self, actor_user_id: str, family_id: str, month: Optional[str] = None) -> List[dict]:
        rows = [row for row in self._visible_rows(actor_user_id, family_id, month) if row.type == "expense"]
        totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        counts: Dict[str, int] = defaultdict(int)
        for row in rows:
            key = row.category_id or "uncategorized"
            totals[key] += row.amount
            counts[key] += 1
        total = sum(totals.values(), Decimal("0.00"))
        result = []
        for category_id, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True):
            category = self.transaction_service.categories.get(category_id)
            result.append({
                "category_id": None if category_id == "uncategorized" else category_id,
                "category": category.name if category else "未分类",
                "amount": amount,
                "count": counts[category_id],
                "ratio": (amount / total).quantize(Decimal("0.0001")) if total else Decimal("0.0000"),
            })
        return result

    def member_summary(self, actor_user_id: str, family_id: str, month: Optional[str] = None) -> List[dict]:
        rows = [row for row in self._visible_rows(actor_user_id, family_id, month) if row.type == "expense"]
        totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for row in rows:
            account = self.family_service.accounts[row.account_id]
            key = "family" if account.owner_id is None else row.member_id
            totals[key] += row.amount
        result = []
        for member_id, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True):
            if member_id == "family":
                name = "家庭"
            else:
                user = self.family_service.users.get(member_id)
                name = user.nickname if user and user.nickname else member_id
            result.append({"member_id": None if member_id == "family" else member_id, "member": name, "amount": amount})
        return result

    def create_budget(self, actor_user_id: str, family_id: str, category_id: str, amount: object) -> Budget:
        self._require_manager(actor_user_id, family_id)
        self.transaction_service._require_category(category_id, family_id)
        budget = Budget(_id("budget"), family_id, category_id, _money(amount))
        self.budgets[budget.id] = budget
        return budget

    def update_budget(self, actor_user_id: str, family_id: str, budget_id: str, amount: object) -> Budget:
        self._require_manager(actor_user_id, family_id)
        budget = self._require_budget(budget_id, family_id)
        budget.amount = _money(amount)
        budget.updated_at = _now()
        return budget

    def disable_budget(self, actor_user_id: str, family_id: str, budget_id: str) -> Budget:
        self._require_manager(actor_user_id, family_id)
        budget = self._require_budget(budget_id, family_id)
        budget.status = "disabled"
        budget.updated_at = _now()
        return budget

    def list_budgets(self, actor_user_id: str, family_id: str, month: Optional[str] = None) -> List[dict]:
        self.family_service._require_member(actor_user_id, family_id)
        used_by_category = defaultdict(lambda: Decimal("0.00"))
        for row in self._visible_rows(actor_user_id, family_id, month):
            if row.type == "expense" and row.category_id:
                used_by_category[row.category_id] += row.amount
        result = []
        for budget in self.budgets.values():
            if budget.family_id != family_id or budget.status != "active":
                continue
            used = used_by_category[budget.category_id]
            remaining = budget.amount - used
            category = self.transaction_service.categories.get(budget.category_id)
            result.append({
                "id": budget.id, "category_id": budget.category_id,
                "category": category.name if category else "未分类",
                "budget": budget.amount, "used": used, "remaining": remaining,
                "usage_ratio": (used / budget.amount).quantize(Decimal("0.0001")),
                "over_budget": used > budget.amount,
            })
        return result

    def recent_transactions(self, actor_user_id: str, family_id: str, month: Optional[str] = None, limit: int = 5) -> List[dict]:
        rows = sorted(self._visible_rows(actor_user_id, family_id, month), key=lambda row: row.transaction_time, reverse=True)[:limit]
        result = []
        for row in rows:
            category = self.transaction_service.categories.get(row.category_id)
            account = self.family_service.accounts.get(row.account_id)
            result.append({
                "id": row.id, "type": row.type, "amount": row.amount,
                "merchant": row.merchant, "description": row.description,
                "category_id": row.category_id,
                "category": category.name if category else "未分类",
                "account_id": row.account_id,
                "account": account.name if account else "未指定账户",
                "transfer_to_account_id": row.transfer_to_account_id,
                "transaction_time": row.transaction_time,
                "status": row.status,
            })
        return result

    def home(self, actor_user_id: str, family_id: str, month: Optional[str] = None) -> dict:
        budgets = self.list_budgets(actor_user_id, family_id, month)
        total_budget = sum((item["budget"] for item in budgets), Decimal("0.00"))
        used_budget = sum((item["used"] for item in budgets), Decimal("0.00"))
        return {
            "summary": self.monthly_summary(actor_user_id, family_id, month),
            "trend": self.trend(actor_user_id, family_id, "day", month),
            "recent_transactions": self.recent_transactions(actor_user_id, family_id, month),
            "category_ranking": self.category_summary(actor_user_id, family_id, month)[:5],
            "member_ranking": self.member_summary(actor_user_id, family_id, month),
            "budgets": budgets,
            "budget_summary": {
                "count": len(budgets),
                "total": total_budget,
                "used": used_budget,
                "remaining": total_budget - used_budget,
                "usage_ratio": (used_budget / total_budget).quantize(Decimal("0.0001")) if total_budget else Decimal("0.0000"),
            },
            "quick_actions": ("expense", "income", "transfer"),
        }

    def _visible_rows(self, actor_user_id: str, family_id: str, month: Optional[str]) -> List[Transaction]:
        actor = self.family_service._require_member(actor_user_id, family_id)
        visible_accounts = {account.id for account in self.family_service.list_accounts(actor_user_id, family_id)}
        rows = [row for row in self.transaction_service.transactions.values() if row.family_id == family_id and row.status == "posted" and row.account_id in visible_accounts]
        if month:
            try:
                year, month_number = (int(item) for item in month.split("-", 1))
                rows = [row for row in rows if row.transaction_time.year == year and row.transaction_time.month == month_number]
            except (ValueError, TypeError):
                raise FamilyError("月份格式应为 YYYY-MM")
        return rows

    def _require_manager(self, actor_user_id: str, family_id: str) -> None:
        actor = self.family_service._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以管理预算")

    def _require_budget(self, budget_id: str, family_id: str) -> Budget:
        budget = self.budgets.get(budget_id)
        if not budget or budget.family_id != family_id:
            raise FamilyError("预算不存在")
        return budget
