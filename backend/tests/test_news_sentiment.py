from datetime import datetime, timedelta, timezone

from app.services.news_sentiment import (
    _process_articles,
    _score_title,
)


def test_positive_headline_has_positive_score():
    score, label = _score_title(
        "Apple capitalizes on strong growth and innovation"
    )

    assert score > 0
    assert label == "positive"


def test_negative_headline_has_negative_score():
    score, label = _score_title(
        "Stock market problem as shares face a bear market"
    )

    assert score < 0
    assert label == "negative"


def test_headline_without_sentiment_cues_is_neutral():
    score, label = _score_title(
        "Apple announces a new product lineup"
    )

    assert score == 0
    assert label == "neutral"


def test_article_processor_filters_unrelated_and_duplicate_headlines():
    now = datetime.now(timezone.utc)
    timestamp = int((now - timedelta(hours=2)).timestamp())

    raw_articles = [
        {
            "uuid": "first",
            "title": "Apple reports strong growth",
            "publisher": "Publisher A",
            "link": "https://example.com/apple-growth",
            "providerPublishTime": timestamp,
            "relatedTickers": ["AAPL"],
        },
        {
            "uuid": "duplicate",
            "title": "Apple reports strong growth",
            "publisher": "Publisher B",
            "link": "https://example.com/duplicate",
            "providerPublishTime": timestamp,
            "relatedTickers": ["AAPL"],
        },
        {
            "uuid": "unrelated",
            "title": "A different company reports a loss",
            "publisher": "Publisher C",
            "link": "https://example.com/other",
            "providerPublishTime": timestamp,
            "relatedTickers": ["MSFT"],
        },
    ]

    articles, _ = _process_articles(raw_articles, "AAPL", now)

    assert len(articles) == 1
    assert articles[0].id == "first"
    assert articles[0].sentiment_label == "positive"


def test_article_processor_excludes_old_headlines():
    now = datetime.now(timezone.utc)

    raw_articles = [
        {
            "uuid": "old",
            "title": "Apple reports strong growth",
            "publisher": "Publisher A",
            "link": "https://example.com/old",
            "providerPublishTime": int(
                (now - timedelta(days=30)).timestamp()
            ),
            "relatedTickers": ["AAPL"],
        }
    ]

    articles, warnings = _process_articles(raw_articles, "AAPL", now)

    assert articles == []
    assert any("older than" in warning for warning in warnings)


def test_demand_pressure_headline_is_negative():
    title = (
        "Apple (AAPL) Faces iPhone Demand Pressure. "
        "Can Its Growth Justify the Premium?"
    )

    score, label = _score_title(title)

    assert label == "negative"
    assert score < 0


def test_question_about_buying_a_stock_is_not_automatically_positive():
    score, label = _score_title(
        "Is Apple Stock a Buy During the Holiday Quarter?"
    )

    assert score == 0
    assert label == "neutral"
from datetime import datetime, timezone

from app.services.news_sentiment import _process_articles


def test_general_market_headline_is_contextual_for_aapl():
    now = datetime.now(timezone.utc)

    articles, _ = _process_articles(
        [
            {
                "uuid": "market-news",
                "title": (
                    "Three Weeks Before The Midterms, "
                    "The Stock Market Problem Is Already Here"
                ),
                "publisher": "Example Publisher",
                "link": "https://example.com/market",
                "providerPublishTime": int(now.timestamp()),
                "relatedTickers": ["AAPL", "NVDA", "META"],
            }
        ],
        "AAPL",
        now,
    )

    assert len(articles) == 1
    assert articles[0].relevance_score == 0.25


def test_direct_apple_headline_receives_high_relevance():
    now = datetime.now(timezone.utc)

    articles, _ = _process_articles(
        [
            {
                "uuid": "apple-news",
                "title": "Apple Reports Strong Revenue Growth",
                "publisher": "Example Publisher",
                "link": "https://example.com/apple",
                "providerPublishTime": int(now.timestamp()),
                "relatedTickers": ["AAPL"],
            }
        ],
        "AAPL",
        now,
    )

    assert len(articles) == 1
    assert articles[0].relevance_score == 1.0


def test_buying_iphones_is_not_automatically_positive():
    score, label = _score_title(
        "Elon Musk's SpaceX could change how Americans buy iPhones"
    )

    assert score == 0
    assert label == "neutral"


