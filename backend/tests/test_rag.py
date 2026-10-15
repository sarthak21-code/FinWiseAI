from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.services.rag import (
    chunk_text,
    compute_content_hash,
    ground_agent_claims,
    ingest_document,
    search_documents,
    seed_demonstration_corpus,
)


def ingest_fixture(db, *, ticker: str, title: str, text: str, source: str = "Synthetic test corpus"):
    return ingest_document(
        db=db,
        issuer="Fixture Corporation",
        ticker=ticker,
        title=title,
        document_type="Synthetic test passage",
        reporting_period="Synthetic fixture period",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        raw_content=text,
        source_name=source,
        source_url=None,
        synthetic=True,
    )


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_chunk_text_preserves_sections():
    sample_text = (
        "# Item 1 Business\n\n"
        "We are a leading provider of accelerated computing chips and networking solutions. "
        "Our architectures power the world's most advanced artificial intelligence models.\n\n"
        "# Item 1A Risk Factors\n\n"
        "Export controls restrict shipments of specialized GPUs to certain international jurisdictions."
    )
    chunks = chunk_text(sample_text, target_words=50)
    assert len(chunks) >= 2
    assert any("Business" in c[0] for c in chunks)
    assert any("Risk Factors" in c[0] for c in chunks)


def test_ingest_and_search_documents(in_memory_db):
    doc = ingest_document(
        db=in_memory_db,
        issuer="Test Corp",
        ticker="TEST",
        title="Test Corp 10-K Report",
        document_type="10-K",
        reporting_period="FY 2025",
        published_at=datetime.now(timezone.utc),
        raw_content="Cloud revenue increased 35% driven by enterprise AI adoption and expanding margins.",
        source_name="SEC",
        synthetic=False,
    )
    assert doc.id is not None

    # Search matches
    results = search_documents(in_memory_db, query="Cloud revenue enterprise AI", symbol="TEST")
    assert len(results) > 0
    assert results[0].ticker == "TEST"
    assert "Cloud revenue" in results[0].excerpt

    # Empty query or non-existent terms return empty
    empty_results = search_documents(in_memory_db, query="nonexistentterm12345", symbol="TEST")
    assert len(empty_results) == 0


def test_seed_demonstration_corpus_idempotent(in_memory_db):
    first_count = seed_demonstration_corpus(in_memory_db)
    assert first_count >= 5
    from app.models.document import FinancialDocument

    seeded_documents = in_memory_db.query(FinancialDocument).all()
    assert all(document.synthetic for document in seeded_documents)
    assert all(document.source_url is None for document in seeded_documents)

    # Second call should not duplicate
    second_count = seed_demonstration_corpus(in_memory_db)
    assert second_count == first_count


def test_ground_agent_claims(in_memory_db):
    seed_demonstration_corpus(in_memory_db)
    claims = ["Services revenue reached an all-time record supported by installed base"]
    citations = ground_agent_claims(in_memory_db, symbol="AAPL", claims=claims)
    assert len(citations) > 0
    assert citations[0].ticker == "AAPL"
    assert citations[0].relevance_score > 0.0
    assert citations[0].claim_type == "context"
    assert citations[0].synthetic is True
    assert citations[0].source_name == "VantageAI synthetic demonstration corpus"


def test_query_changes_bm25_ranking_and_persisted_ids_are_stable(in_memory_db):
    seed_demonstration_corpus(in_memory_db)

    capacity_results = search_documents(
        in_memory_db,
        query="power grid constraints semiconductor delivery data center capacity",
        symbol="MSFT",
        top_k=5,
    )
    revenue_results = search_documents(
        in_memory_db,
        query="Azure cloud revenue grew enterprise migration year over year",
        symbol="MSFT",
        top_k=5,
    )
    repeated_revenue_results = search_documents(
        in_memory_db,
        query="Azure cloud revenue grew enterprise migration year over year",
        symbol="MSFT",
        top_k=5,
    )

    assert capacity_results
    assert revenue_results
    assert capacity_results[0].chunk_id != revenue_results[0].chunk_id
    assert [item.chunk_id for item in revenue_results] == [
        item.chunk_id for item in repeated_revenue_results
    ]
    assert [item.relevance_score for item in revenue_results] == [
        item.relevance_score for item in repeated_revenue_results
    ]
    assert all(item.document_id and item.chunk_id for item in revenue_results)


