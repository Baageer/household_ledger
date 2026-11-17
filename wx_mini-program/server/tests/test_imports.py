from pathlib import Path

import pytest

from ledger.family import FamilyService, FamilyError
from ledger.imports import ImportService
from ledger.transactions import TransactionService


@pytest.fixture
def services(tmp_path):
    families = FamilyService(openid_resolver=lambda code: {"openid": code})
    transactions = TransactionService(families)
    imports = ImportService(families, transactions)
    owner = families.wechat_login("owner")
    family = families.create_family(owner.id, "家庭")
    account = families.create_account(owner.id, family.id, "支付宝", "alipay")
    path = Path(tmp_path) / "alipay.csv"
    path.write_text(
        "支付宝账单导出说明\n交易明细\n交易时间,交易对方,金额,收支,交易单号,备注\n"
        "2026-08-01 09:00,早餐,-12.50,支出,order-1,早餐\n"
        "2026-08-02 10:00,工资,5000,收入,salary-1,八月工资\n",
        encoding="gb18030",
    )
    return families, transactions, imports, owner, family, account, path


def test_alipay_import_preview_and_confirm_is_idempotent(services):
    families, transactions, imports, owner, family, account, path = services
    task = imports.create_task(owner.id, family.id, path, "alipay", account.id)
    preview = imports.preview(owner.id, task.id)
    assert task.status == "reviewing"
    assert preview["total"] == 2
    assert preview["expense_count"] == 1
    assert preview["income_count"] == 1
    assert all(row.account_id == account.id for row in preview["rows"])
    assert {transactions.categories[row.category_id].name for row in preview["rows"]} == {"其他", "收入-其他"}
    imports.confirm(owner.id, task.id)
    imports.confirm(owner.id, task.id)
    assert task.status == "completed"
    assert task.success_count == 2
    assert len(transactions.transactions) == 2
    assert all(transaction.account_id == account.id for transaction in transactions.transactions.values())


def test_import_duplicate_rows_are_not_posted_twice(services):
    _, transactions, imports, owner, family, account, path = services
    task = imports.create_task(owner.id, family.id, path, "alipay", account.id)
    imports.confirm(owner.id, task.id)
    imported = next(transaction for transaction in transactions.transactions.values() if transaction.source_transaction_id == "order-1")
    original_hash = imported.transaction_hash
    shopping = next(category for category in transactions.categories.values() if category.name == "购物")
    transactions.update_transaction(owner.id, family.id, imported.id, category_id=shopping.id)
    second = imports.create_task(owner.id, family.id, path, "alipay", account.id)
    assert second.duplicate_count == 2
    imports.confirm(owner.id, second.id)
    assert len(transactions.transactions) == 2
    assert imported.category_id == shopping.id
    assert imported.transaction_hash == original_hash


def test_import_category_backfill_updates_existing_uncategorized_rows(services):
    _, transactions, imports, owner, family, account, path = services
    task = imports.create_task(owner.id, family.id, path, "alipay", account.id)
    imports.confirm(owner.id, task.id)
    imported = next(iter(transactions.transactions.values()))
    imported.category_id = None
    assert imports.backfill_transaction_categories() == 1
    assert transactions.categories[imported.category_id].name == "其他"


def test_transfer_direction_distinguishes_internal_and_external_flows(services, tmp_path):
    families, transactions, imports, owner, family, account, _ = services
    bank = families.create_account(owner.id, family.id, "招商银行", "bank")
    path = tmp_path / "transfer-flows.csv"
    path.write_text(
        "交易时间,交易对方,金额,收支,交易单号,备注\n"
        "2026-08-03 09:00,招商银行,-100,转出,transfer-1,转到招商银行\n"
        "2026-08-03 10:00,招商银行,50,转入,transfer-2,从招商银行转入\n"
        "2026-08-04 09:00,客户A,200,转入,income-1,外部收款\n"
        "2026-08-05 09:00,客户B,-30,转出,expense-1,外部付款\n",
        encoding="utf-8",
    )
    task = imports.create_task(owner.id, family.id, path, "alipay", account.id)
    preview = imports.preview(owner.id, task.id)
    assert preview["transfer_count"] == 2
    assert preview["income_count"] == 1
    assert preview["expense_count"] == 1
    transfer_rows = [row for row in preview["rows"] if row.direction == "transfer"]
    assert {(row.account_id, row.transfer_to_account_id) for row in transfer_rows} == {
        (account.id, bank.id),
        (bank.id, account.id),
    }
    imports.confirm(owner.id, task.id)
    posted = list(transactions.transactions.values())
    transfers = [transaction for transaction in posted if transaction.type == "transfer"]
    assert {(transaction.account_id, transaction.transfer_to_account_id) for transaction in transfers} == {
        (account.id, bank.id),
        (bank.id, account.id),
    }
    assert transactions.summary(owner.id, family.id, "2026-08") == {
        "income": 200,
        "expense": 30,
        "balance": 170,
    }


def test_invalid_file_and_unsupported_source_are_rejected(services, tmp_path):
    families, _, imports, owner, family, account, _ = services
    with pytest.raises(FamilyError):
        imports.create_task(owner.id, family.id, tmp_path / "missing.csv", "alipay", account.id)
    path = tmp_path / "bad.txt"
    path.write_text("data", encoding="utf-8")
    with pytest.raises(FamilyError):
        imports.create_task(owner.id, family.id, path, "bank", account.id)
