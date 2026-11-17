import base64

import pytest
from fastapi.testclient import TestClient

from main import app, families, sessions, transactions


@pytest.fixture(autouse=True)
def reset_state():
    families.users.clear(); families.users_by_openid.clear(); families.families.clear(); families.members.clear(); families.accounts.clear(); families.invitations.clear()
    transactions.transactions.clear()
    sessions.clear()
    yield
    sessions.clear()


@pytest.fixture
def client():
    return TestClient(app)


def login(client, code="owner"):
    response = client.post("/auth/wechat-login", json={"code": code, "nickname": code})
    assert response.status_code == 200
    return response.json()


def test_health_and_auth_context(client):
    assert client.get("/health").json()["status"] == "ok"
    session = login(client)
    assert session["user"]["nickname"] == "owner"
    assert session["families"] == []
    assert client.get("/families").status_code == 401


def test_family_account_transaction_and_statistics_flow(client):
    session = login(client)
    headers = {"Authorization": f"Bearer {session['token']}"}
    family = client.post("/families", headers=headers, json={"name": "家庭"}).json()
    headers["X-Family-Id"] = family["id"]
    account = client.post("/accounts", headers=headers, json={"name": "现金", "type": "cash", "initial_balance": "100.00"})
    assert account.status_code == 200
    transaction = client.post("/transactions", headers=headers, json={"type": "expense", "amount": "12.50", "account_id": account.json()["id"], "merchant": "早餐", "transaction_time": "2026-08-01T08:00:00+00:00"})
    assert transaction.status_code == 200
    assert transaction.json()["account_name"] == "现金"
    listed = client.get("/transactions", headers=headers)
    assert listed.json()["items"][0]["account_name"] == "现金"
    assert listed.json()["groups"][next(iter(listed.json()["groups"]))][0]["account_name"] == "现金"
    shopping = next(item for item in client.get("/categories", headers=headers).json() if item["name"] == "购物")
    updated = client.put(f"/transactions/{transaction.json()['id']}", headers=headers, json={"category_id": shopping["id"]})
    assert updated.status_code == 200
    assert updated.json()["category_name"] == "购物"
    target = client.post("/accounts", headers=headers, json={"name": "银行卡", "type": "bank"}).json()
    transfer = client.post("/transactions", headers=headers, json={"type": "transfer", "amount": "20", "account_id": account.json()["id"], "transfer_to_account_id": target["id"]})
    assert transfer.json()["account_name"] == "现金"
    assert transfer.json()["transfer_to_account_name"] == "银行卡"
    summary = client.get("/statistics/monthly?month=2026-08", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["expense"] == "12.50"


def test_family_header_and_invalid_account_are_rejected(client):
    session = login(client)
    headers = {"Authorization": f"Bearer {session['token']}"}
    family = client.post("/families", headers=headers, json={"name": "家庭"}).json()
    headers["X-Family-Id"] = family["id"]
    response = client.post("/transactions", headers=headers, json={"type": "expense", "amount": "1", "account_id": "missing"})
    assert response.status_code == 422
    assert client.get("/accounts", headers={"Authorization": headers["Authorization"]}).status_code == 400


def test_alipay_import_serializes_missing_csv_cells(client):
    session = login(client)
    headers = {"Authorization": f"Bearer {session['token']}"}
    family = client.post("/families", headers=headers, json={"name": "瀹跺涵"}).json()
    headers["X-Family-Id"] = family["id"]
    account = client.post("/accounts", headers=headers, json={"name": "支付宝", "type": "alipay"}).json()
    csv_text = "说明\n\n交易时间,交易对方,收/支,金额,交易单号,备注,\n2026-08-01 09:00,淘宝,支出,12.50,order-1,\n"
    payload = {
        "filename": "alipay.csv",
        "source": "alipay",
        "account_id": account["id"],
        "content": base64.b64encode(csv_text.encode("gb18030")).decode("ascii"),
    }
    response = client.post("/imports", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "reviewing"
    confirmed = client.post(f"/imports/{response.json()['id']}/confirm", headers=headers, json={})
    assert confirmed.json()["status"] == "completed"
    items = client.get("/transactions?month=2026-08", headers=headers).json()["items"]
    assert items[0]["category_name"] == "购物"
    assert items[0]["account_name"] == "支付宝"
