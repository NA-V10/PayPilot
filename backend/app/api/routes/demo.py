from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.serializers import tx_detail
from app.core.config import get_settings
from app.core.security import Principal, agent_rate_limit, get_principal
from app.db.session import get_db
from app.schemas.api import DemoRunRequest, TransactionDetail
from app.services.scenarios import SCENARIOS, run_scenario

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/scenarios")
def scenarios() -> list[dict[str, object]]:
    return [
        {"id": s.id, "title": s.title, "agent_id": s.agent_id, "request": s.request, "amount": float(s.amount),
         "currency": "INR", "expected": s.expected, "mode": s.mode, "note": s.note, "faults": sorted(s.faults)}
        for s in SCENARIOS.values()
    ]


@router.post("/run", response_model=TransactionDetail, dependencies=[Depends(agent_rate_limit)])
def run(body: DemoRunRequest, db: Session = Depends(get_db), _: Principal = Depends(get_principal)) -> TransactionDetail:
    """Run a deterministic demo scenario through the real governance pipeline."""
    if not get_settings().demo_mode:
        raise HTTPException(403, "Demo mode is disabled")
    tx = run_scenario(db, body.scenario)
    db.commit()
    return tx_detail(db, tx)


@router.post("/reset")
def reset(db: Session = Depends(get_db), _: Principal = Depends(get_principal)) -> dict[str, str]:
    """Restore the seeded dataset."""
    if not get_settings().demo_mode:
        raise HTTPException(403, "Demo mode is disabled")
    from app.db.seed import seed

    seed(db, reset=True)
    return {"status": "reset"}
