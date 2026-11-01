from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

# Configure an isolated database and deterministic providers before the app is imported.
_tmp = Path(tempfile.mkdtemp(prefix="paypilot-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["PAYPAL_CLIENT_ID"] = ""
os.environ["PAYPAL_CLIENT_SECRET"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["PAYPILOT_API_KEY"] = ""
os.environ["DEMO_MODE"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import agent_rate_limit, payment_rate_limit  # noqa: E402
from app.db import models  # noqa: E402,F401
from app.db.seed import seed  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.llm import reset_llm, set_llm  # noqa: E402
from app.services.paypal import SimulatedProvider, set_payment_provider  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db() -> Iterator[None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    set_payment_provider(SimulatedProvider())
    set_llm(None)
    agent_rate_limit.reset()
    payment_rate_limit.reset()
    yield
    set_payment_provider(None)
    reset_llm()


@pytest.fixture
def db() -> Iterator[object]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