def test_googl_articles_survive_ticker_metadata_mismatch():
    now = datetime.now(timezone.utc)
    timestamp = int((now - timedelta(hours=2)).timestamp())

    raw_articles = [
        {
            "uuid": "googl-news-1",
            "title": "GOOGL Stock Gets a New Analyst Price Target",
            "publisher": "Example Publisher",
            "link": "https://example.com/googl-target",
            "providerPublishTime": timestamp,
            "relatedTickers": ["GOOG"],
        },
        {
            "uuid": "googl-news-2",
            "title": "Alphabet Expands Its Artificial Intelligence Business",
            "publisher": "Example Publisher",
            "link": "https://example.com/alphabet-ai",
            "providerPublishTime": timestamp,
            "relatedTickers": ["GOOG"],
        },
        {
            "uuid": "googl-news-3",
            "title": "Google Announces New Cloud Products",
            "publisher": "Example Publisher",
            "link": "https://example.com/google-cloud",
            "providerPublishTime": timestamp,
            "relatedTickers": ["GOOG"],
        },
        {
            "uuid": "unrelated-news",
            "title": "GSK Plans Job Cuts in Belgium",
            "publisher": "Example Publisher",
            "link": "https://example.com/gsk",
            "providerPublishTime": timestamp,
            "relatedTickers": ["GOOG"],
        },
    ]

    articles, warnings = _process_articles(
        raw_articles,
        "GOOGL",
        now,
    )

    assert len(articles) == 3
    assert {article.id for article in articles} == {
        "googl-news-1",
        "googl-news-2",
        "googl-news-3",
    }

    assert all(
        article.relevance_score >= 0.75
        for article in articles
    )

    assert any("1 articles unrelated" in warning for warning in warnings)


def test_google_collaboration_is_contextual():
    from app.services.news_sentiment import _title_relevance

    score = _title_relevance(
        "GoDaddy, Infoblox, Google and Cloudflare Demonstrate Secure AI Agent Transactions",
        "GOOGL",
        ["GOOG"],
    )

    assert score == 0.45


def test_google_deal_mention_is_contextual():
    from app.services.news_sentiment import _title_relevance

    score = _title_relevance(
        "American Electric Power to Invest in a Project Under Google Deal",
        "GOOGL",
        ["GOOG"],
    )

    assert score == 0.45


def test_alphabet_price_target_is_directly_relevant():
    from app.services.news_sentiment import _title_relevance

    score = _title_relevance(
        "UBS Adjusts Price Target on Alphabet to $380",
        "GOOGL",
        ["GOOG"],
    )

    assert score == 1.0


def test_multi_ticker_roundup_is_contextual_for_googl():
    from app.services.news_sentiment import _title_relevance

    score = _title_relevance(
        "META, TTD, SNAP, GOOGL, BMBL, WDAY Stocks Get New UBS Targets Amid AI And Ad Shifts",
        "GOOGL",
        ["META", "TTD", "SNAP", "GOOG", "BMBL", "WDAY"],
    )

    assert score == 0.45


def test_near_duplicate_google_deal_headlines_are_deduplicated():
    now = datetime.now(timezone.utc)
    timestamp = int((now - timedelta(hours=2)).timestamp())

    raw_articles = [
        {
            "uuid": "aep-1",
            "title": (
                "American Electric Power to Invest $4 Billion in Fuel Cell "
                "Project to Meet Energy Demand From Google"
            ),
            "publisher": "Publisher A",
            "link": "https://example.com/aep-one",
            "providerPublishTime": timestamp,
            "relatedTickers": ["AEP", "GOOG"],
        },
        {
            "uuid": "aep-2",
            "title": (
                "American Electric Power to Invest About $4 Billion in Fuel "
                "Cell Generation Project Under Google Deal"
            ),
            "publisher": "Publisher B",
            "link": "https://example.com/aep-two",
            "providerPublishTime": timestamp,
            "relatedTickers": ["AEP", "GOOG"],
        },
    ]

    articles, warnings = _process_articles(
        raw_articles,
        "GOOGL",
        now,
    )

    assert len(articles) == 1
    assert any("duplicate or near-duplicate" in warning for warning in warnings)
