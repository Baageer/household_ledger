"""ORM repository bridge for the existing domain services.

The domain objects remain the API-facing model.  This repository hydrates
them on startup and flushes mutations to PostgreSQL after requests, allowing
an incremental migration without duplicating business validation rules.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from decimal import Decimal
from typing import Any
from sqlalchemy import select

from .database import (
    AccountModel, AuditLogModel, BudgetModel, CategoryModel, Database,
    FamilyMemberModel, FamilyModel, ImportTaskModel, ImportTransactionModel,
    SessionModel, TransactionModel, UserModel,
)
from .family import Account, Family, FamilyMember, Invitation, User
from .imports import ImportTask, ImportTransaction
from .statistics import Budget
from .transactions import Category, Transaction


def _clean(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


class LedgerRepository:
    def __init__(self, database: Database):
        self.database = database

    def restore(self, families: Any, transactions: Any, statistics: Any, imports: Any) -> None:
        if not self.database.configured:
            return
        with self.database.session_factory() as session:
            for item in session.scalars(select(UserModel)):
                user = User(item.id, item.openid, item.unionid, item.nickname, item.avatar, item.created_at, item.updated_at)
                families.users[user.id] = user; families.users_by_openid[user.openid] = user.id
            for item in session.scalars(select(FamilyModel)):
                families.families[item.id] = Family(item.id, item.name, item.owner_id, item.created_at, item.updated_at)
            for item in session.scalars(select(FamilyMemberModel)):
                families.members[item.id] = FamilyMember(item.id, item.family_id, item.user_id, item.role, item.nickname, item.status, item.created_at)
            for item in session.scalars(select(AccountModel)):
                families.accounts[item.id] = Account(item.id, item.family_id, item.owner_id, item.name, item.type, item.currency, item.initial_balance, item.status, item.created_at, item.updated_at)
            for item in session.scalars(select(CategoryModel)):
                transactions.categories[item.id] = Category(item.id, item.family_id, item.name, item.parent_id, item.system, item.status, item.created_at)
            for item in session.scalars(select(TransactionModel)):
                transactions.transactions[item.id] = Transaction(item.id, item.family_id, item.account_id, item.member_id, item.type, item.amount, item.category_id, item.merchant, item.description, item.transaction_time, item.source, item.transfer_to_account_id, item.source_transaction_id, item.transaction_hash, item.normalized_merchant, item.linked_transaction_id, item.raw_data_ref, item.created_by, item.confidence, item.status, item.created_at, item.updated_at)
            for item in session.scalars(select(BudgetModel)):
                statistics.budgets[item.id] = Budget(item.id, item.family_id, item.category_id, item.amount, item.status, item.created_at, item.updated_at)
            for item in session.scalars(select(ImportTaskModel)):
                imports.tasks[item.id] = ImportTask(item.id, item.family_id, item.uploader_id, item.source, item.file_name, item.account_id, item.status, item.total_count, item.success_count, item.duplicate_count, item.error_count, item.created_at, item.finished_at, item.error_message)
            for item in session.scalars(select(ImportTransactionModel)):
                imports.rows[item.id] = ImportTransaction(
                    id=item.id, import_task_id=item.import_task_id, row_number=item.row_number, raw_data=item.raw_data,
                    transaction_time=item.transaction_time, merchant=item.merchant, amount=item.amount, direction=item.direction,
                    account_id=item.account_id, transfer_to_account_id=item.transfer_to_account_id, category_id=item.category_id,
                    description=item.description, source_transaction_id=item.source_transaction_id,
                    transaction_hash=item.transaction_hash or "", duplicate=item.duplicate,
                    confidence=float(item.confidence or 0), status=item.status,
                    error_reason=item.error_reason, transaction_id=item.transaction_id,
                )

    def flush(self, families: Any, transactions: Any, statistics: Any, imports: Any) -> None:
        if not self.database.configured:
            return
        with self.database.session_factory() as session:
            for item in families.users.values(): session.merge(UserModel(**asdict(item)))
            for item in families.families.values(): session.merge(FamilyModel(**asdict(item)))
            for item in families.members.values(): session.merge(FamilyMemberModel(**asdict(item)))
            for item in families.accounts.values(): session.merge(AccountModel(**asdict(item)))
            for item in transactions.categories.values(): session.merge(CategoryModel(**asdict(item)))
            for item in transactions.transactions.values(): session.merge(TransactionModel(**asdict(item)))
            for item in statistics.budgets.values(): session.merge(BudgetModel(**asdict(item)))
            for item in imports.tasks.values(): session.merge(ImportTaskModel(**asdict(item)))
            for item in imports.rows.values():
                data = _clean(asdict(item))
                session.merge(ImportTransactionModel(**data))
            session.commit()
