from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.intelligence import AgentAssessment, IntelligenceAnalysis
from app.schemas.rag import GroundedCitation
from app.schemas.signals import SignalDimension

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_api_demo_seed_endpoint(client):
    response = client.post("/api/v1/demo/seed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["documents_seeded"] >= 5


def test_api_search_documents(client):
    response = client.get("/api/v1/documents/search", params={"q": "cloud revenue", "symbol": "MSFT"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_evaluation_metrics(client):
    response = client.get("/api/v1/intelligence/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert "total_signals_evaluated" in data
    assert "accuracy_rate_percent" in data


def test_evaluation_update_trigger_requires_token_and_returns_summary(client, monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes.settings, "evaluation_update_token", "test-operator-token")
    updater = AsyncMock(return_value={
        "attempted": 1,
        "evaluated": 1,
        "unavailable": 0,
        "not_matured": 0,
    })
    monkeypatch.setattr(routes, "update_matured_evaluations", updater)

    unauthorized = client.post("/api/v1/intelligence/evaluation/update")
    assert unauthorized.status_code == 404
    updater.assert_not_awaited()

    authorized = client.post(
        "/api/v1/intelligence/evaluation/update",
        headers={"X-Evaluation-Update-Token": "test-operator-token"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["evaluated"] == 1
    updater.assert_awaited_once()


def test_api_portfolio_risk(client):
    response = client.get("/api/v1/profiles/demo_profile_conservative/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_id"] == "demo_profile_conservative"
    assert "hhi_score" in data
    assert len(data["holdings"]) > 0


def test_api_compare_profiles(client, monkeypatch):
    technical_fetch = AsyncMock(side_effect=AssertionError("comparison must reuse its analysis snapshot"))
    monkeypatch.setattr(
        "app.api.routes.analyze_symbol",
        AsyncMock(return_value=SimpleNamespace(
            overall_status="bullish",
            signals=[SimpleNamespace(
                dimension=SignalDimension.PRICE_MOMENTUM,
                metrics={"volatility_daily": 3.0, "rsi_14": 74.0},
            )],
        )),
    )
    monkeypatch.setattr(
        "app.api.routes.get_technical_analysis",
        technical_fetch,
    )

    response = client.post(
        "/api/v1/intelligence/compare-profiles",
        json={
            "symbol": "AAPL",
            "profile_a_id": "demo_profile_conservative",
            "profile_b_id": "demo_profile_aggressive",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["market_facts_unaltered"] is True
    assert data["profile_a"]["risk_tolerance"] == 1
    assert data["profile_b"]["risk_tolerance"] == 5
    assert data["profile_a"]["suitability_rating"] == "Caution / High Volatility for Conservative Mandate"
    assert data["profile_b"]["suitability_rating"] == "Suitable for Growth Mandate"
    technical_fetch.assert_not_awaited()


def test_profile_comparison_does_not_return_provider_exception_details(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.analyze_symbol",
        AsyncMock(side_effect=RuntimeError("provider failure with credential=DO_NOT_DISCLOSE")),
    )

    response = client.post(
        "/api/v1/intelligence/compare-profiles",
        json={
            "symbol": "AAPL",
            "profile_a_id": "demo_profile_conservative",
            "profile_b_id": "demo_profile_aggressive",
        },
    )

    assert response.status_code == 503
    assert "DO_NOT_DISCLOSE" not in response.text
    assert "provider failure" not in response.text
    assert "provider details are withheld" in response.json()["detail"]


def test_api_analysis_preserves_unavailable_agent_status(client, monkeypatch):
    partial_analysis = IntelligenceAnalysis(
        symbol="AAPL",
        generated_at_utc=datetime.now(timezone.utc),
        overall_status="insufficient_data",
        assessments=[
            AgentAssessment(
                agent_name="Technical Agent",
                status="unavailable",
                summary="Technical data is unavailable.",
                source="unavailable",
                confidence=0.0,
                limitations=["No usable technical data was returned."],
            )
        ],
        data_warnings=["Technical analysis unavailable; other results may still be available."],
        analysis_note="Partial analysis; unavailable agents are not treated as neutral observations.",
    )
    monkeypatch.setattr(
        "app.api.routes.analyze_symbol",
        AsyncMock(return_value=partial_analysis),
    )

    response = client.post("/api/v1/intelligence/analyze", json={"symbol": "AAPL"})

    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "insufficient_data"
    assert data["analysis_completeness"] == "partial"
    assert data["assessments"][0]["status"] == "unavailable"
    assert data["assessments"][0]["confidence"] == 0.0
    assert "unavailable" in data["data_warnings"][0].lower()


def test_api_marks_directional_consensus_partial_when_one_agent_is_unavailable(client, monkeypatch):
    partial_analysis = IntelligenceAnalysis(
        symbol="AAPL",
        generated_at_utc=datetime.now(timezone.utc),
        overall_status="bullish",
        analysis_completeness="partial",
        assessments=[
            AgentAssessment(
                agent_name="Technical Agent",
                status="bullish",
                summary="Technical fixture assessment.",
                source="Synthetic test fixture",
                confidence=0.8,
            ),
            AgentAssessment(
                agent_name="Fundamental Agent",
                status="bullish",
                summary="Fundamental fixture assessment.",
                source="Synthetic test fixture",
                confidence=0.7,
            ),
            AgentAssessment(
                agent_name="News Sentiment Agent",
                status="unavailable",
                summary="News fixture unavailable.",
                source="Unavailable",
                confidence=0.0,
            ),
        ],
        data_warnings=["News Sentiment Agent unavailable; no news-based conclusion was included."],
        analysis_note="The directional assessments agree, but this represents partial support.",
    )
    monkeypatch.setattr(
        "app.api.routes.analyze_symbol",
        AsyncMock(return_value=partial_analysis),
    )

    response = client.post("/api/v1/intelligence/analyze", json={"symbol": "AAPL"})

    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "bullish"
    assert data["analysis_completeness"] == "partial"
    assert data["assessments"][2]["status"] == "unavailable"
    assert data["assessments"][2]["confidence"] == 0.0


def test_analysis_api_preserves_synthetic_context_source_and_ids(client, monkeypatch):
    unsupported_claim = "Cloud revenue collapsed after enterprise migration stopped."
    citation = GroundedCitation(
        claim=unsupported_claim,
        claim_type="context",
        document_id="synthetic-document-id",
        chunk_id="synthetic-chunk-id",
        document_title="Synthetic fixture disclosure",
        issuer="Fixture Corporation",
        ticker="MSFT",
        reporting_period="Synthetic fixture period",
        excerpt="Synthetic fixture: Azure cloud revenue grew with enterprise migration.",
        relevance_score=1.25,
        synthetic=True,
        source_name="Synthetic test corpus",
    )
    analysis = IntelligenceAnalysis(
        symbol="MSFT",
        generated_at_utc=datetime.now(timezone.utc),
        overall_status="insufficient_data",
        assessments=[
            AgentAssessment(
                agent_name="News Sentiment Agent",
                status="neutral",
                summary=unsupported_claim,
                evidence=[unsupported_claim],
                source="Deterministic synthetic test fixture",
                citations=[citation],
            )
        ],
        citations=[citation],
        data_warnings=["Synthetic source; this fixture does not verify the claim."],
        analysis_note="Informational test synthesis.",
    )
    monkeypatch.setattr("app.api.routes.analyze_symbol", AsyncMock(return_value=analysis))

    response = client.get("/api/v1/intelligence/analyze/MSFT")

    assert response.status_code == 200
    data = response.json()
    serialized_citation = data["citations"][0]
    assert data["assessments"][0]["summary"] == unsupported_claim
    assert serialized_citation["claim"] == unsupported_claim
    assert serialized_citation["claim_type"] == "context"
    assert serialized_citation["synthetic"] is True
    assert serialized_citation["source_name"] == "Synthetic test corpus"
    assert serialized_citation["document_id"] == "synthetic-document-id"
    assert serialized_citation["chunk_id"] == "synthetic-chunk-id"
