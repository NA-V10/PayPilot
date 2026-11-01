"""PayPilot API: the financial control plane for autonomous AI agents."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import agents, demo, insights, policies, system, transactions
from app.api.routes.payments import paypal_router, payments_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.paypal import PaymentError

configure_logging()
log = get_logger("api")
settings = get_settings()

app = FastAPI(
    title="PayPilot API",
    version="1.0.0",
    description=(
        "AI can reason. PayPilot decides if it can spend.\n\n"
        "Every agent payment passes AgentShield, the Risk Engine, the Policy Engine and the "
        "Approval Engine before PayPal executes it. Authorization is deterministic; no LLM can override it."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Hosted frontends on Render / Vercel. No cookies are used, so this grants no ambient credentials.
    allow_origin_regex=r"https://[a-z0-9-]+\.(onrender\.com|vercel\.app)",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-PayPilot-Key"],
)


def _error(status: int, code: str, message: str, **extra: object) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, **extra}})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    code = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict", 422: "invalid", 429: "rate_limited"}
    return _error(exc.status_code, code.get(exc.status_code, "error"), str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return _error(422, "invalid", "Some fields are invalid.", fields=fields)


@app.exception_handler(PaymentError)
async def payment_error(_: Request, exc: PaymentError) -> JSONResponse:
    return _error(502, "payment_provider_unavailable", f"{exc} No money was moved.", retryable=exc.retryable)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error")
    return _error(500, "internal", "Something went wrong. No money was moved.")


for r in (system.router, agents.router, policies.router, transactions.router, insights.router, demo.router, paypal_router, payments_router):
    app.include_router(r, prefix="/api")
