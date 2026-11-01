"""PayPal payment routes. Only governance-approved transactions can reach PayPal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import tx_detail
from app.core.enums import TransactionStatus
from app.core.security import Principal, get_principal, payment_rate_limit
from app.db.models import Transaction
from app.db.session import get_db
from app.schemas.api import CaptureOrderRequest, CreateOrderRequest, TransactionDetail
from app.services import orchestrator
from app.services.paypal import PaymentError, get_payment_provider, provider_status


def build_router(prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["payments"], dependencies=[Depends(payment_rate_limit)])

    @router.get("/status")
    def status() -> dict[str, object]:
        return provider_status()

    @router.post("/create-order", response_model=TransactionDetail)
    def create_order(body: CreateOrderRequest, db: Session = Depends(get_db), _: Principal = Depends(get_principal)) -> TransactionDetail:
        """Create (or return the existing) PayPal order for an authorized transaction.

        Amount and currency come from the stored transaction, never from the client.
        """
        tx = db.get(Transaction, body.transaction_id)
        if tx is None:
            raise HTTPException(404, "Transaction not found")
        if tx.status == TransactionStatus.PAYMENT_CREATED:
            return tx_detail(db, tx)
        try:
            orchestrator.start_payment(db, tx)
        except orchestrator.TransitionError as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc
        db.commit()
        return tx_detail(db, tx)

    @router.post("/capture-order", response_model=TransactionDetail)
    def capture_order(body: CaptureOrderRequest, db: Session = Depends(get_db), _: Principal = Depends(get_principal)) -> TransactionDetail:
        tx = db.get(Transaction, body.transaction_id)
        if tx is None:
            raise HTTPException(404, "Transaction not found")
        try:
            orchestrator.capture_payment(db, tx, body.order_id)
        except orchestrator.TransitionError as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc
        db.commit()
        return tx_detail(db, tx)

    @router.get("/{order_id}")
    def get_order(order_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
        tx = db.scalar(select(Transaction).where(Transaction.paypal_order_id == order_id))
        if tx is None:
            raise HTTPException(404, "Order not found")
        try:
            remote = get_payment_provider().get_order(order_id)
        except PaymentError as exc:
            remote = {"error": str(exc)}
        return {"transaction_id": tx.id, "status": tx.status, "paypal_status": tx.paypal_status, "provider": tx.payment_provider, "order": remote}

    return router


paypal_router = build_router("/paypal")
payments_router = build_router("/payments")
