"""Tests for the read-only McpCall Django admin.

The admin dashboard shows 30-day aggregates mined from ``McpCall`` rows;
this admin page is the raw-row browser behind it — filterable by tool and
date, with the recorded arguments JSON visible. It is strictly read-only:
the table is an audit log written by the MCP endpoint, and a hand-edited
audit row is worse than no row.
"""
import pytest
from django.contrib import admin
from django.utils import timezone

from assistant.models import McpCall

CHANGELIST_URL = "/admin/assistant/mcpcall/"


def record_screen_call(**overrides):
    fields = {
        "method": "tools/call",
        "tool_name": "screen_companies",
        "ip_hash": "a" * 64,
        "user_agent": "Claude-User/1.0",
        "arguments": {"filters": {"pe10": {"max": 10}}, "country": "BR"},
        "result_count": 42,
    }
    fields.update(overrides)
    return McpCall.objects.create(**fields)


class TestRegistration:
    def test_mcpcall_is_registered(self):
        assert McpCall in admin.site._registry

    def test_list_shows_the_columns_that_identify_a_call(self):
        list_display = admin.site._registry[McpCall].list_display
        for field in ("timestamp", "method", "tool_name", "result_count",
                      "failed", "rate_limited", "latency_ms"):
            assert field in list_display

    def test_list_is_filterable_by_tool_and_outcome(self):
        list_filter = admin.site._registry[McpCall].list_filter
        for field in ("method", "tool_name", "failed", "rate_limited"):
            assert field in list_filter

    def test_list_is_navigable_by_date(self):
        assert admin.site._registry[McpCall].date_hierarchy == "timestamp"


@pytest.mark.django_db
class TestReadOnly:
    """Audit rows can be looked at, never created, edited, or deleted."""

    def test_add_change_and_delete_are_all_denied(self, superuser_client):
        model_admin = admin.site._registry[McpCall]
        request = superuser_client.get(CHANGELIST_URL).wsgi_request

        assert model_admin.has_add_permission(request) is False
        assert model_admin.has_change_permission(request) is False
        assert model_admin.has_delete_permission(request) is False

    def test_detail_page_is_viewable(self, superuser_client):
        call = record_screen_call()
        response = superuser_client.get(f"{CHANGELIST_URL}{call.pk}/change/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestChangelist:
    def test_renders_recorded_calls(self, superuser_client):
        record_screen_call()
        response = superuser_client.get(CHANGELIST_URL)

        assert response.status_code == 200
        assert b"screen_companies" in response.content

    def test_detail_page_shows_the_arguments_json(self, superuser_client):
        call = record_screen_call()
        response = superuser_client.get(f"{CHANGELIST_URL}{call.pk}/change/")

        assert b"pe10" in response.content

    def test_filters_by_tool_name(self, superuser_client):
        record_screen_call()
        record_screen_call(tool_name="get_company",
                           arguments={"symbol": "WEGE3"}, result_count=None)

        response = superuser_client.get(
            CHANGELIST_URL, {"tool_name": "get_company"}
        )

        assert response.status_code == 200
        listed_tools = [
            call.tool_name for call in response.context["cl"].result_list
        ]
        assert listed_tools == ["get_company"]
