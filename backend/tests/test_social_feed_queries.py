"""Query-count regression tests for the social feed.

Sentry flagged ``/api/social/feed/global/`` as an N+1 (WEB-DJANGO-16): a
single page of 25 Sponds fired 40+ repeated statements and took 548ms to
render. ``_annotate_sponds`` already annotated the counts, so the queries
had to be coming from the serializer, and they were:

* ``get_like_count`` and ``get_reply_count`` passed the fallback query as
  ``getattr``'s default argument. Python evaluates arguments before the
  call, so the COUNT ran on every row even though the annotation existed
  and its value was the one returned.
* ``get_viewer_has_liked`` ran an ``EXISTS`` per row.
* ``get_handle_mentions`` called ``.select_related()`` on the related
  manager, which builds a fresh queryset and so ignores the
  ``prefetch_related`` the view had already paid for.

These tests pin the cost so none of the four can come back unnoticed: the
query count must not grow with the number of Sponds in the page.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from social.models import Spond, SpondLike, SpondMention


User = get_user_model()


def _make_user(email):
    return User.objects.create_user(
        username=email, email=email, password="x",
        handle=email.split("@")[0], email_verified=True,
    )


@pytest.fixture
def author(db):
    return _make_user("author@x.com")


@pytest.fixture
def viewer(db):
    return _make_user("viewer@x.com")


def _populate_feed(author, viewer, *, spond_count):
    """Create ``spond_count`` Sponds, each with a like, a reply and a mention.

    Every relation the serializer touches is present on every row, so a
    per-row query shows up as a count that scales with ``spond_count``.
    """
    for index in range(spond_count):
        spond = Spond.objects.create(author=author, body=f"spond {index}")
        SpondLike.objects.create(user=viewer, spond=spond)
        Spond.objects.create(author=author, body=f"reply {index}", parent=spond)
        SpondMention.objects.create(spond=spond, mentioned_user=viewer)


def _count_queries(client, url, django_assert_num_queries):
    """Return the number of queries the request issues, and its payload."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)
    assert response.status_code == 200
    return len(captured), response.json()


@pytest.mark.django_db
def test_global_feed_query_count_does_not_grow_with_page_size(author, viewer):
    """The whole point: adding Sponds must not add queries.

    Two feeds, one with three Sponds and one with twelve, must cost the
    same. Before the serializer fix the second cost roughly four extra
    queries per extra Spond.
    """
    client = Client()
    client.force_login(viewer)

    _populate_feed(author, viewer, spond_count=3)
    small_count, small_body = _count_queries(
        client, "/api/social/feed/global/", None,
    )
    assert len(small_body["results"]) == 3

    _populate_feed(author, viewer, spond_count=9)
    large_count, large_body = _count_queries(
        client, "/api/social/feed/global/", None,
    )
    assert len(large_body["results"]) == 12

    assert large_count == small_count, (
        f"feed queries scale with page size: {small_count} queries for 3 "
        f"Sponds, {large_count} for 12. The serializer is querying per row."
    )


@pytest.mark.django_db
def test_global_feed_still_reports_correct_counts(author, viewer):
    """Guard the fix: cheaper must not mean wrong."""
    client = Client()
    client.force_login(viewer)
    _populate_feed(author, viewer, spond_count=2)

    response = client.get("/api/social/feed/global/")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2

    for entry in results:
        assert entry["like_count"] == 1
        assert entry["reply_count"] == 1
        assert entry["viewer_has_liked"] is True
        assert entry["handle_mentions"] == ["viewer"]


@pytest.mark.django_db
def test_viewer_has_liked_is_false_for_other_viewers(author, viewer):
    """The like annotation must be scoped to the requesting user."""
    stranger = _make_user("stranger@x.com")
    _populate_feed(author, viewer, spond_count=2)

    client = Client()
    client.force_login(stranger)
    response = client.get("/api/social/feed/global/")

    assert response.status_code == 200
    for entry in response.json()["results"]:
        assert entry["viewer_has_liked"] is False
        assert entry["like_count"] == 1


@pytest.mark.django_db
def test_anonymous_feed_reports_no_viewer_like(author, viewer):
    """Anonymous viewers get ``False`` without any per-row lookup."""
    _populate_feed(author, viewer, spond_count=2)

    response = Client().get("/api/social/feed/global/")

    assert response.status_code == 200
    for entry in response.json()["results"]:
        assert entry["viewer_has_liked"] is False
