from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientError

from app.core import auth
from app.core.config import settings
from app.main import app

ISSUER = "https://test-project.supabase.co/auth/v1"
AUDIENCE = "authenticated"


@pytest.fixture
def token_tools(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, token):
            header = jwt.get_unverified_header(token)
            if header.get("kid") != "local-test-key":
                raise PyJWKClientError("Unknown key id")
            return SimpleNamespace(key=public_key, algorithm_name="RS256")

    monkeypatch.setattr(settings, "supabase_url", "https://test-project.supabase.co")
    monkeypatch.setattr(settings, "supabase_jwt_audience", AUDIENCE)
    monkeypatch.setattr(auth, "_jwks_client", lambda _url: FakeJwksClient())

    def make_token(
        *,
        subject="user-a",
        issuer=ISSUER,
        audience=AUDIENCE,
        expires_in=60,
        role="authenticated",
        key=private_key,
        kid="local-test-key",
    ):
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": subject,
                "iss": issuer,
                "aud": audience,
                "role": role,
                "iat": now,
                "exp": now + timedelta(seconds=expires_in),
            },
            key,
            algorithm="RS256",
            headers={"kid": kid},
        )

    return make_token, private_key


@pytest.fixture
def client(token_tools):
    with TestClient(app) as test_client:
        yield test_client


