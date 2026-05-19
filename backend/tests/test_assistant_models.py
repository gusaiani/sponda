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