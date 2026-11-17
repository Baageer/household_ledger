"""PostgreSQL database foundation for the household ledger.

The domain services remain usable in memory for local tests.  When
``DATABASE_URL`` is configured, this module provides the production schema
and connection lifecycle used by the FastAPI application.
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Iterator, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


JsonType = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


class UserModel(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    unionid: Mapped[Optional[str]] = mapped_column(String(128))
    nickname: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    avatar: Mapped[str] = mapped_column(Text, default="", nullable=False)


class FamilyModel(TimestampMixin, Base):
    __tablename__ = "families"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)


class FamilyMemberModel(Base):
    __tablename__ = "family_members"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    nickname: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    __table_args__ = (UniqueConstraint("family_id", "user_id", name="uq_family_member"), Index("ix_family_members_user", "user_id", "status"))


class AccountModel(TimestampMixin, Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)


class CategoryModel(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("categories.id"))
    system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    __table_args__ = (UniqueConstraint("family_id", "name", name="uq_category_name"),)


class TransactionModel(TimestampMixin, Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    member_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    category_id: Mapped[Optional[str]] = mapped_column(ForeignKey("categories.id"))
    merchant: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    normalized_merchant: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    transaction_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    source_transaction_id: Mapped[Optional[str]] = mapped_column(String(200))
    transaction_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    transfer_to_account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("accounts.id"))
    linked_transaction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("transactions.id"))
    raw_data_ref: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(16), default="posted", nullable=False, index=True)
    __table_args__ = (
        UniqueConstraint("family_id", "transaction_hash", name="uq_transaction_hash"),
        Index("ix_transactions_family_time", "family_id", "transaction_time"),
        Index("ix_transactions_source_id", "family_id", "source", "account_id", "source_transaction_id"),
    )


class BudgetModel(TimestampMixin, Base):
    __tablename__ = "budgets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    __table_args__ = (UniqueConstraint("family_id", "category_id", name="uq_budget_category"),)


class ImportTaskModel(TimestampMixin, Base):
    __tablename__ = "import_tasks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("accounts.id"))
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(Text)
    file_checksum: Mapped[Optional[str]] = mapped_column(String(64))
    parser_version: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)


class ImportTransactionModel(Base):
    __tablename__ = "import_transactions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_task_id: Mapped[str] = mapped_column(ForeignKey("import_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JsonType, nullable=False)
    transaction_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    merchant: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    direction: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("accounts.id"))
    transfer_to_account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("accounts.id"))
    category_id: Mapped[Optional[str]] = mapped_column(ForeignKey("categories.id"))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_transaction_id: Mapped[Optional[str]] = mapped_column(String(200))
    transaction_hash: Mapped[Optional[str]] = mapped_column(String(64))
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    error_reason: Mapped[Optional[str]] = mapped_column(Text)
    transaction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("transactions.id"))


class SessionModel(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[Optional[str]] = mapped_column(ForeignKey("families.id", ondelete="SET NULL"))
    actor_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True)


class Database:
    """Connection and schema manager.

    ``DATABASE_URL`` should normally be a PostgreSQL URL such as
    ``postgresql+psycopg://ledger:secret@localhost:5432/ledger``.
    """

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv("DATABASE_URL")
        self.engine = create_engine(self.url, pool_pre_ping=True) if self.url else None
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False) if self.engine else None

    @property
    def configured(self) -> bool:
        return self.engine is not None

    def create_schema(self) -> None:
        if not self.engine:
            raise RuntimeError("DATABASE_URL is not configured")
        Base.metadata.create_all(self.engine)

    def check(self) -> bool:
        if not self.engine:
            return False
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def session(self) -> Iterator[Session]:
        if not self.session_factory:
            raise RuntimeError("DATABASE_URL is not configured")
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()


__all__ = ["Base", "Database", "UserModel", "FamilyModel", "FamilyMemberModel", "AccountModel", "CategoryModel", "TransactionModel", "BudgetModel", "ImportTaskModel", "ImportTransactionModel", "SessionModel", "AuditLogModel"]