def test_protected_endpoint_rejects_missing_and_malformed_tokens(client):
    assert client.get("/api/v1/profiles").status_code == 401
    malformed = client.get(
        "/api/v1/profiles", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert malformed.status_code == 401


def test_auth_configuration_rejects_non_project_supabase_urls(client, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://supabase.example/project/path")
    response = client.get(
        "/api/v1/profiles",
        headers={"Authorization": "Bearer a.b.c"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication is not configured."


@pytest.mark.parametrize(
    "claims",
    [
        {"expires_in": -60},
        {"issuer": "https://other.supabase.co/auth/v1"},
        {"audience": "wrong-audience"},
        {"role": "service_role"},
        {"kid": "unknown-key"},
    ],
)
def test_protected_endpoint_rejects_invalid_claims(client, token_tools, claims):
    make_token, _ = token_tools
    response = client.get(
        "/api/v1/profiles",
        headers={"Authorization": f"Bearer {make_token(**claims)}"},
    )
    assert response.status_code == 401


def test_protected_endpoint_rejects_a_forged_signature(client, token_tools):
    make_token, _ = token_tools
    forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = client.get(
        "/api/v1/profiles",
        headers={"Authorization": f"Bearer {make_token(key=forged_key)}"},
    )
    assert response.status_code == 401


def test_valid_token_creates_identity_from_verified_issuer_and_subject(client, token_tools):
    make_token, _ = token_tools
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {make_token(subject='stable-user-a')}"},
    )
    assert response.status_code == 200
    assert response.json()["issuer"] == ISSUER
    assert response.json()["subject"] == "stable-user-a"
    assert response.json()["id"]


def test_public_health_endpoint_remains_anonymous(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_profile_and_nested_holding_access_is_scoped_to_verified_user(client, token_tools):
    make_token, _ = token_tools
    token_a = make_token(subject="owner-a")
    token_b = make_token(subject="owner-b")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    created = client.post(
        "/api/v1/profiles",
        headers=headers_a,
        json={
            "name": "Owner A profile",
            "risk_tolerance": 3,
            "investment_horizon_months": 18,
            "max_single_asset_allocation": 0.2,
            "owner_id": "forged-client-owner",
        },
    )
    assert created.status_code == 201
    profile_id = created.json()["id"]
    owner_a_profile = client.get(f"/api/v1/profiles/{profile_id}", headers=headers_a)
    assert owner_a_profile.status_code == 200

    owner_b_profile = client.get(f"/api/v1/profiles/{profile_id}", headers=headers_b)
    assert owner_b_profile.status_code == 404
    owner_b_list = client.get("/api/v1/profiles", headers=headers_b)
    assert owner_b_list.status_code == 200
    assert profile_id not in {profile["id"] for profile in owner_b_list.json()}

    holding_payload = {
        "symbol": "AAPL",
        "shares": 2,
        "weight": 0.1,
        "asset_category": "Technology",
    }
    denied_holding = client.post(
        f"/api/v1/profiles/{profile_id}/holdings",
        headers=headers_b,
        json=holding_payload,
    )
    assert denied_holding.status_code == 404
    added_holding = client.post(
        f"/api/v1/profiles/{profile_id}/holdings",
        headers=headers_a,
        json=holding_payload,
    )
    assert added_holding.status_code == 201
    assert added_holding.json()["profile_id"] == profile_id

    assert client.get(
        f"/api/v1/profiles/{profile_id}/portfolio", headers=headers_b
    ).status_code == 404
    assert client.put(f"/api/v1/profiles/{profile_id}", headers=headers_a).status_code == 405
    assert client.delete(f"/api/v1/profiles/{profile_id}", headers=headers_a).status_code == 405


def test_session_detail_is_not_disclosed_across_users(client, token_tools):
    from app.db.session import SessionLocal
    from app.models.session import AnalysisSession

    make_token, _ = token_tools
    token_a = make_token(subject="session-owner-a")
    token_b = make_token(subject="session-owner-b")
    response = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token_a}"}
    )
    owner_id = response.json()["id"]
    session_id = "30000000-0000-4000-8000-000000000001"
    with SessionLocal() as db:
        db.add(
            AnalysisSession(
                id=session_id,
                symbol="AAPL",
                status="completed",
                overall_classification="neutral",
                total_latency_ms=1,
                rag_latency_ms=0,
                agents_data="[]",
                disagreements_data="[]",
                signals_data="[]",
                citations_data="[]",
                reasoning_trace="[]",
                personalized_interpretation="{}",
                owner_id=owner_id,
            )
        )
        db.commit()

    own = client.get(
        f"/api/v1/intelligence/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    other = client.get(
        f"/api/v1/intelligence/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert own.status_code == 200
    assert other.status_code == 404
    listed_by_other = client.get(
        "/api/v1/intelligence/sessions",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert session_id not in {item["id"] for item in listed_by_other.json()}


def test_evaluation_metrics_are_scoped_to_the_verified_user(client, token_tools):
    from app.db.session import SessionLocal
    from app.models.evaluation import SignalEvaluation
    from app.models.session import AnalysisSession

    make_token, _ = token_tools
    token_a = make_token(subject="evaluation-owner-a")
    token_b = make_token(subject="evaluation-owner-b")
    owner_a_id = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["id"]
    owner_b_id = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token_b}"}
    ).json()["id"]

    def session(session_id: str, owner_id: str, symbol: str) -> AnalysisSession:
        return AnalysisSession(
            id=session_id,
            symbol=symbol,
            status="completed",
            overall_classification="bullish",
            total_latency_ms=100,
            rag_latency_ms=10,
            agents_data="[]",
            disagreements_data="[]",
            signals_data="[]",
            citations_data="[]",
            reasoning_trace="[]",
            personalized_interpretation="{}",
            owner_id=owner_id,
        )

    session_a_id = "40000000-0000-4000-8000-000000000001"
    session_b_id = "40000000-0000-4000-8000-000000000002"
    with SessionLocal() as db:
        db.add_all([
            session(session_a_id, owner_a_id, "AAPL"),
            session(session_b_id, owner_b_id, "MSFT"),
        ])
        for session_id, owner_id, symbol in (
            (session_a_id, owner_a_id, "AAPL"),
            (session_b_id, owner_b_id, "MSFT"),
        ):
            db.add(
                SignalEvaluation(
                    session_id=session_id,
                    owner_id=owner_id,
                    symbol=symbol,
                    signal_dimension="synthesis",
                    signal_classification="bullish",
                    signal_timestamp=datetime.now(timezone.utc),
                    entry_price=100,
                    evaluation_horizon_days=30,
                    target_date="2099-01-01",
                    outcome="pending_window",
                    is_synthetic=False,
                    data_source="Synthetic test fixture",
                )
            )
        db.commit()

    response_a = client.get(
        "/api/v1/intelligence/evaluation",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    response_b = client.get(
        "/api/v1/intelligence/evaluation",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response_a.status_code == response_b.status_code == 200
    metrics_a = response_a.json()
    metrics_b = response_b.json()
    assert metrics_a["total_sessions"] == 1
    assert metrics_a["total_signals_evaluated"] == 1
    assert {row["symbol"] for row in metrics_a["evaluation_history"]} == {"AAPL"}
    assert metrics_b["total_sessions"] == 1
    assert metrics_b["total_signals_evaluated"] == 1
    assert {row["symbol"] for row in metrics_b["evaluation_history"]} == {"MSFT"}
