from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.llm import get_llm
from app.services.paypal import provider_status

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system/status")
def system_status() -> dict[str, object]:
    settings = get_settings()
    llm = get_llm()
    return {
        "demo_mode": settings.demo_mode,
        "payments": provider_status(),
        "llm": {
            "configured": llm is not None,
            "provider": llm.name if llm else None,
            "model": llm.model if llm else None,
            "label": f"{llm.name} · {llm.model}" if llm else "Rule-based parser (no LLM configured)",
        },
        "authorization": "deterministic",
    }
