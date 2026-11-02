from datetime import datetime, timezone

import pytest
from jsonschema import Draft202012Validator

from helpers import REPO_ROOT, pipeline_doc, write_registry
from registry_tools.index import build_index
from registry_tools.collect import collect_metrics
from registry_tools.model import load_registry
from registry_tools.ranking_page import render_ranking_page
from registry_tools.schema import load_schema

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("maintenance", [
    {"status": "available", "repository": "https://github.com/BioCode-Commons/STAR"},
    {"status": "planned"},
])
def test_registered_maintenance_is_valid_without_replacing_the_original(maintenance):
    doc = pipeline_doc(biocode_maintenance=maintenance)
    assert not list(Draft202012Validator(load_schema(REPO_ROOT)).iter_errors(doc))


@pytest.mark.parametrize("maintenance", [
    {"status": "available"},
    {"status": "available", "repository": "https://github.com/someone/STAR"},
    {"status": "available", "repository": "https://github.com/BioCode-Commons/.github"},
    {"status": "available", "repository": "https://github.com/BioCode-Commons"},
    {"status": "available", "repository": "javascript:alert(1)"},
    {"status": "available", "repository": "https://github.com/BioCode-Commons/STAR/issues"},
    {"status": "available", "repository": "https://github.com/BioCode-Commons/STAR?x=1"},
    {"status": "maybe"},
])
def test_maintenance_cannot_claim_available_without_a_biocode_repository(maintenance):
    doc = pipeline_doc(biocode_maintenance=maintenance)
    assert list(Draft202012Validator(load_schema(REPO_ROOT)).iter_errors(doc))


def test_maintenance_reaches_the_index_without_changing_upstream_activity_or_score(tmp_path):
    original = pipeline_doc()
    write_registry(tmp_path, original)
    metrics = {"pipelines": {"cp_alpha": {
        "activity_repository": "https://github.com/org/alpha",
        "activity": {"raw": 3, "last_commit_at": "2020-01-01T00:00:00Z"},
    }}}
    before = build_index(load_registry(tmp_path), metrics, "a" * 40, NOW)
    original["biocode_maintenance"] = {"status": "available", "repository": "https://github.com/BioCode-Commons/STAR"}
    write_registry(tmp_path, original)
    after = build_index(load_registry(tmp_path), metrics, "a" * 40, NOW)
    assert after["pipelines"][0]["biocode_maintenance"] == original["biocode_maintenance"]
    assert after["pipelines"][0]["metrics"] == before["pipelines"][0]["metrics"]
    assert after["pipelines"][0]["repositories"] == [{"url": "https://github.com/org/alpha", "primary": True}]


def test_collection_queries_only_the_original_even_when_a_biocode_replacement_is_registered(tmp_path):
    calls = []

    class GitHub:
        def collect(self, repository, now):
            calls.append(repository)
            return {"raw": 0, "last_commit_at": "2020-01-01T00:00:00Z"}, None

    write_registry(tmp_path, pipeline_doc(papers=[], biocode_maintenance={
        "status": "available", "repository": "https://github.com/BioCode-Commons/STAR"}))
    metrics, failed, attempted = collect_metrics(load_registry(tmp_path), None, GitHub(), None, NOW)
    assert (failed, attempted) == (0, 1)
    assert calls == ["https://github.com/org/alpha"]
    assert metrics["pipelines"]["cp_alpha"]["activity_repository"] == "https://github.com/org/alpha"


def _row(pid, name, maintenance=None):
    item = pipeline_doc(pid, name=name)
    if maintenance is not None:
        item["biocode_maintenance"] = maintenance
    item["metrics"] = {"priority": 0.5, "priority_reason": None, "activity": {
        "last_commit_at": "2020-01-01T00:00:00Z", "commits": 0, "releases": 0,
        "merged_prs": 0, "closed_issues": 0,
    }}
    return item


def test_page_distinguishes_available_planned_and_unregistered_and_links_upstream():
    index = {"registry_commit": "a" * 40, "config": {"citation_years": [2024, 2025, 2026], "activity_window_days": 365},
             "pipelines": [
                 _row("cp_available", "Available", {"status": "available", "repository": "https://github.com/BioCode-Commons/STAR"}),
                 _row("cp_planned", "Planned", {"status": "planned"}),
                 _row("cp_unknown", "Unknown"),
             ]}
    html = render_ranking_page(index)
    assert "BioCode maintenance" in html
    assert '<a href="https://github.com/BioCode-Commons/STAR">Available</a>' in html
    assert "Planned" in html and "Not registered" in html
    assert '<a href="https://github.com/org/available">2020-01-01</a>' in html
    assert "Original GitHub update" in html
    assert "original author's primary GitHub repository" in html
