from datetime import datetime, timezone
from decimal import Decimal

from ledger.database import Database
from ledger.family import FamilyService
from ledger.imports import ImportService
from ledger.repository import LedgerRepository
from ledger.statistics import StatisticsService
from ledger.transactions import TransactionService


def build_services():
    families = FamilyService(openid_resolver=lambda code: {"openid": f"openid-{code}"})
    transactions = TransactionService(families)
    statistics = StatisticsService(families, transactions)
    imports = ImportService(families, transactions)
    return families, transactions, statistics, imports


def test_sqlite_repository_round_trip(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}"
    database = Database(url=database_url)
    database.create_schema()
    repository = LedgerRepository(database)

    families, transactions, statistics, imports = build_services()
    owner = families.wechat_login("owner")
    family = families.create_family(owner.id, "测试家庭")
    account = families.create_account(owner.id, family.id, "现金", "cash", initial_balance="100.00")
    shopping = next(category for category in transactions.list_categories(owner.id, family.id) if category.name == "购物")
    transaction_time = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    transaction = transactions.create_transaction(
        owner.id, family.id, "expense", "12.50", account.id,
        category_id=shopping.id, merchant="测试商户", transaction_time=transaction_time,
    )
    transactions.update_transaction(owner.id, family.id, transaction.id, category_id=shopping.id)
    budget = statistics.create_budget(owner.id, family.id, shopping.id, "500")
    sessions = {"token-key": owner.id}
    session_expiry = {"token-key": datetime(2026, 12, 1, tzinfo=timezone.utc)}

    repository.flush(families, transactions, statistics, imports, sessions=sessions, session_expiry=session_expiry)

    restored_families, restored_transactions, restored_statistics, restored_imports = build_services()
    restored_sessions: dict[str, str] = {}
    restored_expiry: dict[str, datetime] = {}
    restored_repository = LedgerRepository(Database(url=database_url))
    restored_repository.restore(
        restored_families, restored_transactions, restored_statistics, restored_imports,
        sessions=restored_sessions, session_expiry=restored_expiry,
    )

    restored_repository.flush(
        restored_families, restored_transactions, restored_statistics, restored_imports,
        sessions=restored_sessions, session_expiry=restored_expiry,
    )

    restored = restored_transactions.transactions[transaction.id]
    assert restored.merchant == "测试商户"
    assert restored.amount == Decimal("12.50")
    assert restored.category_id == shopping.id
    assert restored.transaction_time.replace(tzinfo=timezone.utc) == transaction_time
    assert restored_families.accounts[account.id].initial_balance == Decimal("100.00")
    assert restored_statistics.budgets[budget.id].amount == Decimal("500.00")

    assert restored_transactions.category_rules[family.id]["测试商户"] == shopping.id
    assert restored_transactions.match_category_rule(family.id, "测试商户(分店)") == shopping.id
    assert restored_sessions == sessions
    assert restored_expiry == session_expiry
    assert sum(1 for category in restored_transactions.categories.values() if category.family_id == "*" and category.name == "餐饮") == 1
