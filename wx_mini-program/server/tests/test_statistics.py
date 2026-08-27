from datetime import datetime, timezone
from decimal import Decimal

import pytest

from ledger.family import FamilyService, PermissionDenied
from ledger.statistics import StatisticsService
from ledger.transactions import TransactionService


@pytest.fixture
def services():
    families = FamilyService(openid_resolver=lambda code: {"openid": code})
    transactions = TransactionService(families)
    stats = StatisticsService(families, transactions)
    owner = families.wechat_login("owner", nickname="妈妈")
    member = families.wechat_login("member", nickname="爸爸")
    family = families.create_family(owner.id, "家庭")
    families.invite_member(owner.id, family.id, member.id)
    public = families.create_account(owner.id, family.id, "家庭现金", "cash")
    private = families.create_account(owner.id, family.id, "微信", "wechat", owner_id=owner.id)
    category = transactions.list_categories(owner.id, family.id)[0]
    return families, transactions, stats, owner, member, family, public, private, category


def test_monthly_category_member_and_home_statistics(services):
    _, ledger, stats, owner, member, family, public, private, category = services
    ledger.create_transaction(owner.id, family.id, "income", 1000, public.id, transaction_time=datetime(2026, 8, 1, tzinfo=timezone.utc))
    ledger.create_transaction(owner.id, family.id, "expense", 100, private.id, category_id=category.id, transaction_time=datetime(2026, 8, 2, tzinfo=timezone.utc))
    ledger.create_transaction(member.id, family.id, "expense", 40, public.id, category_id=category.id, transaction_time=datetime(2026, 8, 3, tzinfo=timezone.utc))
    summary = stats.monthly_summary(owner.id, family.id, "2026-08")
    assert summary["income"] == Decimal("1000.00")
    assert summary["expense"] == Decimal("140.00")
    assert summary["balance"] == Decimal("860.00")
    assert stats.category_summary(owner.id, family.id, "2026-08")[0]["ratio"] == Decimal("1.0000")
    assert stats.member_summary(owner.id, family.id, "2026-08")[0]["amount"] == Decimal("100.00")
    home = stats.home(owner.id, family.id, "2026-08")
    assert home["summary"]["expense"] == Decimal("140.00")
    assert home["quick_actions"] == ("expense", "income", "transfer")


def test_trend_supports_day_week_month_and_invalid_granularity(services):
    _, ledger, stats, owner, _, family, public, _, category = services
    ledger.create_transaction(owner.id, family.id, "expense", 10, public.id, category_id=category.id, transaction_time=datetime(2026, 8, 3, tzinfo=timezone.utc))
    ledger.create_transaction(owner.id, family.id, "expense", 20, public.id, category_id=category.id, transaction_time=datetime(2026, 8, 10, tzinfo=timezone.utc))
    assert len(stats.trend(owner.id, family.id, "day", "2026-08")) == 2
    assert len(stats.trend(owner.id, family.id, "week", "2026-08")) == 2
    assert len(stats.trend(owner.id, family.id, "month", "2026-08")) == 1
    with pytest.raises(ValueError):
        stats.trend(owner.id, family.id, "year", "2026-08")


def test_budget_usage_update_disable_and_member_permission(services):
    _, ledger, stats, owner, member, family, public, _, category = services
    budget = stats.create_budget(owner.id, family.id, category.id, "100.005")
    ledger.create_transaction(member.id, family.id, "expense", 80, public.id, category_id=category.id)
    listed = stats.list_budgets(member.id, family.id)
    assert listed[0]["used"] == Decimal("80.00")
    assert listed[0]["remaining"] == Decimal("20.01")
    ledger.create_transaction(member.id, family.id, "expense", 30, public.id, category_id=category.id)
    assert stats.list_budgets(owner.id, family.id)[0]["over_budget"] is True
    with pytest.raises(PermissionDenied):
        stats.update_budget(member.id, family.id, budget.id, 200)
    stats.disable_budget(owner.id, family.id, budget.id)
    assert stats.list_budgets(owner.id, family.id) == []
