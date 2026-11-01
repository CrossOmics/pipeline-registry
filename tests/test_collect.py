from datetime import datetime, timezone

from helpers import pipeline_doc, write_registry
from registry_tools.citations import CitationResult
from registry_tools.collect import collect_metrics
from registry_tools.http import CollectError
from registry_tools.model import load_registry

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
ACTIVITY = {"commits": 1, "releases": 0, "merged_prs": 0, "closed_issues": 0, "raw": 1, "last_commit_at": None,
            "archived": False, "stars": 2, "moved_to_url": None, "error": None}


class FakeCitations:
    def __init__(self, failing=()):
        self.failing = set(failing)

    def collect(self, paper):
        if paper.get("doi") in self.failing:
            raise CollectError("openalex down")
        return CitationResult("openalex", total=10, recent=4, by_year={"2026": 4})


class FakeGitHub:
    def collect(self, repo_url, now):
        if "gitlab" in repo_url:
            return None, "unsupported_host"
        return dict(ACTIVITY), None


def test_collects_every_pipeline(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"), pipeline_doc("cp_beta", repositories=[]),
                   pipeline_doc("cp_gamma", repositories=[{"url": "https://gitlab.com/a/b", "primary": True}]))

    metrics, failed, attempted = collect_metrics(load_registry(tmp_path), None, FakeGitHub(), FakeCitations(), NOW)

    assert (failed, attempted) == (0, 3)
    assert metrics["collected_at"] == "2026-11-02T03:00:00Z"
    alpha = metrics["pipelines"]["cp_alpha"]
    assert alpha["papers"] == {"doi:10.1000/alpha": {"source": "openalex", "total": 10, "recent": 4,
                                                     "by_year": {"2026": 4}, "work_id": None, "error": None}}
    assert (alpha["activity"], alpha["activity_reason"], alpha["stale_since"]) == (ACTIVITY, None, None)
    assert metrics["pipelines"]["cp_beta"]["activity_reason"] == "no_repo"
    assert metrics["pipelines"]["cp_gamma"]["activity_reason"] == "unsupported_host"


def test_a_failed_pipeline_keeps_its_previous_metrics_and_marks_them_stale(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"), pipeline_doc("cp_beta"))
    first, _, _ = collect_metrics(load_registry(tmp_path), None, FakeGitHub(), FakeCitations(), NOW)

    second, failed, attempted = collect_metrics(load_registry(tmp_path), first, FakeGitHub(),
                                                FakeCitations(failing={"10.1000/alpha"}), LATER)

    assert (failed, attempted) == (1, 2)
    alpha = second["pipelines"]["cp_alpha"]
    assert alpha["papers"] == first["pipelines"]["cp_alpha"]["papers"]
    assert alpha["collected_at"] == "2026-11-02T03:00:00Z"
    assert alpha["stale_since"] == "2026-11-09T03:00:00Z"
    assert second["pipelines"]["cp_beta"]["stale_since"] is None

    third, _, _ = collect_metrics(load_registry(tmp_path), second, FakeGitHub(),
                                  FakeCitations(failing={"10.1000/alpha"}),
                                  datetime(2026, 11, 16, tzinfo=timezone.utc))
    assert third["pipelines"]["cp_alpha"]["stale_since"] == "2026-11-09T03:00:00Z"


def test_a_failed_pipeline_without_history_records_the_error(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"))
    metrics, failed, _ = collect_metrics(load_registry(tmp_path), None, FakeGitHub(),
                                         FakeCitations(failing={"10.1000/alpha"}), NOW)
    alpha = metrics["pipelines"]["cp_alpha"]
    assert failed == 1
    assert (alpha["papers"], alpha["activity"], alpha["stale_since"]) == ({}, None, "2026-11-02T03:00:00Z")
    assert "openalex down" in alpha["error"]
