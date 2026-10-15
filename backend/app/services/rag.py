import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import DocumentChunk, FinancialDocument
from app.schemas.rag import DocumentSearchResult, GroundedCitation


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(
    text: str,
    target_words: int = 150,
    overlap_words: int = 30,
) -> list[tuple[str, str]]:
    """Split text into structured chunks preserving section headings.
    Returns list of (section_name, chunk_text).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[tuple[str, str]] = []
    current_section = "General Overview"
    current_words: list[str] = []

    for para in paragraphs:
        # Check if paragraph looks like a section header
        if para.startswith("#") or (len(para) < 80 and para.endswith(":") or para.isupper()):
            if current_words:
                chunks.append((current_section, " ".join(current_words)))
                current_words = []
            current_section = para.strip("# :")
            continue

        words = para.split()
        if not words:
            continue

        if len(current_words) + len(words) > target_words and current_words:
            chunks.append((current_section, " ".join(current_words)))
            # Keep overlap
            current_words = current_words[-overlap_words:] if overlap_words < len(current_words) else []

        current_words.extend(words)

    if current_words:
        chunks.append((current_section, " ".join(current_words)))

    return chunks


def ingest_document(
    db: Session,
    issuer: str,
    ticker: str,
    title: str,
    document_type: str,
    reporting_period: str,
    published_at: datetime,
    raw_content: str,
    source_name: str = "Official SEC Filing",
    source_url: Optional[str] = None,
    synthetic: bool = False,
) -> FinancialDocument:
    """Ingest a financial document with chunking and duplicate prevention."""
    content_hash = compute_content_hash(raw_content)

    existing = db.execute(
        select(FinancialDocument).where(FinancialDocument.content_hash == content_hash)
    ).scalar_one_or_none()

    if existing:
        # Keep provenance corrections idempotent for databases seeded by older versions.
        existing.issuer = issuer
        existing.ticker = ticker.upper()
        existing.title = title
        existing.document_type = document_type
        existing.reporting_period = reporting_period
        existing.published_at = published_at
        existing.source_name = source_name
        existing.source_url = source_url
        existing.synthetic = synthetic
        db.commit()
        return existing

    doc = FinancialDocument(
        issuer=issuer,
        ticker=ticker.upper(),
        title=title,
        document_type=document_type,
        reporting_period=reporting_period,
        published_at=published_at,
        source_name=source_name,
        source_url=source_url,
        content_hash=content_hash,
        synthetic=synthetic,
        raw_content=raw_content,
    )
    db.add(doc)
    db.flush()

    raw_chunks = chunk_text(raw_content)
    for idx, (section, chunk_content) in enumerate(raw_chunks):
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=idx,
            section=section,
            text=chunk_content,
            token_count=len(chunk_content.split()),
        )
        db.add(chunk)

    db.commit()
    db.refresh(doc)
    return doc


def tokenize(text: str) -> list[str]:
    """Basic lexical tokenizer with stopword removal."""
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
        "with", "by", "from", "up", "about", "into", "over", "after", "is", "are",
        "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
        "did", "will", "would", "shall", "should", "may", "might", "must", "can",
        "could", "it", "its", "that", "this", "these", "those", "as", "if", "than",
    }
    words = re.findall(r"\b[A-Za-z0-9_]{2,}\b", text.lower())
    return [w for w in words if w not in stopwords]


def search_documents(
    db: Session,
    query: str,
    symbol: Optional[str] = None,
    top_k: int = 5,
) -> list[DocumentSearchResult]:
    """Ranked BM25 lexical retrieval across financial document chunks."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    stmt = select(DocumentChunk, FinancialDocument).join(
        FinancialDocument, DocumentChunk.document_id == FinancialDocument.id
    )

    if symbol:
        clean_sym = symbol.strip().upper()
        stmt = stmt.where(
            (FinancialDocument.ticker == clean_sym) | (FinancialDocument.ticker == "MARKET")
        )

    rows = db.execute(stmt).all()
    if not rows:
        return []

    # Total corpus size
    total_docs = len(rows)
    # Compute document frequencies
    doc_freq: dict[str, int] = {}
    chunk_tokens_map: dict[str, list[str]] = {}

    for chunk, _ in rows:
        c_tokens = tokenize(chunk.text)
        chunk_tokens_map[chunk.id] = c_tokens
        unique_tokens = set(c_tokens)
        for t in query_tokens:
            if t in unique_tokens:
                doc_freq[t] = doc_freq.get(t, 0) + 1

    avg_len = sum(len(toks) for toks in chunk_tokens_map.values()) / max(1, total_docs)
    k1 = 1.5
    b = 0.75

    scored: list[tuple[float, DocumentChunk, FinancialDocument]] = []

    for chunk, doc in rows:
        c_tokens = chunk_tokens_map[chunk.id]
        c_len = len(c_tokens)
        if c_len == 0:
            continue

        score = 0.0
        token_counts: dict[str, int] = {}
        for tok in c_tokens:
            token_counts[tok] = token_counts.get(tok, 0) + 1

        matched_tokens = 0
        for q_tok in query_tokens:
            if q_tok in token_counts:
                matched_tokens += 1
                tf = token_counts[q_tok]
                df = doc_freq.get(q_tok, 1)
                idf = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))
                denom = tf + k1 * (1.0 - b + b * (c_len / avg_len))
                score += idf * ((tf * (k1 + 1.0)) / max(1e-5, denom))

        if matched_tokens > 0:
            # Boost ticker matches when content is relevant
            if symbol and doc.ticker.upper() == symbol.strip().upper():
                score += 0.5
            if score > 0.1:
                scored.append((score, chunk, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[DocumentSearchResult] = []
    for score, chunk, doc in scored[:top_k]:
        # Formulate a clean excerpt
        excerpt = chunk.text
        if len(excerpt) > 280:
            excerpt = excerpt[:277] + "..."

        results.append(
            DocumentSearchResult(
                document_id=doc.id,
                chunk_id=chunk.id,
                document_title=doc.title,
                issuer=doc.issuer,
                ticker=doc.ticker,
                document_type=doc.document_type,
                reporting_period=doc.reporting_period,
                published_at=doc.published_at,
                source_name=doc.source_name,
                source_url=doc.source_url,
                relevance_score=round(float(score), 3),
                excerpt=excerpt,
                synthetic=doc.synthetic,
            )
        )

    return results


def ground_agent_claims(
    db: Session,
    symbol: str,
    claims: list[str],
) -> list[GroundedCitation]:
    """Ground agent assertions into retrieved financial document passages."""
    citations: list[GroundedCitation] = []
    seen_chunks = set()

    for claim in claims:
        search_results = search_documents(db, query=claim, symbol=symbol, top_k=2)
        for r in search_results:
            if r.chunk_id in seen_chunks:
                continue
            seen_chunks.add(r.chunk_id)

            citations.append(
                GroundedCitation(
                    claim=claim,
                    # Lexical relevance finds related text; it does not establish
                    # that the passage proves the claim.
                    claim_type="context",
                    document_id=r.document_id,
                    chunk_id=r.chunk_id,
                    document_title=r.document_title,
                    issuer=r.issuer,
                    ticker=r.ticker,
                    reporting_period=r.reporting_period,
                    excerpt=r.excerpt,
                    relevance_score=r.relevance_score,
                    synthetic=r.synthetic,
                    source_name=r.source_name,
                    source_url=r.source_url,
                )
            )
            break  # Top 1 citation per claim

    return citations


def seed_demonstration_corpus(db: Session) -> int:
    """Seed clearly labeled synthetic filing-style passages for demonstrations."""
    docs_to_seed = [
        {
            "issuer": "Apple Inc.",
            "ticker": "AAPL",
            "title": "Synthetic Apple financial disclosure scenario (10-K style)",
            "document_type": "Synthetic demonstration",
            "reporting_period": "Synthetic scenario; not a filed period",
            "published_at": datetime(2025, 11, 1, 0, 0, tzinfo=timezone.utc),
            "source_name": "VantageAI synthetic demonstration corpus",
            "source_url": None,
            "synthetic": True,
            "raw_content": (
                "# Business and Segment Performance\n\n"
                "Total net sales increased 6% or $22.6 billion during fiscal 2025 compared to fiscal 2024, "
                "driven by growth in Services and iPhone revenue. Services revenue reached an all-time record "
                "of $96.2 billion, supported by expanded active installed base of devices across all geographic segments.\n\n"
                "# Gross Margin and Capital Allocation\n\n"
                "Gross margin was 46.2%, compared to 44.1% in fiscal 2024. The expansion reflected strength in Services "
                "and favorable component cost dynamics. Operating cash flow stood at $118.3 billion, enabling $95 billion "
                "in share repurchases and $15.2 billion in dividend payouts to shareholders.\n\n"
                "# Risk Factors and Regulatory Pressures\n\n"
                "The Company remains subject to complex, changing antitrust and digital market regulations in the European "
                "Union and United States regarding App Store billing rules and platform interoperability requirements, "
                "which could impact commission structures and service monetization."
            ),
        },
        {
            "issuer": "Microsoft Corporation",
            "ticker": "MSFT",
            "title": "Synthetic Microsoft financial disclosure scenario (10-Q style)",
            "document_type": "Synthetic demonstration",
            "reporting_period": "Synthetic scenario; not a filed period",
            "published_at": datetime(2026, 1, 28, 0, 0, tzinfo=timezone.utc),
            "source_name": "VantageAI synthetic demonstration corpus",
            "source_url": None,
            "synthetic": True,
            "raw_content": (
                "# Intelligent Cloud Segment Performance\n\n"
                "Intelligent Cloud revenue was $29.8 billion, increasing 20% year-over-year. Azure and other cloud services "
                "revenue grew 29%, driven by accelerated commercial enterprise migration and hyperscale AI workload adoption.\n\n"
                "# Capital Expenditures and Infrastructure Capacity\n\n"
                "Capital expenditures including assets acquired under finance leases were $14.5 billion, supporting surging "
                "demand for cloud computing and specialized artificial intelligence infrastructure across North America and Europe.\n\n"
                "# Balance Sheet and Operating Profitability\n\n"
                "Operating income increased 17% to $27.0 billion. Cash and short-term investments totaled $80.2 billion. "
                "Management notes power grid constraints and semiconductor delivery lead times as pacing factors for data center capacity additions."
            ),
        },
        {
            "issuer": "NVIDIA Corporation",
            "ticker": "NVDA",
            "title": "Synthetic NVIDIA financial disclosure scenario (10-K style)",
            "document_type": "Synthetic demonstration",
            "reporting_period": "Synthetic scenario; not a filed period",
            "published_at": datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc),
            "source_name": "VantageAI synthetic demonstration corpus",
            "source_url": None,
            "synthetic": True,
            "raw_content": (
                "# Compute and Networking Revenue\n\n"
                "Compute and Networking revenue surged 135% year-over-year, driven by extraordinary demand for Hopper and Blackwell "
                "GPU architectures from cloud service providers, sovereign AI initiatives, and frontier model developers.\n\n"
                "# Gross Margin and Supply Chain Dependencies\n\n"
                "Gross margin expanded to 75.1% compared to 72.7% in the prior year. The Company relies heavily on single-source "
                "advanced packaging (CoWoS) and foundry partners, particularly Taiwan Semiconductor Manufacturing Company (TSMC).\n\n"
                "# Export Controls and Geopolitical Risks\n\n"
                "United States export control regulations restrict shipment of certain high-performance compute chips to China and "
                "other designated jurisdictions. While custom compliant architectures were developed, competitive dynamics in restricted "
                "markets remain constrained."
            ),
        },
        {
            "issuer": "Alphabet Inc.",
            "ticker": "GOOGL",
            "title": "Synthetic Alphabet financial disclosure scenario (10-K style)",
            "document_type": "Synthetic demonstration",
            "reporting_period": "Synthetic scenario; not a filed period",
            "published_at": datetime(2025, 2, 5, 0, 0, tzinfo=timezone.utc),
            "source_name": "VantageAI synthetic demonstration corpus",
            "source_url": None,
            "synthetic": True,
            "raw_content": (
                "# Google Search and Advertising Disclosures\n\n"
                "Google Services revenue increased 12% to $265.8 billion, led by Google Search query volume growth and retail advertiser spend. "
                "YouTube advertising revenue rose 14% to $36.1 billion reflecting brand advertising momentum.\n\n"
                "# Google Cloud Profitability Milestone\n\n"
                "Google Cloud revenue reached $43.2 billion with operating profit reaching $4.8 billion, marking sustained operating leverage "
                "and expansion of enterprise Gemini model API deployments.\n\n"
                "# Antitrust Remediation Risk Factors\n\n"
                "Ongoing legal proceedings with the United States Department of Justice regarding search distribution agreements and ad-tech "
                "monopolization could result in structural remedies or restrictions on default browser distribution contracts."
            ),
        },
        {
            "issuer": "Tesla, Inc.",
            "ticker": "TSLA",
            "title": "Synthetic Tesla financial disclosure scenario (10-K style)",
            "document_type": "Synthetic demonstration",
            "reporting_period": "Synthetic scenario; not a filed period",
            "published_at": datetime(2025, 1, 30, 0, 0, tzinfo=timezone.utc),
            "source_name": "VantageAI synthetic demonstration corpus",
            "source_url": None,
            "synthetic": True,
            "raw_content": (
                "# Automotive Vehicle Deliveries and Pricing Pressure\n\n"
                "Total automotive revenues reached $82.4 billion. Automotive gross margin excluding regulatory credits was 16.4%, "
                "impacted by global price cuts, aggressive EV price competition in China, and customer financing incentives.\n\n"
                "# Energy Storage and Megapack Expansion\n\n"
                "Energy generation and storage revenues doubled to $12.1 billion with gross profit exceeding 28%, driven by rapid deployment "
                "of Megapack utility-scale battery installations globally.\n\n"
                "# Full Self-Driving and Autonomous Fleet Uncertainty\n\n"
                "Commercial deployment of Cybercab and unsupervised Full Self-Driving technology remains dependent upon regulatory approvals, "
                "fleet validation miles, and unresolved safety liability frameworks across municipal jurisdictions."
            ),
        },
        {
            "issuer": "Synthetic Demo Scenario Corp",
            "ticker": "DEMO",
            "title": "SYNTHETIC DEMO: Stress Test Scenario Filing for Degraded Data Analysis",
            "document_type": "Synthetic 8-K",
            "reporting_period": "Demo Simulation 2026",
            "published_at": datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
            "source_name": "Synthetic Hackathon Demonstration Corpus",
            "source_url": None,
            "synthetic": True,
            "raw_content": (
                "# SYNTHETIC DEMONSTRATION NOTICE\n\n"
                "THIS IS A SYNTHETIC SIMULATION DOCUMENT PREPARED STRICTLY FOR TESTING AND DEMONSTRATING "
                "THE VANTAGEAI RETRIEVAL AND DISAGREEMENT PIPELINE. IT DOES NOT REPRESENT ANY REAL-WORLD COMPANY.\n\n"
                "# Simulated Supply Chain Disruption\n\n"
                "Synthetic testing notes a 40% component shortage across Tier-1 suppliers, creating a sharp divergence "
                "between optimistic technical price trends and deteriorating physical fulfillment capacity.\n\n"
                "# Simulated Agent Stress Testing\n\n"
                "This document is indexed to test multi-agent disagreement handling where news/filing evidence directly "
                "contradicts short-term technical momentum."
            ),
        },
    ]

    count = 0
    for doc in docs_to_seed:
        ingest_document(
            db=db,
            issuer=doc["issuer"],
            ticker=doc["ticker"],
            title=doc["title"],
            document_type=doc["document_type"],
            reporting_period=doc["reporting_period"],
            published_at=doc["published_at"],
            raw_content=doc["raw_content"],
            source_name=doc["source_name"],
            source_url=doc["source_url"],
            synthetic=doc["synthetic"],
        )
        count += 1

    return count
