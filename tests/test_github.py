from datetime import datetime, timezone

import httpx
import pytest

from registry_tools.github import GitHubCollector
from registry_tools.http import CollectError

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=timezone.utc)


def _repo(url="https://github.com/nf-core/rnaseq", archived=False):
    return {"data": {"repository": {
        "url": url, "isArchived": archived, "stargazerCount": 410,
        "defaultBranchRef": {"target": {"committedDate": "2026-10-01T10:00:00Z", "history": {"totalCount": 12}}},
        "releases": {"nodes": [{"createdAt": "2026-09-01T00:00:00Z"}, {"createdAt": "2025-01-01T00:00:00Z"}]},
    }}}


def _handler(graphql_body, seen):
    def handler(request):
        seen.append(request)
        if request.url.path == "/graphql":
            return httpx.Response(200, json=graphql_body)
        query = request.url.params["q"]
        return httpx.Response(200, json={"total_count": 3 if "is:pr" in query else 7})
    return handler


def _collector(handler):
    return GitHubCollector(httpx.Client(transport=httpx.MockTransport(handler)), "tok", sleep=lambda s: None)


def test_collects_activity_in_the_window():
    seen = []
    activity, reason = _collector(_handler(_repo(), seen)).collect("https://github.com/nf-core/rnaseq", NOW)

    assert reason is None
    assert activity == {"commits": 12, "releases": 1, "merged_prs": 3, "closed_issues": 7,
                        "raw": 12 + 5 * 1 + 2 * 3 + 7, "last_commit_at": "2026-10-01T10:00:00Z",
                        "archived": False, "stars": 410, "moved_to_url": None, "error": None}
    graphql = seen[0]
    assert graphql.headers["authorization"] == "Bearer tok"
    assert b'"since": "2025-11-02T03:00:00Z"' in graphql.content or b'"since":"2025-11-02T03:00:00Z"' in graphql.content
    assert "merged:>=2025-11-02" in seen[1].url.params["q"]
    assert "repo:nf-core/rnaseq" in seen[2].url.params["q"]


def test_archived_repo_has_zero_raw_activity():
    activity, _ = _collector(_handler(_repo(archived=True), [])).collect("https://github.com/nf-core/rnaseq", NOW)
    assert (activity["archived"], activity["raw"], activity["commits"]) == (True, 0, 12)


def test_moved_repo_reports_the_new_url_and_searches_there():
    seen = []
    activity, _ = _collector(_handler(_repo(url="https://github.com/new-org/rnaseq"), seen)).collect(
        "https://github.com/nf-core/rnaseq", NOW)
    assert activity["moved_to_url"] == "https://github.com/new-org/rnaseq"
    assert "repo:new-org/rnaseq" in seen[1].url.params["q"]


def test_missing_repo_and_other_hosts():
    not_found = {"data": {"repository": None}, "errors": [{"type": "NOT_FOUND", "message": "x"}]}
    assert _collector(_handler(not_found, [])).collect("https://github.com/a/b", NOW) == (None, "repo_unreachable")
    assert _collector(_handler(_repo(), [])).collect("https://gitlab.com/a/b", NOW) == (None, "unsupported_host")


def test_other_graphql_errors_raise():
    body = {"data": {"repository": None}, "errors": [{"type": "INTERNAL", "message": "boom"}]}
    with pytest.raises(CollectError):
        _collector(_handler(body, [])).collect("https://github.com/a/b", NOW)
