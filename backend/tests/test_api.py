from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_current_user
from app.models.user import UserIdentity
from app.services.historical_prices import (
    HistoricalBar,
    HistoricalPriceHistory,
)


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: UserIdentity(
        id="11111111-1111-4111-8111-111111111111",
        issuer="https://test.supabase.co/auth/v1",
        subject="legacy-api-test-user",
    )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["application"] == "FinWiseAI"


def test_health(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"


def test_create_and_retrieve_investor(client):
    payload = {
        "name": "Demo Investor",
        "risk_tolerance": 2,
        "investment_horizon_months": 24,
        "max_single_asset_allocation": 0.15,
    }

    created = client.post("/api/v1/investors", json=payload)

    assert created.status_code == 201

    profile = created.json()

    assert profile["name"] == "Demo Investor"
    assert profile["risk_tolerance"] == 2
    assert profile["max_single_asset_allocation"] == 0.15

    retrieved = client.get(
        f"/api/v1/investors/{profile['id']}"
    )

    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == profile["id"]


def test_invalid_risk_tolerance_is_rejected(client):
    payload = {
        "name": "Invalid Investor",
        "risk_tolerance": 8,
        "investment_horizon_months": 12,
        "max_single_asset_allocation": 0.20,
    }

    response = client.post("/api/v1/investors", json=payload)

    assert response.status_code == 422


def test_missing_investor_returns_404(client):
    response = client.get(
        "/api/v1/investors/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


def test_market_history_endpoint(client, monkeypatch):
    history = HistoricalPriceHistory(
        symbol="AAPL",
        bars=(
            HistoricalBar(
                trading_day="2026-10-13",
                open=100.0,
                high=103.0,
                low=99.0,
                close=102.0,
                volume=1_000_000,
            ),
        ),
        source="Test fixture",
        fetched_at_utc=datetime.now(timezone.utc),
        data_note="Deterministic test history.",
    )
    monkeypatch.setattr(
        "app.api.routes.get_historical_prices",
        AsyncMock(return_value=history),
    )

    response = client.get("/api/v1/market/history/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert isinstance(data["bars"], list)
    assert len(data["bars"]) > 0
    assert "close" in data["bars"][-1]
    assert "trading_day" in data["bars"][-1]


def test_market_history_invalid_symbol(client):
    response = client.get("/api/v1/market/history/INVALID$$$SYMBOL")
    assert response.status_code == 422
