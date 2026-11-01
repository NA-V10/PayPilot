from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Transaction
from app.schemas.api import AuditEventOut, TransactionDetail, TransactionOut


def tx_out(tx: Transaction) -> TransactionOut:
    out = TransactionOut.model_validate(tx)
    out.policy_decision = (tx.policy_result or {}).get("decision")
    return out


def tx_detail(db: Session, tx: Transaction) -> TransactionDetail:
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.transaction_id == tx.id).order_by(AuditEvent.timestamp, AuditEvent.id)
    ).all()
    out = TransactionDetail.model_validate(tx)
    out.policy_decision = (tx.policy_result or {}).get("decision")
    out.events = [AuditEventOut.model_validate(e) for e in events]
    return out
