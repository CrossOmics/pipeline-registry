import hashlib
import json
from datetime import datetime, timezone

from helpers import pipeline_doc, version_doc, write_registry
from registry_tools.index import build_index, serialize, write_dist
from registry_tools.model import load_registry

NOW = datetime(2026, 11, 2, 3, 12, 44, tzinfo=timezone.utc)
VOCAB = {"domain": ["transcriptomics"], "modalities": ["scrna-seq"], "inputs": ["fastq"], "outputs": ["h5ad"]}


def _activity(raw, stars=1):
    return {"commits": raw, "releases": 0, "merged_prs": 0, "closed_issues": 0, "raw": raw,
            "last_commit_at": None, "archived": False, "stars": stars, "moved_to_url": None, "error": None}


def _cited(recent, work_id):
    return {"source": "openalex", "total": recent * 3, "recent": recent,
            "by_year": {"2024": 0, "2025": recent // 2, "2026": recent - recent // 2}, "work_id": work_id, "error": None}


def _metrics():
    return {"collected_at": "2026-11-02T03:05:10Z", "config": {}, "pipelines": {
        "cp_alpha": {"papers": {"doi:10.1000/alpha": _cited(100, "W1"), "doi:10.1000/alpha2": _cited(100, "W1")},
                     "activity": _activity(1), "activity_reason": None, "activity_repository": "https://github.com/org/alpha",
                     "collected_at": "2026-11-02T03:05:10Z", "stale_since": None, "error": None},
        "cp_beta": {"papers": {"doi:10.1000/beta": _cited(10, "W2")}, "activity": _activity(50),
                    "activity_reason": None, "activity_repository": "https://github.com/org/beta", "collected_at": "2026-11-02T03:05:10Z",
                    "stale_since": "2026-10-26T03:00:00Z", "error": None},
    }}


def _registry(tmp_path):
    write_registry(
        tmp_path,
        pipeline_doc("cp_alpha", papers=[{"doi": "10.1000/alpha", "title": "Alpha"}, {"doi": "10.1000/alpha2"}],
                     contributors=[{"name": "Jane Doe", "github": "JaneDoe", "role": "creator"}],
                     versions=[version_doc("cv_alpha_1", contributors=[
                         {"name": "Jane D.", "github": "janedoe", "role": "maintainer"}])]),
        pipeline_doc("cp_beta", kind="workflow", versions=[
            version_doc("cv_beta_1", "b"),
            version_doc("cv_beta_2", "d", parent="cv_beta_1", kind="optimization",
                        test_dataset={"accession": "SRR6750041", "description": "PBMC 1k"},
                        improvement_effect={"metrics": [{"name": "peak_rss_gb", "value": 14, "baseline": 31}]},
                        gardener_package={"ref": "ghcr.io/x/y:1", "digest": "sha256:" + "e" * 64}),
        ]),
        pipeline_doc("cp_gamma", papers=[], versions=[version_doc("cv_gamma_1", "c")]),
        {"schema_version": 1, "id": "cp_old_alpha", "moved_to": "cp_alpha"},
    )
    return load_registry(tmp_path)


def test_index_shape_scores_and_contributors(tmp_path):
    index = build_index(_registry(tmp_path), _metrics(), "f" * 40, NOW, vocab=VOCAB)

    assert (index["schema_version"], index["generated_at"], index["registry_commit"]) == (1, "2026-11-02T03:12:44Z",
                                                                                          "f" * 40)
    assert index["metrics_collected_at"] == "2026-11-02T03:05:10Z"
    assert index["config"] == {"citation_window_years": 3, "citation_years": [2024, 2025, 2026],
                               "activity_window_days": 365}
    assert index["vocab"] == VOCAB
    assert index["moved"] == {"cp_old_alpha": "cp_alpha"}
    assert index["contributors"] == [{"id": "ctr_gh_janedoe", "name": "Jane Doe", "github": "JaneDoe", "orcid": None}]
    alpha, beta, gamma = index["pipelines"]
    assert (alpha["kind"], beta["kind"]) == ("tool", "workflow")
    assert alpha["contributors"] == [{"contributor_id": "ctr_gh_janedoe", "role": "creator"}]
    assert alpha["papers"][0] == {"doi": "10.1000/alpha", "url": None, "title": "Alpha",
                                  "citations": _cited(100, "W1")}
    assert alpha["metrics"]["recent_citations"] == 100  # same OpenAlex work counted once
    assert alpha["metrics"]["citations_by_year"] == {"2024": 0, "2025": 50, "2026": 50}
    assert (alpha["metrics"]["priority"], beta["metrics"]["priority"]) == (1.0, 0.0)
    assert beta["metrics"]["stale_since"] == "2026-10-26T03:00:00Z"
    assert beta["versions"][0] == {
        "id": "cv_beta_1", "kind": "original", "label": "1.0", "repo": "https://github.com/org/alpha",
        "commit": "b" * 40, "parent": None, "released_at": None, "contributors": [], "improvement": None,
        "test_dataset": None, "improvement_effect": None, "gardener_package": None, "withdrawn": False}
    assert beta["versions"][1] == {
        "id": "cv_beta_2", "kind": "optimization", "label": "1.0", "repo": "https://github.com/org/alpha",
        "commit": "d" * 40, "parent": "cv_beta_1", "released_at": None, "contributors": [],
        "improvement": "Faster.",
        "test_dataset": {"accession": "SRR6750041", "url": None, "sha256": None, "description": "PBMC 1k"},
        "improvement_effect": {"summary": None,
                               "metrics": [{"name": "peak_rss_gb", "value": 14, "baseline": 31, "unit": None}]},
        "gardener_package": {"ref": "ghcr.io/x/y:1", "digest": "sha256:" + "e" * 64}, "withdrawn": False}
    assert gamma["metrics"]["priority_reason"] == "no_paper"
    assert gamma["metrics"]["citations_by_year"] is None


def test_missing_metrics_mean_no_citation_data(tmp_path):
    index = build_index(_registry(tmp_path), None, "f" * 40, NOW)
    alpha = index["pipelines"][0]
    assert alpha["papers"][0]["citations"] is None
    assert alpha["metrics"]["priority_reason"] == "no_citation_data"
    assert index["metrics_collected_at"] is None
    assert index["config"]["citation_years"] == [2024, 2025, 2026]
    assert index["vocab"] == {}


def test_serialization_is_deterministic_and_hashed(tmp_path):
    registry = _registry(tmp_path)
    first = serialize(build_index(registry, _metrics(), "f" * 40, NOW))
    second = serialize(build_index(registry, _metrics(), "f" * 40, NOW))
    assert first == second
    assert b"\n" not in first and b": " not in first

    digest = write_dist(build_index(registry, _metrics(), "f" * 40, NOW), tmp_path / "dist")
    body = (tmp_path / "dist" / "index.json").read_bytes()
    assert digest == hashlib.sha256(body).hexdigest()
    assert (tmp_path / "dist" / "index.json.sha256").read_text() == digest + "\n"
    assert json.loads(body)["schema_version"] == 1
