from datetime import date

import httpx
import pytest

from registry_tools.citations import (
    CitationCollector, OpenAlexClient, SemanticScholarClient, window_years,
)
from registry_tools.http import CollectError, request_json

YEARS = window_years(date(2026, 11, 2), 3)
NO_SLEEP = lambda seconds: None  # noqa: E731


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _collector(handler, api_key=None):
    http = _client(handler)
    return CitationCollector(OpenAlexClient(http, "ops@example.org", sleep=NO_SLEEP),
                             SemanticScholarClient(http, api_key, sleep=NO_SLEEP), YEARS)


def test_window_years():
    assert YEARS == [2024, 2025, 2026]
    assert window_years(date(2027, 1, 3), 3) == [2025, 2026, 2027]


def test_request_json_retries_rate_limits_then_gives_up():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": "1"})

    with pytest.raises(CollectError):
        request_json(_client(handler), "GET", "https://x.test/a", sleep=NO_SLEEP)
    assert len(calls) == 4


def test_request_json_404_is_none_and_recovers_from_a_5xx():
    responses = iter([httpx.Response(502), httpx.Response(200, json={"ok": True})])
    assert request_json(_client(lambda r: next(responses)), "GET", "https://x.test/a", sleep=NO_SLEEP) == {"ok": True}
    assert request_json(_client(lambda r: httpx.Response(404)), "GET", "https://x.test/a", sleep=NO_SLEEP) is None


def test_openalex_hit_counts_the_window():
    def handler(request):
        assert request.url.path == "/works/doi:10.1038/x"
        assert request.url.params["mailto"] == "ops@example.org"
        return httpx.Response(200, json={"id": "https://openalex.org/W1", "cited_by_count": 900, "counts_by_year": [
            {"year": 2026, "cited_by_count": 40}, {"year": 2025, "cited_by_count": 100},
            {"year": 2024, "cited_by_count": 60}, {"year": 2023, "cited_by_count": 500}]})

    result = _collector(handler).collect({"doi": "10.1038/X"})

    assert result.to_json() == {"source": "openalex", "total": 900, "recent": 200,
                                "by_year": {"2024": 60, "2025": 100, "2026": 40},
                                "work_id": "https://openalex.org/W1", "error": None}


def test_openalex_miss_falls_back_to_semantic_scholar_with_paging():
    def handler(request):
        if request.url.host == "api.openalex.org":
            return httpx.Response(404)
        if request.url.path == "/graph/v1/paper/DOI:10.1/x":
            return httpx.Response(200, json={"paperId": "P1", "citationCount": 3})
        assert request.url.path == "/graph/v1/paper/P1/citations"
        if request.url.params["offset"] == "0":
            return httpx.Response(200, json={"next": 1000, "data": [
                {"citingPaper": {"year": 2025}}, {"citingPaper": {"year": 2019}}]})
        return httpx.Response(200, json={"data": [{"citingPaper": {"year": 2026}}]})

    result = _collector(handler).collect({"doi": "10.1/x"})

    assert (result.source, result.total, result.recent, result.by_year, result.work_id) == (
        "semantic_scholar", 3, 2, {"2024": 0, "2025": 1, "2026": 1}, "s2:P1")


def test_preprint_url_goes_to_semantic_scholar_and_other_urls_are_not_found():
    def handler(request):
        assert request.url.host == "api.semanticscholar.org"
        assert request.headers["x-api-key"] == "k"
        if request.url.path.endswith("/citations"):
            return httpx.Response(200, json={"data": []})
        assert request.url.path == "/graph/v1/paper/URL:https://www.biorxiv.org/content/10.1101/1"
        return httpx.Response(200, json={"paperId": "P2", "citationCount": 0})

    collector = _collector(handler, api_key="k")
    assert collector.collect({"url": "https://www.biorxiv.org/content/10.1101/1"}).source == "semantic_scholar"
    missing = collector.collect({"url": "https://example.org/paper"})
    assert (missing.source, missing.error) == (None, "not_found")


def test_neither_source_has_the_paper():
    result = _collector(lambda r: httpx.Response(404)).collect({"doi": "10.1/none"})
    assert (result.source, result.recent, result.error) == (None, None, "not_found")