def test_matching_claim_is_still_context_not_verified_support(in_memory_db):
    ingest_fixture(
        in_memory_db,
        ticker="TEST",
        title="Matching synthetic passage",
        text="Synthetic fixture: cloud revenue increased 20 percent during the year.",
    )

    citations = ground_agent_claims(
        in_memory_db,
        symbol="TEST",
        claims=["Cloud revenue increased 20 percent during the year."],
    )

    assert len(citations) == 1
    assert citations[0].claim_type == "context"
    assert citations[0].synthetic is True


def test_bm25_does_not_detect_a_claim_contradicted_by_its_passage(in_memory_db):
    ingest_fixture(
        in_memory_db,
        ticker="TEST",
        title="Contradictory synthetic passage",
        text="Synthetic fixture: cloud revenue declined 20 percent during the year.",
    )

    citations = ground_agent_claims(
        in_memory_db,
        symbol="TEST",
        claims=["Cloud revenue increased 20 percent during the year."],
    )

    assert len(citations) == 1
    assert citations[0].claim_type == "context"
    assert "declined" in citations[0].excerpt


def test_claim_without_a_retrieved_passage_has_no_citation(in_memory_db):
    ingest_fixture(
        in_memory_db,
        ticker="TEST",
        title="Unrelated synthetic passage",
        text="Synthetic fixture: the office lease expires in June.",
    )

    citations = ground_agent_claims(
        in_memory_db,
        symbol="TEST",
        claims=["Quantum processors achieved commercial fusion."],
    )

    assert citations == []


def test_lexically_relevant_passage_is_not_specific_claim_support(in_memory_db):
    ingest_fixture(
        in_memory_db,
        ticker="TEST",
        title="Related but nonsupporting synthetic passage",
        text="Synthetic fixture: cloud revenue is reported by the finance department each quarter.",
    )

    citations = ground_agent_claims(
        in_memory_db,
        symbol="TEST",
        claims=["Cloud revenue doubled after the product launch."],
    )

    assert len(citations) == 1
    assert citations[0].claim_type == "context"
    assert "reported" in citations[0].excerpt


def test_empty_retrieval_returns_no_citations(in_memory_db):
    assert ground_agent_claims(
        in_memory_db,
        symbol="TEST",
        claims=["Cloud revenue increased."],
    ) == []


def test_multiple_passages_return_only_one_context_citation_per_claim(in_memory_db):
    ingest_fixture(
        in_memory_db,
        ticker="TEST",
        title="Supporting synthetic passage",
        text="Synthetic fixture: cloud revenue increased 20 percent in fiscal 2025.",
    )
    ingest_fixture(
        in_memory_db,
        ticker="TEST",
        title="Related nonsupporting synthetic passage",
        text="Synthetic fixture: cloud revenue enterprise migration fiscal 2025 quarterly disclosure.",
    )

    candidates = search_documents(
        in_memory_db,
        query="Cloud revenue increased 20 percent in fiscal 2025.",
        symbol="TEST",
        top_k=5,
    )
    citations = ground_agent_claims(
        in_memory_db,
        symbol="TEST",
        claims=["Cloud revenue increased 20 percent in fiscal 2025."],
    )

    assert len(candidates) == 2
    assert any("increased 20 percent" in result.excerpt for result in candidates)
    assert any("quarterly disclosure" in result.excerpt for result in candidates)
    assert len(citations) == 1
    assert citations[0].claim_type == "context"
    assert citations[0].document_id in {result.document_id for result in candidates}
    assert citations[0].chunk_id
