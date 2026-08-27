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
    imports.confirm(owner.id, task.id)
    imports.confirm(owner.id, task.id)
    assert task.status == "completed"
    assert task.success_count == 2
    assert len(transactions.transactions) == 2


def test_import_duplicate_rows_are_not_posted_twice(services):
    _, transactions, imports, owner, family, account, path = services
    task = imports.create_task(owner.id, family.id, path, "alipay", account.id)
    imports.confirm(owner.id, task.id)
    second = imports.create_task(owner.id, family.id, path, "alipay", account.id)
    assert second.duplicate_count == 2
    imports.confirm(owner.id, second.id)
    assert len(transactions.transactions) == 2


def test_invalid_file_and_unsupported_source_are_rejected(services, tmp_path):
    families, _, imports, owner, family, account, _ = services
    with pytest.raises(FamilyError):
        imports.create_task(owner.id, family.id, tmp_path / "missing.csv", "alipay", account.id)
    path = tmp_path / "bad.txt"
    path.write_text("data", encoding="utf-8")
    with pytest.raises(FamilyError):
        imports.create_task(owner.id, family.id, path, "bank", account.id)
