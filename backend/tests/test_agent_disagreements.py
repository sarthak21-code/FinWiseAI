from app.schemas.intelligence import AgentAssessment
from app.services.intelligence import detect_disagreements


def make_assessment(
    agent_name: str,
    status: str,
    is_demo: bool = False,
) -> AgentAssessment:
    return AgentAssessment(
        agent_name=agent_name,
        status=status,
        summary=f"{agent_name} assessment is {status}.",
        evidence=["Test evidence."],
        limitations=[],
        source="Test source",
        is_demo=is_demo,
    )


def test_opposing_directional_agents_produce_disagreement():
    assessments = [
        make_assessment("Technical Agent", "bullish"),
        make_assessment("Fundamental Agent", "bearish"),
    ]

    disagreements = detect_disagreements(assessments)

    assert len(disagreements) == 1
    assert disagreements[0].agents == [
        "Technical Agent",
        "Fundamental Agent",
    ]
    assert disagreements[0].significance == "high"
    assert "bullish" in disagreements[0].conflict
    assert "bearish" in disagreements[0].conflict


def test_neutral_and_bullish_agents_are_not_direct_conflict():
    assessments = [
        make_assessment("Technical Agent", "neutral"),
        make_assessment("Fundamental Agent", "bullish"),
    ]

    disagreements = detect_disagreements(assessments)

    assert disagreements == []


def test_agents_with_matching_directions_have_no_disagreement():
    assessments = [
        make_assessment("Technical Agent", "bullish"),
        make_assessment("Fundamental Agent", "bullish"),
    ]

    disagreements = detect_disagreements(assessments)

    assert disagreements == []


def test_demo_data_does_not_create_directional_disagreement():
    assessments = [
        make_assessment("Technical Agent", "bullish", is_demo=True),
        make_assessment("Fundamental Agent", "bearish"),
    ]

    disagreements = detect_disagreements(assessments)

    assert disagreements == []


def test_insufficient_data_and_bullish_agents_are_not_direct_conflict():
    assessments = [
        make_assessment("Technical Agent", "bullish"),
        make_assessment("News Sentiment Agent", "insufficient_data"),
    ]

    disagreements = detect_disagreements(assessments)

    assert disagreements == []


def test_unavailable_and_bearish_agents_are_not_direct_conflict():
    assessments = [
        make_assessment("Technical Agent", "bearish"),
        make_assessment("News Sentiment Agent", "unavailable"),
    ]

    disagreements = detect_disagreements(assessments)

    assert disagreements == []


def test_multiple_opposing_agents_produce_all_direct_conflicts():
    assessments = [
        make_assessment("Technical Agent", "bullish"),
        make_assessment("Fundamental Agent", "bearish"),
        make_assessment("News Sentiment Agent", "bullish"),
    ]

    disagreements = detect_disagreements(assessments)

    assert len(disagreements) == 2
    assert all(item.significance == "high" for item in disagreements)
