from datetime import datetime, timezone
from decimal import Decimal

import pytest

from ledger.family import FamilyError, FamilyService, PermissionDenied
from ledger.transactions import TransactionService


@pytest.fixture
def services():
    families = FamilyService(openid_resolver=lambda code: {"openid": "wx-" + code})
    ledger = TransactionService(families)
    owner = families.wechat_login("owner")
    member = families.wechat_login("member")
    family = families.create_family(owner.id, "家庭")
    families.invite_member(owner.id, family.id, member.id)
    cash = families.create_account(owner.id, family.id, "家庭现金", "cash")
    private = families.create_account(owner.id, family.id, "微信", "wechat", owner_id=owner.id)
    return families, ledger, owner, member, family, cash, private


def test_manual_income_expense_and_transfer_summary(services):
    _, ledger, owner, _, family, cash, private = services
    meal = ledger.create_transaction(owner.id, family.id, "expense", "56.005", private.id, merchant="外卖")
    salary = ledger.create_transaction(owner.id, family.id, "income", 10000, cash.id, category_id=None)
    transfer = ledger.create_transaction(owner.id, family.id, "transfer", 500, cash.id, transfer_to_account_id=private.id)
    assert meal.amount == Decimal("56.01")
    assert transfer.category_id is None
    assert ledger.summary(owner.id, family.id) == {"income": Decimal("10000.00"), "expense": Decimal("56.01"), "balance": Decimal("9943.99")}


def test_member_can_only_edit_own_transaction_and_deleted_rows_are_hidden(services):
    _, ledger, owner, member, family, cash, _ = services
    mine = ledger.create_transaction(member.id, family.id, "expense", 10, cash.id)
    theirs = ledger.create_transaction(owner.id, family.id, "expense", 20, cash.id)
    ledger.update_transaction(member.id, family.id, mine.id, amount=12)
    with pytest.raises(PermissionDenied):
        ledger.update_transaction(member.id, family.id, theirs.id, amount=1)
    ledger.delete_transaction(member.id, family.id, mine.id)
    assert ledger.list_transactions(member.id, family.id)["total"] == 1


def test_transaction_list_supports_month_date_groups_and_pagination(services):
    _, ledger, owner, _, family, cash, _ = services
    ledger.create_transaction(owner.id, family.id, "expense", 10, cash.id, transaction_time=datetime(2026, 8, 2, tzinfo=timezone.utc))
    ledger.create_transaction(owner.id, family.id, "expense", 20, cash.id, transaction_time=datetime(2026, 8, 1, tzinfo=timezone.utc))
    ledger.create_transaction(owner.id, family.id, "expense", 30, cash.id, transaction_time=datetime(2026, 7, 31, tzinfo=timezone.utc))
    result = ledger.list_transactions(owner.id, family.id, month="2026-08", page=1, page_size=1)
    assert result["total"] == 2
    assert list(result["groups"]) == ["2026-08-02"]


def test_category_cannot_be_deleted_after_transaction_reference(services):
    _, ledger, owner, _, family, cash, _ = services
    category = ledger.create_category(owner.id, family.id, "宠物")
    ledger.create_transaction(owner.id, family.id, "expense", 50, cash.id, category_id=category.id)
    with pytest.raises(FamilyError):
        ledger.delete_category(owner.id, family.id, category.id)
    with pytest.raises(FamilyError):
        ledger.delete_category(owner.id, family.id, ledger.list_categories(owner.id, family.id)[0].id)


def test_source_id_and_fingerprint_are_idempotent(services):
    _, ledger, owner, _, family, cash, _ = services
    first = ledger.create_transaction(owner.id, family.id, "expense", 18, cash.id, source="wechat", source_transaction_id="wx-1", merchant="便利店")
    same_source = ledger.create_transaction(owner.id, family.id, "expense", 99, cash.id, source="wechat", source_transaction_id="wx-1", merchant="不同名称")
    same_fingerprint = ledger.create_transaction(owner.id, family.id, "expense", 18, cash.id, source="wechat", merchant="便利店", transaction_time=first.transaction_time)
    assert same_source.id == first.id
    assert same_fingerprint.id == first.id
    assert len(ledger.transactions) == 1


def test_transfer_candidates_and_refund_link(services):
    _, ledger, owner, _, family, cash, private = services
    transfer = ledger.create_transaction(owner.id, family.id, "transfer", 500, cash.id, transfer_to_account_id=private.id)
    candidates = ledger.find_transfer_candidates(owner.id, family.id, private.id, 500, transfer.transaction_time)
    assert candidates == [transfer]
    expense = ledger.create_transaction(owner.id, family.id, "expense", 80, private.id)
    refund = ledger.create_transaction(owner.id, family.id, "refund", 30, private.id, linked_transaction_id=expense.id)
    assert refund.linked_transaction_id == expense.id
    assert ledger.summary(owner.id, family.id)["income"] == Decimal("0.00")


def test_merchant_normalization_is_recorded(services):
    _, ledger, owner, _, family, cash, _ = services
    ledger.merchant_rules["美团外卖"] = "美团"
    transaction = ledger.create_transaction(owner.id, family.id, "expense", 56, cash.id, merchant="美团外卖")
    assert transaction.normalized_merchant == "美团"


def test_category_update_learns_merchant_rule(services):
    _, ledger, owner, _, family, cash, _ = services
    shopping = next(category for category in ledger.categories.values() if category.name == "购物")
    transaction = ledger.create_transaction(owner.id, family.id, "expense", 30, cash.id, merchant="小王家早餐铺")
    ledger.update_transaction(owner.id, family.id, transaction.id, category_id=shopping.id)
    assert ledger.match_category_rule(family.id, "小王家早餐铺") == shopping.id
    assert ledger.match_category_rule(family.id, "小王家早餐铺(分店)") == shopping.id
    assert ledger.match_category_rule(family.id, "其他商户") is None
