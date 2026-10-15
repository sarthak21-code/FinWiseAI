import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import yfinance as yf

from app.schemas.news import NewsArticleSummary, NewsSentimentResult


SOURCE = "Yahoo Finance via yfinance Search"
MAX_AGE_DAYS = 14
MIN_ARTICLES = 3

POSITIVE_TERMS = (
    "capitalizes", "growth", "grows", "beat", "beats", "strong",
    "surge", "surges", "record", "profit", "profits", "upgrade",
    "upgraded", "outperform", "bullish", "rally", "rallies",
    "increase", "increases", "improve", "improves", "improved",
    "success", "successful", "opportunity", "opportunities",
    "breakthrough", "innovation", "gain", "gains", "rise",
    "rises", "soar", "soars", "expands", "expansion", "adoption",
)

NEGATIVE_TERMS = (
    "bear market", "bearish", "problem", "decline", "slump",
    "fall", "falls", "drop", "drops", "plunge", "plunges",
    "crash", "weak", "risk", "risks", "loss", "losses", "miss",
    "misses", "downgrade", "downgrades", "overvalued", "sell",
    "cut", "cuts", "threat", "warning", "concern", "concerns",
    "disappoint", "disappoints", "recession", "debt", "lawsuit",
    "probe", "investigation", "negative", "downside", "layoffs",
    "recall", "slowdown", "worse", "worst", "shortfall",
    "pressure", "pressures", "weakness", "deterioration",
)

POSITIVE_PHRASES = (
    "record high",
    "record highs",
    "52-week high",
    "52-week highs",
    "strong growth",
    "beats estimates",
    "beat estimates",
    "raises guidance",
    "raised guidance",
    "strong demand",
    "profit growth",
)

NEGATIVE_PHRASES = (
    "demand pressure",
    "weak demand",
    "bear market",
    "stock market problem",
    "phone threat",
    "valuation pressure",
    "margin pressure",
    "growth slowdown",
    "sales decline",
    "revenue decline",
    "profit warning",
    "cuts guidance",
    "cut guidance",
    "misses estimates",
    "missed estimates",
    "demand weakness",
    "falling demand",
)


def _score_title(title: str) -> tuple[float, str]:
    """Score headline wording using transparent, context-aware heuristics."""

    text = title.lower()

    def matching_terms(terms: tuple[str, ...]) -> list[str]:
        return [
            term
            for term in terms
            if re.search(
                r"(?<!\w)" + re.escape(term) + r"(?!\w)",
                text,
            )
        ]

    positive_hits = matching_terms(POSITIVE_TERMS)
    negative_hits = matching_terms(NEGATIVE_TERMS)
    positive_phrases = matching_terms(POSITIVE_PHRASES)
    negative_phrases = matching_terms(NEGATIVE_PHRASES)

    # Questions alone do not constitute evidence of positive or negative
    # sentiment. Retain a directional label only when an explicit sentiment
    # phrase provides stronger evidence.
    if "?" in title and not positive_phrases and not negative_phrases:
        return 0.0, "neutral"

    # Explicit multi-word phrases carry more weight than isolated words.
    positive_points = (
        0.5 * len(positive_hits)
        + 1.25 * len(positive_phrases)
    )
    negative_points = (
        0.5 * len(negative_hits)
        + 1.5 * len(negative_phrases)
    )

    total_points = positive_points + negative_points

    if total_points == 0:
        return 0.0, "neutral"

    score = (positive_points - negative_points) / total_points
    score = max(-1.0, min(1.0, score))

    if score > 0:
        label = "positive"
    elif score < 0:
        label = "negative"
    else:
        label = "neutral"

    return score, label


