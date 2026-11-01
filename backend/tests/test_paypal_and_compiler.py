from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.engines.policy import fmt
from app.services.parsing import parse_amount
from app.services.paypal import PaymentError, PayPalProvider, set_payment_provider
from app.services.policy_compiler import compile_policy
from tests.factories import policy

# ---------------- PayPal provider (real HTTP shapes, mocked transport)


def paypal_transport(fail_capture: bool = False, auth_ok: bool = True) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.url.path == "/v1/oauth2/token":
            if not auth_ok:
                return httpx.Response(401, json={"error": "invalid_client"})
            return httpx.Response(200, json={"access_token": "A21AA", "expires_in": 32400})
        if req.url.path == "/v2/checkout/orders" and req.method == "POST":
            body = json.loads(req.content)
            assert body["intent"] == "CAPTURE"
            return httpx.Response(201, json={
                "id": "5O190127TN364715T", "status": "CREATED",
                "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=5O190127TN364715T"}],
            })
        if req.url.path.endswith("/capture"):
            if fail_capture:
                return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_NOT_APPROVED"}]})
            return httpx.Response(201, json={
                "id": "5O190127TN364715T", "status": "COMPLETED",
                "purchase_units": [{"payments": {"captures": [{"id": "3C679366HH908993F", "status": "COMPLETED"}]}}],
            })
        if req.method == "GET":
            return httpx.Response(200, json={"id": req.url.path.rsplit("/", 1)[-1], "status": "APPROVED"})
        return httpx.Response(404)

    return httpx.MockTransport(handler), calls


def settings() -> Settings:
    return Settings(paypal_client_id="cid", paypal_client_secret="secret", paypal_environment="sandbox")


def test_paypal_create_and_capture_order() -> None:
    transport, calls = paypal_transport()
    p = PayPalProvider(settings(), transport=transport)
    order = p.create_order(reference_id="PP-1", trace_id="tr_1", description="Hotel", amount=Decimal("94.05"), currency="USD")
    assert order.order_id == "5O190127TN364715T"
    assert order.approve_url and "sandbox.paypal.com" in order.approve_url
    assert order.simulated is False
    create = next(c for c in calls if c.url.path == "/v2/checkout/orders")
    assert create.headers["PayPal-Request-Id"] == "PP-1-create"
    assert json.loads(create.content)["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "94.05"}

    cap = p.capture_order(order.order_id, idempotency_key="PP-1-capture")
    assert cap.status == "COMPLETED"
    assert cap.capture_id == "3C679366HH908993F"
    # Token is cached across calls.
    assert sum(1 for c in calls if c.url.path == "/v1/oauth2/token") == 1


def test_paypal_capture_failure_raises() -> None:
    transport, _ = paypal_transport(fail_capture=True)
    p = PayPalProvider(settings(), transport=transport)
    with pytest.raises(PaymentError) as exc:
        p.capture_order("X", idempotency_key="k")
    assert "ORDER_NOT_APPROVED" in str(exc.value)
    assert exc.value.retryable is False


def test_paypal_bad_credentials() -> None:
    transport, _ = paypal_transport(auth_ok=False)
    p = PayPalProvider(settings(), transport=transport)
    assert p.check_connection() is False


def test_live_paypal_flow_waits_for_buyer_then_captures(client: TestClient) -> None:
    transport, _ = paypal_transport()
    set_payment_provider(PayPalProvider(settings(), transport=transport))
    tx = client.post("/api/demo/run", json={"scenario": "safe_purchase"}).json()
    # Real PayPal needs buyer approval, so we never fake completion.
    assert tx["status"] == "PAYMENT_CREATED"
    assert tx["payment_provider"] == "paypal"
    assert tx["paypal_order_id"] == "5O190127TN364715T"
    assert tx["settlement_currency"] == "USD"
    assert tx["settlement_amount"] == pytest.approx(94.05)

    bad = client.post("/api/paypal/capture-order", json={"transaction_id": tx["id"], "order_id": "SOMEONE-ELSES"})
    assert bad.status_code == 409

    done = client.post("/api/paypal/capture-order", json={"transaction_id": tx["id"], "order_id": tx["paypal_order_id"]}).json()
    assert done["status"] == "COMPLETED"
    assert done["paypal_capture_id"] == "3C679366HH908993F"
    # Capturing again is idempotent.
    again = client.post("/api/payments/capture-order", json={"transaction_id": tx["id"], "order_id": tx["paypal_order_id"]})
    assert again.status_code == 200


def test_paypal_unapproved_capture_keeps_order_open(client: TestClient) -> None:
    transport, _ = paypal_transport(fail_capture=True)
    set_payment_provider(PayPalProvider(settings(), transport=transport))
    tx = client.post("/api/demo/run", json={"scenario": "safe_purchase"}).json()
    r = client.post("/api/paypal/capture-order", json={"transaction_id": tx["id"], "order_id": tx["paypal_order_id"]}).json()
    assert r["status"] == "PAYMENT_CREATED"
    assert "not approved" in r["failure_reason"]


# ---------------- Natural language policy compiler


def test_compiler_parses_spec_example() -> None:
    r = compile_policy(
        "You can spend up to ₹20,000 per transaction. Anything above ₹10,000 needs my approval. Never use suspicious merchants.",
        policy(max_transaction_amount=Decimal("50000"), require_approval_above=Decimal("25000"), daily_spending_limit=Decimal("100000"),
               monthly_spending_limit=Decimal("500000"), minimum_merchant_trust=60),
    )
    assert r.valid, r.errors
    assert r.source == "rules"
    assert r.policy is not None
    assert r.policy.max_transaction_amount == Decimal("20000")
    assert r.policy.require_approval_above == Decimal("10000")
    assert r.policy.minimum_merchant_trust == 80


def test_compiler_handles_daily_limits_categories_and_lakhs() -> None:
    r = compile_policy("Max ₹1.5 lakh per purchase. Daily limit ₹2,00,000. Never buy gift cards or crypto. No international payments.",
                       policy(monthly_spending_limit=Decimal("1000000")))
    assert r.policy is not None
    assert r.policy.max_transaction_amount == Decimal("150000")
    assert r.policy.daily_spending_limit == Decimal("200000")
    assert {"gift_cards", "crypto"} <= set(r.policy.blocked_categories)
    assert r.policy.allow_international is False


def test_compiler_reports_invalid_policy() -> None:
    r = compile_policy("Daily limit ₹50,000. Monthly limit ₹10,000.", policy())
    assert r.valid is False
    assert r.errors


def test_compiler_endpoint(client: TestClient) -> None:
    r = client.post("/api/policies/compile", json={"instruction": "Anything above ₹5,000 needs my approval", "policy_id": "pol_travel"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["changes"][0]["display"] == "₹5,000"


@pytest.mark.parametrize(
    "text,expected",
    [("₹1,20,000", Decimal("120000")), ("20k", Decimal("20000")), ("$1,500.50", Decimal("1500.50")), ("Rs. 7900", Decimal("7900"))],
)
def test_amount_parsing(text: str, expected: Decimal) -> None:
    parsed = parse_amount(text)
    assert parsed and parsed[0] == expected


def test_fmt_usd() -> None:
    assert fmt(Decimal("1500"), "USD") == "$1,500"
