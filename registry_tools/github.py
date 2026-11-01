"""GitHub activity of a pipeline's primary repository over the last year (SPEC-02 §3.2)."""

import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

from registry_tools import ACTIVITY_WINDOW_DAYS
from registry_tools.http import CollectError, request_json
from registry_tools.model import github_owner_name, normalize_repo_url

GRAPHQL = "https://api.github.com/graphql"
SEARCH = "https://api.github.com/search/issues"
SEARCH_INTERVAL_SECONDS = 60 / 25

_QUERY = """
query($owner: String!, $name: String!, $since: GitTimestamp!) {
  repository(owner: $owner, name: $name) {
    url
    isArchived
    stargazerCount
    defaultBranchRef { target { ... on Commit { committedDate history(since: $since) { totalCount } } } }
    releases(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { createdAt } }
  }
}
"""


def _parse(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class GitHubCollector:
    def __init__(self, http: httpx.Client, token: Optional[str], window_days: int = ACTIVITY_WINDOW_DAYS,
                 sleep: Callable[[float], None] = time.sleep):
        self.http, self.window_days, self.sleep = http, window_days, sleep
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def collect(self, repo_url: str, now: datetime) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        owner_name = github_owner_name(repo_url)
        if owner_name is None:
            return None, "unsupported_host"
        since = now - timedelta(days=self.window_days)
        variables = {"owner": owner_name[0], "name": owner_name[1], "since": since.strftime("%Y-%m-%dT%H:%M:%SZ")}
        body = request_json(self.http, "POST", GRAPHQL, json={"query": _QUERY, "variables": variables},
                            headers=self.headers, sleep=self.sleep)
        if body is None:
            return None, "repo_unreachable"
        repository = (body.get("data") or {}).get("repository")
        if repository is None:
            if any(error.get("type") == "NOT_FOUND" for error in body.get("errors") or []):
                return None, "repo_unreachable"
            raise CollectError(f"GitHub GraphQL for {repo_url}: {body.get('errors')}")
        resolved = normalize_repo_url(repository["url"])
        owner, name = github_owner_name(resolved) or owner_name
        target = (repository.get("defaultBranchRef") or {}).get("target") or {}
        commits = int((target.get("history") or {}).get("totalCount") or 0)
        releases = sum(1 for release in (repository.get("releases") or {}).get("nodes") or []
                       if _parse(release["createdAt"]) >= since)
        day = since.strftime("%Y-%m-%d")
        merged_prs = self._count(f"repo:{owner}/{name} is:pr is:merged merged:>={day}")
        closed_issues = self._count(f"repo:{owner}/{name} is:issue is:closed closed:>={day}")
        archived = bool(repository.get("isArchived"))
        return {
            "commits": commits,
            "releases": releases,
            "merged_prs": merged_prs,
            "closed_issues": closed_issues,
            "raw": 0 if archived else commits + 5 * releases + 2 * merged_prs + closed_issues,
            "last_commit_at": target.get("committedDate"),
            "archived": archived,
            "stars": int(repository.get("stargazerCount") or 0),
            "moved_to_url": resolved if resolved != normalize_repo_url(repo_url) else None,
            "error": None,
        }, None

    def _count(self, query: str) -> int:
        self.sleep(SEARCH_INTERVAL_SECONDS)
        body = request_json(self.http, "GET", SEARCH, params={"q": query, "per_page": 1},
                            headers=self.headers, sleep=self.sleep)
        return int((body or {}).get("total_count") or 0)
