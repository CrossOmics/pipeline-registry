from datetime import datetime, timezone

from helpers import GOLDEN, GOLDEN_STAR, GOLDEN_STAR_APPENDED, pipeline_doc, version_doc, write_registry
from registry_tools.model import (
    contributor_id, dump_pipeline, github_owner_name, iso, load_registry, load_yaml, normalize_doi,
    normalize_repo_url, paper_key, primary_repository,
)


def test_normalize_doi_strips_prefixes_and_lowercases():
    assert normalize_doi(" https://doi.org/10.1038/S41587-020-0439-X ") == "10.1038/s41587-020-0439-x"
    assert normalize_doi("doi:10.1/ABC") == "10.1/abc"
    assert normalize_doi("10.1/abc") == "10.1/abc"


def test_normalize_repo_url():
    assert normalize_repo_url("https://GitHub.com/nf-core/RNAseq.git/") == "https://github.com/nf-core/rnaseq"
    assert normalize_repo_url("http://gitlab.com/a/b") == "https://gitlab.com/a/b"


def test_github_owner_name():
    assert github_owner_name("https://github.com/nf-core/rnaseq.git") == ("nf-core", "rnaseq")
    assert github_owner_name("https://gitlab.com/a/b") is None
    assert github_owner_name("https://github.com/nf-core") is None


def test_contributor_id_prefers_github_then_orcid_then_name():
    assert contributor_id({"name": "J", "github": "JaneDoe", "orcid": "0000-0002-1825-0097"}) == "ctr_gh_janedoe"
    assert contributor_id({"name": "J", "orcid": "0000-0002-1825-0097"}) == "ctr_orcid_0000-0002-1825-0097"
    assert contributor_id({"name": "José  Núñez-Ruiz"}) == "ctr_name_jos_n_ez_ruiz"


def test_paper_key_and_primary_repository():
    assert paper_key({"doi": "DOI:10.1/X"}) == "doi:10.1/x"
    assert paper_key({"url": "https://arxiv.org/abs/1"}) == "url:https://arxiv.org/abs/1"
    assert primary_repository(pipeline_doc("cp_alpha")) == "https://github.com/org/alpha"
    assert primary_repository(pipeline_doc("cp_alpha", repositories=[])) is None


def test_iso_formats_utc_seconds():
    assert iso(datetime(2026, 11, 2, 3, 4, 5, 123, tzinfo=timezone.utc)) == "2026-11-02T03:04:05Z"


def test_load_registry_keeps_dates_as_strings_and_splits_moved(tmp_path):
    write_registry(
        tmp_path,
        pipeline_doc("cp_beta", versions=[version_doc("cv_beta_1", released_at="2024-09-12")]),
        pipeline_doc("cp_alpha"),
        {"schema_version": 1, "id": "cp_old", "moved_to": "cp_beta"},
    )
    (tmp_path / "pipelines" / "cp_broken.yaml").write_text("id: [unclosed", encoding="utf-8")

    registry = load_registry(tmp_path)

    assert [p["id"] for p in registry.pipelines()] == ["cp_alpha", "cp_beta"]
    assert registry.moved() == {"cp_old": "cp_beta"}
    beta = registry.pipelines()[1]
    assert beta["versions"][0]["released_at"] == "2024-09-12"
    assert [v["id"] for _, v in registry.versions()] == ["cv_alpha_1", "cv_beta_1"]
    broken = [f for f in registry.files if f.stem == "cp_broken"][0]
    assert broken.doc is None and broken.error and broken.text == "id: [unclosed"


def test_dump_pipeline_orders_keys_and_drops_empty_values():
    doc = {"versions": [{"withdrawn": False, "parent": None, "id": "cv_a_1", "improvement": None,
                         "contributors": [], "kind": "original"}],
           "zzz_unknown": 1, "id": "cp_a", "modalities": [], "schema_version": 1}
    assert dump_pipeline(doc) == (
        "schema_version: 1\nid: cp_a\nversions:\n- id: cv_a_1\n  kind: original\n  parent: null\nzzz_unknown: 1\n")
    assert dump_pipeline({"moved_to": "cp_b", "id": "cp_a", "schema_version": 1}) == (
        "schema_version: 1\nid: cp_a\nmoved_to: cp_b\n")


def test_golden_files_are_the_canonical_text_and_round_trip():
    for name, doc in (("cp_star.yaml", GOLDEN_STAR), ("cp_star_appended.yaml", GOLDEN_STAR_APPENDED)):
        text = (GOLDEN / name).read_text(encoding="utf-8")
        assert text == dump_pipeline(doc)
        assert dump_pipeline(load_yaml(text)) == text
    assert "released_at: '2022-11-01'" in (GOLDEN / "cp_star.yaml").read_text(encoding="utf-8")


def test_appending_a_version_appends_text():
    before = dump_pipeline(GOLDEN_STAR)
    after = dump_pipeline(GOLDEN_STAR_APPENDED)
    assert after.startswith(before) and after != before