COMPANY_ALIASES = {
    "AAPL": (
        "apple",
        "iphone",
        "iphones",
        "ipad",
        "macbook",
        "mac mini",
        "mac studio",
        "siri",
        "apple intelligence",
        "homepod",
        "app store",
        "cupertino",
        "apple tv",
    ),
    "MSFT": ("microsoft", "windows", "azure", "xbox"),
    "NVDA": ("nvidia", "geforce", "cuda", "blackwell"),
    "GOOGL": ("google", "alphabet", "youtube", "android"),
    "GOOG": ("google", "alphabet", "youtube", "android"),
    "AMZN": ("amazon", "aws", "alexa", "prime video"),
    "META": ("meta platforms", "facebook", "instagram", "whatsapp"),
    "TSLA": ("tesla", "cybertruck", "model 3", "model y"),
}


def _title_relevance(
    title: str,
    symbol: str,
    related_tickers: list[str],
) -> float:
    """Separate direct company coverage from contextual mentions."""

    symbol = symbol.upper()
    text = title.lower()

    # A basket headline naming several tickers is contextual coverage,
    # even if the requested ticker appears in the list.
    basket = re.match(
        r"^\s*([A-Z][A-Z0-9.^=-]{0,7}"
        r"(?:\s*,\s*[A-Z][A-Z0-9.^=-]{0,7}){2,})\s+stocks?\b",
        title,
        flags=re.IGNORECASE,
    )

    if basket:
        listed_tickers = {
            item.strip().upper()
            for item in basket.group(1).split(",")
        }

        if symbol in listed_tickers:
            return 0.45

    # An explicit ticker mention outside a multi-stock roundup is strong
    # evidence that the article is relevant to the requested company.
    if re.search(
        r"(?<!\w)" + re.escape(symbol.lower()) + r"(?!\w)",
        text,
    ):
        return 1.0

    aliases = COMPANY_ALIASES.get(symbol, ())

    for alias in aliases:
        escaped = re.escape(alias)

        if not re.search(
            r"(?<!\w)" + escaped + r"(?!\w)",
            text,
        ):
            continue

        # Collaboration, customer, supplier, and deal mentions are
        # contextual unless the headline explicitly covers the company.
        contextual_patterns = (
            rf"\b(?:under|through|via|following|from|by)\s+"
            rf"(?:the\s+)?{escaped}(?:\s+deal)?\b",
            rf"\b{escaped}\s+(?:and|with|alongside)\b",
            rf"\b(?:with|alongside|and)\s+{escaped}\b",
        )

        if any(
            re.search(pattern, text)
            for pattern in contextual_patterns
        ):
            return 0.45

        return 1.0

    if symbol in related_tickers:
        return 0.25

    return 0.10

