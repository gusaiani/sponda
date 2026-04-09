"""Tests for company analysis model, API endpoint, and import command."""
import json
import tempfile

import pytest
from django.test import Client

from quotes.models import CompanyAnalysis


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def sample_analysis():
    return CompanyAnalysis.objects.create(
        ticker="PETR4",
        content="A Petrobras apresenta fundamentos sólidos ao longo dos últimos 10 anos.",
        data_quarter="2025-Q4",
    )


@pytest.mark.django_db
class TestCompanyAnalysisModel:
    def test_create_analysis(self):
        analysis = CompanyAnalysis.objects.create(
            ticker="VALE3",
            content="Análise da Vale.",
            data_quarter="2025-Q4",
        )
        assert analysis.ticker == "VALE3"
        assert analysis.content == "Análise da Vale."
        assert analysis.data_quarter == "2025-Q4"
        assert analysis.generated_at is not None

    def test_ordering_is_newest_first(self):
        CompanyAnalysis.objects.create(
            ticker="PETR4", content="Older", data_quarter="2024-Q4",
        )
        CompanyAnalysis.objects.create(
            ticker="PETR4", content="Newer", data_quarter="2025-Q4",
        )
        analyses = list(CompanyAnalysis.objects.filter(ticker="PETR4"))
        assert analyses[0].content == "Newer"
        assert analyses[1].content == "Older"

    def test_str_representation(self):
        analysis = CompanyAnalysis.objects.create(
            ticker="ITUB4", content="Test", data_quarter="2025-Q4",
        )
        assert str(analysis) == "ITUB4 — 2025-Q4"


@pytest.mark.django_db
class TestCompanyAnalysisAPI:
    def test_returns_latest_analysis(self, api_client, sample_analysis):
        response = api_client.get("/api/quote/PETR4/analysis/")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "PETR4"
        assert "fundamentos sólidos" in data["content"]
        assert data["dataQuarter"] == "2025-Q4"
        assert len(data["versions"]) == 1

    def test_returns_404_for_missing_ticker(self, api_client):
        response = api_client.get("/api/quote/FAKE11/analysis/")
        assert response.status_code == 404

    def test_case_insensitive_ticker(self, api_client, sample_analysis):
        response = api_client.get("/api/quote/petr4/analysis/")
        assert response.status_code == 200
        assert response.json()["ticker"] == "PETR4"

    def test_versions_list_includes_all(self, api_client):
        CompanyAnalysis.objects.create(
            ticker="VALE3", content="Old analysis", data_quarter="2024-Q4",
        )
        CompanyAnalysis.objects.create(
            ticker="VALE3", content="New analysis", data_quarter="2025-Q4",
        )
        response = api_client.get("/api/quote/VALE3/analysis/")
        data = response.json()
        assert data["content"] == "New analysis"
        assert len(data["versions"]) == 2

    def test_cache_header_is_set(self, api_client, sample_analysis):
        response = api_client.get("/api/quote/PETR4/analysis/")
        assert "max-age=3600" in response["Cache-Control"]


@pytest.mark.django_db
class TestImportAnalysesCommand:
    def test_imports_from_json_file(self):
        from django.core.management import call_command

        analyses_data = [
            {
                "ticker": "PETR4",
                "content": "Análise da Petrobras.",
                "dataQuarter": "2025-Q4",
            },
            {
                "ticker": "VALE3",
                "content": "Análise da Vale.",
                "dataQuarter": "2025-Q4",
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            json.dump(analyses_data, temp_file)
            temp_file_path = temp_file.name

        call_command("import_analyses", temp_file_path)

        assert CompanyAnalysis.objects.count() == 2
        assert CompanyAnalysis.objects.filter(ticker="PETR4").exists()
        assert CompanyAnalysis.objects.filter(ticker="VALE3").exists()

    def test_skips_existing_analyses(self):
        from django.core.management import call_command

        CompanyAnalysis.objects.create(
            ticker="PETR4", content="Existing.", data_quarter="2025-Q4",
        )

        analyses_data = [
            {
                "ticker": "PETR4",
                "content": "New version.",
                "dataQuarter": "2025-Q4",
            },
            {
                "ticker": "VALE3",
                "content": "Análise da Vale.",
                "dataQuarter": "2025-Q4",
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            json.dump(analyses_data, temp_file)
            temp_file_path = temp_file.name

        call_command("import_analyses", temp_file_path)

        assert CompanyAnalysis.objects.count() == 2
        assert CompanyAnalysis.objects.get(ticker="PETR4").content == "Existing."
        assert CompanyAnalysis.objects.filter(ticker="VALE3").exists()
