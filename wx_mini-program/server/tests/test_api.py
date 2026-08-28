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
    transaction = client.post("/transactions", headers=headers, json={"type": "expense", "amount": "12.50", "account_id": account.json()["id"], "merchant": "早餐"})
    assert transaction.status_code == 200
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
