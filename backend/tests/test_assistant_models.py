import pytest
from django.contrib.auth import get_user_model

from assistant.models import LLMQuery

User = get_user_model()


@pytest.mark.django_db
def test_llmquery_persists_core_fields():
    """A query row records who asked, about which ticker, and cost/usage."""
    user = User.objects.create_user(
        username="g@example.com", email="g@example.com", password="pw123456"
    )
    query = LLMQuery.objects.create(
        user=user,
        ticker="PETR4",
        question="Is PETR4 cheap on PE10?",
        classification="on_topic",
        model="gpt-4o",
        input_tokens=900,
        output_tokens=120,
        cost_usd="0.003600",
        latency_ms=1840,
        status="ok",
    )

    assert query.pk is not None
    assert query.user == user
    assert query.created_at is not None


@pytest.mark.django_db
def test_llmquery_default_feature_is_ask():
    """Every existing row (and any caller that doesn't pass `feature`)
    is an `ask` query - the screening feature is opt-in, not a silent
    reclassification of the whole eval corpus.
    """
    query = LLMQuery.objects.create(
        ticker="PETR4",
        question="Is PETR4 cheap on PE10?",
        classification="on_topic",
    )

    assert query.feature == "ask"


@pytest.mark.django_db
def test_llmquery_screen_feature_allows_blank_ticker_with_filters():
    """Screening queries answer 'which companies match?', not 'tell me
    about ticker X' - there is no single ticker to attach, so `ticker`
    must be omittable, and the parsed filter set is stored for the eval
    corpus instead.
    """
    interpreted_filters = {"pe10_max": 10, "sector": "Energy"}
    query = LLMQuery.objects.create(
        feature="screen",
        ticker="",
        question="Which cheap energy companies pay a good dividend?",
        classification="on_topic",
        interpreted_filters=interpreted_filters,
    )

    assert query.pk is not None
    assert query.feature == "screen"
    assert query.ticker == ""
    assert query.interpreted_filters == interpreted_filters