def _process_articles(
    raw_articles: list[dict[str, Any]],
    symbol: str,
    now: datetime,
) -> tuple[list[NewsArticleSummary], list[str]]:
    """Filter irrelevant, stale and duplicate headlines."""

    symbol = symbol.upper()
    now = now.astimezone(timezone.utc)

    articles: list[NewsArticleSummary] = []
    warnings: list[str] = []
    seen_titles: set[str] = set()
    seen_title_tokens: list[set[str]] = []

    missing_timestamps = False
    stale_articles = False
    unrelated_articles = 0
    duplicate_articles = 0

    title_stop_words = {
        "the", "a", "an", "and", "or", "to", "of", "in", "for",
        "from", "by", "with", "under", "about", "as", "at", "is",
        "are", "will", "has", "have", "on", "its", "their",
        "this", "that", "could", "would", "amid",
    }

    for raw in raw_articles:
        if not isinstance(raw, dict):
            continue

        title = str(raw.get("title") or "").strip()
        if not title:
            continue

        related = raw.get("relatedTickers") or []
        if not isinstance(related, list):
            related = []

        related_tickers = sorted({
            str(ticker).strip().upper()
            for ticker in related
            if ticker
        })

        # Provider ticker metadata is not always an exact match for a
        # requested company. For example, Yahoo Finance can tag Alphabet
        # coverage with GOOG when the requested symbol is GOOGL.
        #
        # Keep articles with an explicit company/ticker reference in the
        # headline, even if the provider's relatedTickers list differs.
        # Continue excluding articles that have neither an exact ticker
        # match nor a direct headline reference to the requested company.
        headline_relevance = _title_relevance(
            title,
            symbol,
            related_tickers,
        )

        has_direct_company_reference = headline_relevance >= 0.45

        if (
            related_tickers
            and symbol not in related_tickers
            and not has_direct_company_reference
        ):
            unrelated_articles += 1
            continue

        try:
            published_at = datetime.fromtimestamp(
                float(raw["providerPublishTime"]),
                tz=timezone.utc,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
            OSError,
        ):
            missing_timestamps = True
            continue

        age = now - published_at

        if age < -timedelta(minutes=10):
            warnings.append(
                "An article with a future publication timestamp was excluded."
            )
            continue

        if age > timedelta(days=MAX_AGE_DAYS):
            stale_articles = True
            continue

        normalized_title = re.sub(
            r"[^a-z0-9]+",
            " ",
            title.lower(),
        ).strip()

        title_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", normalized_title)
            if token not in title_stop_words
        }

        exact_duplicate = normalized_title in seen_titles

        near_duplicate = any(
            len(title_tokens & previous_tokens) >= 6
            and len(title_tokens & previous_tokens)
            / min(len(title_tokens), len(previous_tokens)) >= 0.70
            for previous_tokens in seen_title_tokens
            if title_tokens and previous_tokens
        )

        if exact_duplicate or near_duplicate:
            duplicate_articles += 1
            continue

        seen_titles.add(normalized_title)
        seen_title_tokens.append(title_tokens)

        score, label = _score_title(title)

        relevance = _title_relevance(
            title,
            symbol,
            related_tickers,
        )

        articles.append(
            NewsArticleSummary(
                id=raw.get("uuid"),
                title=title,
                publisher=raw.get("publisher"),
                link=raw.get("link"),
                published_at_utc=published_at,
                sentiment_score=score,
                sentiment_label=label,
                relevance_score=relevance,
                related_tickers=related_tickers,
            )
        )

    if missing_timestamps:
        warnings.append(
            "Some headlines lacked usable publication timestamps and were excluded."
        )

    if stale_articles:
        warnings.append(
            f"Headlines older than {MAX_AGE_DAYS} days were excluded."
        )

    if unrelated_articles:
        warnings.append(
            f"{unrelated_articles} articles unrelated to {symbol} were excluded."
        )

    if duplicate_articles:
        warnings.append(
            f"{duplicate_articles} duplicate or near-duplicate headlines were excluded."
        )

    articles.sort(
        key=lambda article: article.published_at_utc,
        reverse=True,
    )

    return articles[:12], warnings


def _aggregate_sentiment(
    articles: list[NewsArticleSummary],
    now: datetime,
) -> float | None:
    """Aggregate headline scores using freshness and relevance weights."""

    if not articles:
        return None

    now = now.astimezone(timezone.utc)
    weighted_sum = 0.0
    total_weight = 0.0

    for article in articles:
        age_days = max(
            0.0,
            (now - article.published_at_utc).total_seconds() / 86400.0,
        )

        freshness = max(
            0.25,
            1.0 - age_days / MAX_AGE_DAYS,
        )
        weight = freshness * article.relevance_score

        weighted_sum += article.sentiment_score * weight
        total_weight += weight

    if total_weight <= 0:
        return None

    return max(-1.0, min(1.0, weighted_sum / total_weight))


def _unavailable_result(symbol: str) -> NewsSentimentResult:
    return NewsSentimentResult(
        symbol=symbol,
        status="unavailable",
        summary="The news provider could not provide usable data.",
        source=SOURCE,
        fetched_at_utc=datetime.now(timezone.utc),
        limitations=[
            "No directional news assessment could be established."
        ],
        data_warnings=[
            "Yahoo Finance news access may be temporarily unavailable or rate-limited."
        ],
        is_demo=False,
    )


