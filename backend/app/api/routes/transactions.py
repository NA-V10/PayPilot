from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.serializers import tx_detail, tx_out
from app.core.enums import ApprovalStatus, TransactionStatus
from app.core.security import Principal, get_principal
from app.db.models import AuditEvent, Merchant, Transaction
from app.db.session import get_db
from app.schemas.api import ApprovalAction, AuditEventOut, TransactionDetail, TransactionOut, TransactionPage
from app.services import orchestrator

router = APIRouter(tags=["transactions"])


def _get_tx(db: Session, tx_id: str) -> Transaction:
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(404, f"Transaction {tx_id} not found")
    return tx


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    db: Session = Depends(get_db),
    status: list[str] | None = Query(default=None),
    agent_id: str | None = None,
    risk_level: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionPage:
    stmt = select(Transaction).outerjoin(Merchant, Transaction.merchant_id == Merchant.id)
    if status:
        stmt = stmt.where(Transaction.status.in_(status))
    if agent_id:
        stmt = stmt.where(Transaction.agent_id == agent_id)
    if risk_level:
        stmt = stmt.where(Transaction.risk_level == risk_level)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Transaction.id.ilike(like), Transaction.description.ilike(like), Merchant.name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)).all()
    return TransactionPage(items=[tx_out(t) for t in rows], total=total)


@router.get("/transactions/{tx_id}", response_model=TransactionDetail)
def get_transaction(tx_id: str, db: Session = Depends(get_db)) -> TransactionDetail:
    return tx_detail(db, _get_tx(db, tx_id))


@router.get("/transactions/{tx_id}/events", response_model=list[AuditEventOut])
def get_events(tx_id: str, db: Session = Depends(get_db)) -> list[AuditEventOut]:
    _get_tx(db, tx_id)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.transaction_id == tx_id).order_by(AuditEvent.timestamp)).all()
    return [AuditEventOut.model_validate(e) for e in rows]


# ---------------- approvals


@router.get("/approvals", response_model=list[TransactionDetail])
def list_approvals(db: Session = Depends(get_db), state: str = Query(default="pending", pattern="^(pending|resolved|all)$")) -> list[TransactionDetail]:
    stmt = select(Transaction)
    if state == "pending":
        stmt = stmt.where(Transaction.approval_status == ApprovalStatus.PENDING, Transaction.status == TransactionStatus.AWAITING_APPROVAL)
    elif state == "resolved":
        stmt = stmt.where(Transaction.approval_status.in_([ApprovalStatus.APPROVED, ApprovalStatus.DENIED]))
    else:
        stmt = stmt.where(Transaction.approval_status != ApprovalStatus.NOT_REQUIRED)
    rows = db.scalars(stmt.order_by(Transaction.created_at.desc()).limit(100)).all()
    return [tx_detail(db, t) for t in rows]


@router.post("/approvals/{tx_id}/approve", response_model=TransactionDetail)
def approve(tx_id: str, body: ApprovalAction | None = None, db: Session = Depends(get_db), who: Principal = Depends(get_principal)) -> TransactionDetail:
    tx = _get_tx(db, tx_id)
    try:
        orchestrator.approve(db, tx, who.name, body.note if body else None)
    except orchestrator.TransitionError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    return tx_detail(db, tx)


@router.post("/approvals/{tx_id}/deny", response_model=TransactionDetail)
def deny(tx_id: str, body: ApprovalAction | None = None, db: Session = Depends(get_db), who: Principal = Depends(get_principal)) -> TransactionDetail:
    tx = _get_tx(db, tx_id)
    try:
        orchestrator.deny(db, tx, who.name, body.note if body else None)
    except orchestrator.TransitionError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    return tx_detail(db, tx)


__all__ = ["router", "TransactionOut"]
