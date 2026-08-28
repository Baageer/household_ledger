"""FastAPI 最小联调服务，使用进程内领域服务存储数据。"""

from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ledger.family import FamilyService, PermissionDenied
from ledger.statistics import StatisticsService
from ledger.transactions import TransactionService

app = FastAPI(title="Household Ledger API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

families = FamilyService(openid_resolver=lambda code: {"openid": f"dev-{code}"})
transactions = TransactionService(families)
statistics = StatisticsService(families, transactions)
sessions: dict[str, str] = {}


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
    return {"status": "ok", "service": "household-ledger"}


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
