"""FastAPI 最小联调服务，使用进程内领域服务存储数据。"""

from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
import math
from pathlib import Path
from typing import Optional
from uuid import uuid4
import base64
import tempfile
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ledger.family import FamilyService, PermissionDenied
from ledger.statistics import StatisticsService
from ledger.transactions import TransactionService
from ledger.imports import ImportService
from ledger.database import Database
from ledger.repository import LedgerRepository

app = FastAPI(title="Household Ledger API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

families = FamilyService(openid_resolver=lambda code: {"openid": f"dev-{code}"})
transactions = TransactionService(families)
statistics = StatisticsService(families, transactions)
imports = ImportService(families, transactions)
database = Database()
repository = LedgerRepository(database)
sessions: dict[str, str] = {}


@app.on_event("startup")
def initialize_database() -> None:
    if database.configured and os.getenv("AUTO_CREATE_DB", "false").lower() in ("1", "true", "yes"):
        database.create_schema()
    if database.configured:
        try:
            repository.restore(families, transactions, statistics, imports)
        except Exception as error:
            raise RuntimeError("Unable to restore ledger state from PostgreSQL") from error


@app.middleware("http")
async def persist_domain_state(request, call_next):
    response = await call_next(request)
    if database.configured:
        try:
            repository.flush(families, transactions, statistics, imports)
        except Exception as error:
            raise RuntimeError("Unable to persist ledger state to PostgreSQL") from error
    return response


class LoginRequest(BaseModel):
    code: str = Field(min_length=1)
    nickname: str = ""
    avatar: str = ""


class FamilyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: str
    owner_id: Optional[str] = None
    currency: str = "CNY"
    initial_balance: str = "0.00"


class MemberInviteRequest(BaseModel):
    invitee_openid: str = Field(min_length=1)
    role: str = "member"


class MemberRoleRequest(BaseModel):
    role: str


class TransactionRequest(BaseModel):
    type: str
    amount: str
    account_id: str
    category_id: Optional[str] = None
    member_id: Optional[str] = None
    merchant: str = ""
    description: str = ""
    transaction_time: Optional[datetime] = None
    transfer_to_account_id: Optional[str] = None

class CategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    parent_id: Optional[str] = None

class BudgetRequest(BaseModel):
    category_id: str
    amount: str

class ImportRequest(BaseModel):
    filename: str
    source: str
    account_id: Optional[str] = None
    content: str


def jsonable(value):
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def current_user(authorization: Optional[str] = Header(default=None)) -> str:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    user_id = sessions.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user_id


def family_id(x_family_id: Optional[str] = Header(default=None, alias="X-Family-Id")) -> str:
    if not x_family_id:
        raise HTTPException(status_code=400, detail="缺少家庭上下文")
    return x_family_id


def domain_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionDenied):
        return HTTPException(status_code=403, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@app.get("/health")
def health():
    result = {"status": "ok", "service": "household-ledger", "database": "not_configured"}
    if database.configured:
        try:
            result["database"] = "ok" if database.check() else "unavailable"
        except Exception:
            result["database"] = "error"
    return result


@app.get("/health/database")
def database_health():
    if not database.configured:
        return {"configured": False, "status": "not_configured"}
    try:
        database.check()
        return {"configured": True, "status": "ok"}
    except Exception:
        return {"configured": True, "status": "error"}


@app.post("/auth/wechat-login")
def wechat_login(payload: LoginRequest):
    try:
        user = families.wechat_login(payload.code, payload.nickname, payload.avatar)
        token = uuid4().hex
        sessions[token] = user.id
        user_families = families.list_families(user.id)
        current = user_families[0].id if user_families else None
        return jsonable({"token": token, "user": user, "families": user_families, "currentFamilyId": current})
    except Exception as error:
        raise domain_error(error)


@app.get("/families")
def list_families(user_id: str = Depends(current_user)):
    return jsonable(families.list_families(user_id))


@app.post("/families")
def create_family(payload: FamilyRequest, user_id: str = Depends(current_user)):
    try:
        return jsonable(families.create_family(user_id, payload.name))
    except Exception as error:
        raise domain_error(error)


@app.get("/families/{family_id}/members")
def list_members(family_id: str, user_id: str = Depends(current_user)):
    try:
        members = families.list_members(user_id, family_id)
        return jsonable([{**asdict(member), "user": asdict(families.users.get(member.user_id)) if families.users.get(member.user_id) else None} for member in members])
    except Exception as error:
        raise domain_error(error)


@app.post("/families/{family_id}/invitations")
def create_invitation(family_id: str, payload: MemberInviteRequest, user_id: str = Depends(current_user)):
    try:
        return jsonable(families.create_invitation(user_id, family_id, payload.invitee_openid, payload.role))
    except Exception as error:
        raise domain_error(error)


@app.post("/invitations/{token}/accept")
def accept_invitation(token: str, user_id: str = Depends(current_user)):
    try:
        return jsonable(families.accept_invitation(user_id, token))
    except Exception as error:
        raise domain_error(error)


@app.put("/families/{family_id}/members/{member_user_id}")
def update_member_role(family_id: str, member_user_id: str, payload: MemberRoleRequest, user_id: str = Depends(current_user)):
    try:
        return jsonable(families.set_member_role(user_id, family_id, member_user_id, payload.role))
    except Exception as error:
        raise domain_error(error)


@app.delete("/families/{family_id}/members/{member_user_id}")
def disable_member(family_id: str, member_user_id: str, user_id: str = Depends(current_user)):
    try:
        return jsonable(families.disable_member(user_id, family_id, member_user_id))
    except Exception as error:
        raise domain_error(error)


@app.get("/accounts")
def list_accounts(user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(families.list_accounts(user_id, current_family))
    except Exception as error:
        raise domain_error(error)


@app.post("/accounts")
def create_account(payload: AccountRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(families.create_account(user_id, current_family, payload.name, payload.type, payload.owner_id, payload.currency, payload.initial_balance))
    except Exception as error:
        raise domain_error(error)


@app.put("/accounts/{account_id}")
def update_account(account_id: str, payload: AccountRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(families.update_account(user_id, current_family, account_id, payload.name, payload.owner_id, payload.currency))
    except Exception as error:
        raise domain_error(error)


@app.delete("/accounts/{account_id}")
def disable_account(account_id: str, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(families.disable_account(user_id, current_family, account_id))
    except Exception as error:
        raise domain_error(error)


@app.get("/transactions")
def list_transactions(month: Optional[str] = Query(default=None), page: int = 1, page_size: int = 20, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(transactions.list_transactions(user_id, current_family, month, page, page_size))
    except Exception as error:
        raise domain_error(error)


@app.post("/transactions")
def create_transaction(payload: TransactionRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(transactions.create_transaction(user_id, current_family, payload.type, payload.amount, payload.account_id, payload.category_id, payload.member_id, payload.merchant, payload.description, payload.transaction_time, payload.transfer_to_account_id))
    except Exception as error:
        raise domain_error(error)

@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(transactions._require_transaction(transaction_id, current_family))
    except Exception as error: raise domain_error(error)

@app.put("/transactions/{transaction_id}")
def update_transaction(transaction_id: str, payload: TransactionRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(transactions.update_transaction(user_id, current_family, transaction_id, amount=payload.amount, category_id=payload.category_id, merchant=payload.merchant, description=payload.description, transaction_time=payload.transaction_time))
    except Exception as error: raise domain_error(error)

@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: str, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(transactions.delete_transaction(user_id, current_family, transaction_id))
    except Exception as error: raise domain_error(error)

@app.get("/categories")
def list_categories(user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(transactions.list_categories(user_id, current_family))
    except Exception as error: raise domain_error(error)

@app.post("/categories")
def create_category(payload: CategoryRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(transactions.create_category(user_id, current_family, payload.name, payload.parent_id))
    except Exception as error: raise domain_error(error)

@app.delete("/categories/{category_id}")
def delete_category(category_id: str, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(transactions.delete_category(user_id, current_family, category_id))
    except Exception as error: raise domain_error(error)

@app.get("/budgets")
def list_budgets(month: Optional[str] = Query(default=None), user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(statistics.list_budgets(user_id, current_family, month))
    except Exception as error: raise domain_error(error)

@app.post("/budgets")
def create_budget(payload: BudgetRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(statistics.create_budget(user_id, current_family, payload.category_id, payload.amount))
    except Exception as error: raise domain_error(error)

@app.put("/budgets/{budget_id}")
def update_budget(budget_id: str, payload: BudgetRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(statistics.update_budget(user_id, current_family, budget_id, payload.amount))
    except Exception as error: raise domain_error(error)

@app.delete("/budgets/{budget_id}")
def delete_budget(budget_id: str, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try: return jsonable(statistics.disable_budget(user_id, current_family, budget_id))
    except Exception as error: raise domain_error(error)

@app.post("/imports")
def create_import(payload: ImportRequest, user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        suffix = Path(payload.filename).suffix or '.csv'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(base64.b64decode(payload.content))
            path = Path(handle.name)
        task = imports.create_task(user_id, current_family, path, payload.source, payload.account_id)
        task.file_name = payload.filename
        return jsonable(task)
    except Exception as error: raise domain_error(error)

@app.get("/imports/{task_id}")
def preview_import(task_id: str, user_id: str = Depends(current_user)):
    try: return jsonable(imports.preview(user_id, task_id))
    except Exception as error: raise domain_error(error)

class ImportConfirmRequest(BaseModel):
    row_ids: Optional[list[str]] = None

class ImportRowUpdate(BaseModel):
    merchant: Optional[str] = None
    amount: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None

@app.post("/imports/{task_id}/confirm")
def confirm_import(task_id: str, payload: ImportConfirmRequest = ImportConfirmRequest(), user_id: str = Depends(current_user)):
    try: return jsonable(imports.confirm(user_id, task_id, payload.row_ids))
    except Exception as error: raise domain_error(error)

@app.put("/imports/{task_id}/rows/{row_id}")
def update_import_row(task_id: str, row_id: str, payload: ImportRowUpdate, user_id: str = Depends(current_user)):
    try:
        task = imports._require_task(task_id); families._require_member(user_id, task.family_id)
        row = imports.rows.get(row_id)
        if not row or row.import_task_id != task_id: raise ValueError("导入明细不存在")
        if payload.merchant is not None: row.merchant = payload.merchant.strip()
        if payload.amount is not None: row.amount = abs(imports._parse_amount(payload.amount))
        if payload.description is not None: row.description = payload.description.strip()
        if payload.category_id is not None: row.category_id = payload.category_id
        if row.error_reason and row.amount and row.merchant: row.error_reason = None; row.status = "pending"
        return jsonable(row)
    except Exception as error: raise domain_error(error)

@app.post("/imports/{task_id}/retry")
def retry_import(task_id: str, user_id: str = Depends(current_user)):
    try: return jsonable(imports.retry(user_id, task_id))
    except Exception as error: raise domain_error(error)


@app.get("/statistics/home")
def home(month: Optional[str] = Query(default=None), user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(statistics.home(user_id, current_family, month))
    except Exception as error:
        raise domain_error(error)


@app.get("/statistics/monthly")
def monthly(month: Optional[str] = Query(default=None), user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(statistics.monthly_summary(user_id, current_family, month))
    except Exception as error:
        raise domain_error(error)


@app.get("/statistics/trend")
def trend(granularity: str = "day", month: Optional[str] = Query(default=None), user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(statistics.trend(user_id, current_family, granularity, month))
    except Exception as error:
        raise domain_error(error)


@app.get("/statistics/category")
def category(month: Optional[str] = Query(default=None), user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(statistics.category_summary(user_id, current_family, month))
    except Exception as error:
        raise domain_error(error)


@app.get("/statistics/members")
def members(month: Optional[str] = Query(default=None), user_id: str = Depends(current_user), current_family: str = Depends(family_id)):
    try:
        return jsonable(statistics.member_summary(user_id, current_family, month))
    except Exception as error:
        raise domain_error(error)
