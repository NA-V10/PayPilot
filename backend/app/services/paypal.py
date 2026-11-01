"""Payment execution via PayPal Orders v2.

Two providers share one interface:
  * PayPalProvider: real PayPal REST API (sandbox or live). Used whenever credentials exist.
  * SimulatedProvider: used only when credentials are absent. Every order id is prefixed
    `SIM-` and every response is marked `simulated: true`, so a simulated payment can never
    be mistaken for a real one.

The client secret stays server-side. The frontend only ever sees the public client id.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger("paypal")


class PaymentError(RuntimeError):
    """A payment provider failure. `retryable` hints whether the user should try again."""

    def __init__(self, message: str, *, retryable: bool = True, details: Any = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.details = details


@dataclass
class OrderResult:
    order_id: str
    status: str
    approve_url: str | None
    simulated: bool
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaptureResult:
    order_id: str
    status: str
    capture_id: str | None
    simulated: bool
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(Protocol):
    mode: str  # "paypal" | "simulated"

    def create_order(self, *, reference_id: str, trace_id: str, description: str, amount: Decimal, currency: str) -> OrderResult: ...

    def capture_order(self, order_id: str, *, idempotency_key: str) -> CaptureResult: ...

    def get_order(self, order_id: str) -> dict[str, Any]: ...


class PayPalProvider:
    mode = "paypal"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._client = httpx.Client(base_url=settings.paypal_base_url, timeout=20.0, transport=transport)
        self._token: str | None = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._token_expiry - 60:
                return self._token
            try:
                resp = self._client.post(
                    "/v1/oauth2/token",
                    data={"grant_type": "client_credentials"},
                    auth=(self._settings.paypal_client_id, self._settings.paypal_client_secret),
                )
            except httpx.HTTPError as exc:
                raise PaymentError("PayPal could not be reached.") from exc
            if resp.status_code in (400, 401):
                raise PaymentError("PayPal rejected the configured credentials.", retryable=False)
            if resp.status_code >= 400:
                raise PaymentError(f"PayPal authentication failed ({resp.status_code}).")
            body = resp.json()
            self._token = body["access_token"]
            self._token_expiry = time.monotonic() + float(body.get("expires_in", 300))
            return self._token

    def _request(self, method: str, path: str, *, idempotency_key: str | None = None, json: Any = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}
        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key
        try:
            resp = self._client.request(method, path, headers=headers, json=json)
        except httpx.HTTPError as exc:
            raise PaymentError("PayPal could not be reached.") from exc
        if resp.status_code >= 400:
            try:
                details = resp.json()
            except ValueError:
                details = {"body": resp.text[:500]}
            issue = ""
            if isinstance(details, dict):
                issues = details.get("details") or []
                issue = issues[0].get("issue", "") if issues else details.get("name", "")
            log.warning("PayPal API error", extra={"data": {"status": resp.status_code, "issue": issue, "path": path}})
            raise PaymentError(
                f"PayPal returned {resp.status_code}{f' ({issue})' if issue else ''}.",
                retryable=resp.status_code >= 500,
                details=details,
            )
        return resp.json() if resp.content else {}

    def create_order(self, *, reference_id: str, trace_id: str, description: str, amount: Decimal, currency: str) -> OrderResult:
        frontend = self._settings.frontend_url.rstrip("/")
        body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": reference_id,
                    "custom_id": trace_id,
                    "description": description[:127],
                    "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                }
            ],
            "application_context": {
                "brand_name": "PayPilot",
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING",
                "return_url": f"{frontend}/paypal/return?tx={reference_id}",
                "cancel_url": f"{frontend}/transactions?tx={reference_id}",
            },
        }
        data = self._request("POST", "/v2/checkout/orders", idempotency_key=f"{reference_id}-create", json=body)
        approve = next((l["href"] for l in data.get("links", []) if l.get("rel") in ("approve", "payer-action")), None)
        return OrderResult(order_id=data["id"], status=data.get("status", "CREATED"), approve_url=approve, simulated=False, raw=data)

    def capture_order(self, order_id: str, *, idempotency_key: str) -> CaptureResult:
        data = self._request("POST", f"/v2/checkout/orders/{order_id}/capture", idempotency_key=idempotency_key, json={})
        capture_id = None
        try:
            capture_id = data["purchase_units"][0]["payments"]["captures"][0]["id"]
        except (KeyError, IndexError, TypeError):
            pass
        return CaptureResult(order_id=order_id, status=data.get("status", "UNKNOWN"), capture_id=capture_id, simulated=False, raw=data)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/checkout/orders/{order_id}")

    def check_connection(self) -> bool:
        try:
            self._access_token()
            return True
        except PaymentError:
            return False


class SimulatedProvider:
    """Clearly-labelled stand-in used only when PayPal credentials are not configured."""

    mode = "simulated"

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}

    def create_order(self, *, reference_id: str, trace_id: str, description: str, amount: Decimal, currency: str) -> OrderResult:
        order_id = f"SIM-{secrets.token_hex(6).upper()}"
        self._orders[order_id] = {"id": order_id, "status": "CREATED", "amount": f"{amount:.2f}", "currency": currency, "simulated": True}
        return OrderResult(order_id=order_id, status="CREATED", approve_url=None, simulated=True, raw=self._orders[order_id])

    def capture_order(self, order_id: str, *, idempotency_key: str) -> CaptureResult:
        order = self._orders.get(order_id)
        if order is None:
            # Process restarted; simulated orders are not persisted by a provider.
            order = {"id": order_id, "simulated": True}
            self._orders[order_id] = order
        order["status"] = "COMPLETED"
        order.setdefault("capture_id", f"SIMCAP-{secrets.token_hex(5).upper()}")
        return CaptureResult(order_id=order_id, status="COMPLETED", capture_id=order["capture_id"], simulated=True, raw=order)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._orders.get(order_id, {"id": order_id, "status": "UNKNOWN", "simulated": True})


_provider: PaymentProvider | None = None
_status_cache: tuple[float, bool] | None = None


def get_payment_provider() -> PaymentProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        _provider = PayPalProvider(settings) if settings.paypal_configured else SimulatedProvider()
    return _provider


def set_payment_provider(provider: PaymentProvider | None) -> None:
    """Test hook."""
    global _provider, _status_cache
    _provider = provider
    _status_cache = None


def provider_status() -> dict[str, Any]:
    global _status_cache
    settings = get_settings()
    provider = get_payment_provider()
    if isinstance(provider, PayPalProvider):
        now = time.monotonic()
        if _status_cache is None or now - _status_cache[0] > 60:
            _status_cache = (now, provider.check_connection())
        connected = _status_cache[1]
        return {
            "mode": "paypal",
            "environment": settings.paypal_environment,
            "connected": connected,
            "client_id": settings.paypal_client_id,
            "settlement_currency": settings.paypal_settlement_currency,
            "label": f"PayPal {settings.paypal_environment.title()}",
        }
    return {
        "mode": "simulated",
        "environment": "demo",
        "connected": True,
        "client_id": None,
        "settlement_currency": settings.paypal_settlement_currency,
        "label": "Simulated payments (no PayPal credentials)",
    }