def _fetch_sync(symbol: str) -> NewsSentimentResult:
    now = datetime.now(timezone.utc)

    try:
        result = yf.Search(
            symbol,
            news_count=12,
            max_results=1,
            include_research=False,
        ).search()

        raw_articles = getattr(result, "news", [])
        if not isinstance(raw_articles, list):
            raw_articles = []

        articles, processing_warnings = _process_articles(
            raw_articles,
            symbol,
            now,
        )

    except Exception:
        # Keep provider errors from taking down the intelligence endpoint.
        return _unavailable_result(symbol)

    score = _aggregate_sentiment(articles, now)

    positive_count = sum(
        article.sentiment_label == "positive"
        for article in articles
    )
    negative_count = sum(
        article.sentiment_label == "negative"
        for article in articles
    )
    neutral_count = sum(
        article.sentiment_label == "neutral"
        for article in articles
    )

    direct_count = sum(
        article.relevance_score >= 0.75
        for article in articles
    )
    contextual_count = len(articles) - direct_count

    evidence = [
        f"Analyzed {len(articles)} unique recent headlines: "
        f"{direct_count} directly relevant and "
        f"{contextual_count} contextual or weakly related.",
        (
            f"Headline labels: {positive_count} positive, "
            f"{negative_count} negative, {neutral_count} neutral."
        ),
    ]

    if score is not None:
        evidence.append(
            f"Weighted headline sentiment score: {score:+.3f} "
            "(range: -1 negative to +1 positive)."
        )

    limitations = [
        "Sentiment uses headlines, not full article text.",
        "The word-list heuristic can miss context, negation, sarcasm and speculation.",
        "Yahoo Finance is an unofficial data interface; availability can change.",
        "This assessment is informational, not personalized investment advice.",
    ]

    warnings = [
        "Headline sentiment is a prototype heuristic, not a validated prediction model."
    ]
    warnings.extend(processing_warnings)

    if direct_count < MIN_ARTICLES:
        return NewsSentimentResult(
            symbol=symbol,
            status="insufficient_data",
            summary=(
                f"Only {direct_count} directly relevant recent headlines "
                f"were found out of {len(articles)} usable recent headlines; "
                f"at least {MIN_ARTICLES} directly relevant headlines are "
                "required for a directional assessment."
            ),
            evidence=evidence,
            limitations=limitations,
            source=SOURCE,
            fetched_at_utc=now,
            sentiment_score=score,
            articles=articles,
            data_warnings=warnings,
            is_demo=False,
        )

    if score is not None and score >= 0.15:
        status = "bullish"
        summary = (
            "Recent headlines have a positive net signal under the configured "
            "headline-scoring rules."
        )
    elif score is not None and score <= -0.15:
        status = "bearish"
        summary = (
            "Recent headlines have a negative net signal under the configured "
            "headline-scoring rules."
        )
    else:
        status = "neutral"
        summary = (
            "Recent headlines show mixed or weak directional sentiment under "
            "the configured headline-scoring rules."
        )

    return NewsSentimentResult(
        symbol=symbol,
        status=status,
        summary=summary,
        evidence=evidence,
        limitations=limitations,
        source=SOURCE,
        fetched_at_utc=now,
        sentiment_score=score,
        articles=articles,
        data_warnings=warnings,
        is_demo=False,
    )


async def analyze_news_sentiment(
    raw_symbol: str,
) -> NewsSentimentResult:
    """Fetch news without blocking FastAPI's event loop."""

    symbol = raw_symbol.strip().upper()

    if not symbol or len(symbol) > 24:
        raise ValueError("Provide a valid ticker symbol.")

    if not all(char.isalnum() or char in ".-^=" for char in symbol):
        raise ValueError("Ticker symbol contains invalid characters.")

    return await asyncio.to_thread(_fetch_sync, symbol)
