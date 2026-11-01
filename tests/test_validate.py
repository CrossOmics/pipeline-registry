from helpers import REPO_ROOT, pipeline_doc, version_doc, write_registry
from registry_tools.model import load_registry
from registry_tools.schema import load_schema
from registry_tools.validate import Issue, validate_registry

SCHEMA = load_schema(REPO_ROOT)


def _issues(root, base=None):
    return validate_registry(load_registry(root), SCHEMA, base=load_registry(base) if base else None)


def _rules(issues):
    return sorted({issue.rule for issue in issues})


def test_a_valid_registry_has_no_issues(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"), pipeline_doc("cp_beta", kind="workflow", versions=[
        version_doc("cv_beta_1", "b", repo="https://github.com/org/beta"),
        version_doc("cv_beta_2", "c", parent="cv_beta_1", repo="https://github.com/org/beta",
                    improvement="Release notes."),
        version_doc("cv_beta_3", "d", parent="cv_beta_2", kind="optimization", repo="https://github.com/other/beta",
                    released_at="2026-01-02",
                    test_dataset={"accession": "SRR6750041", "description": "PBMC 1k"},
                    improvement_effect={"metrics": [{"name": "runtime_min", "value": 12, "baseline": 30}]},
                    gardener_package={"ref": "ghcr.io/x/y:1", "digest": "sha256:" + "d" * 64}),
        version_doc("cv_beta_4", "e", parent="cv_beta_3", kind="optimization", repo="https://github.com/third/beta",
                    withdrawn=True, improvement_effect={"summary": "Uses less memory."}),
    ]), {"schema_version": 1, "id": "cp_old_alpha", "moved_to": "cp_alpha"})
    assert _issues(tmp_path) == []


def test_r1_missing_field_bad_commit_and_unknown_vocab(tmp_path):
    doc = pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1", commit="abc")], modalities=["rna"])
    del doc["description"]
    write_registry(tmp_path, doc)

    issues = _issues(tmp_path)

    assert _rules(issues) == ["R1"]
    pointers = {issue.pointer for issue in issues}
    assert "/versions/0/commit" in pointers
    assert "/modalities/0" in pointers
    assert any("description" in issue.message for issue in issues)


def test_r1_kind_dependent_fields(tmp_path):
    doc = pipeline_doc("cp_alpha", versions=[
        version_doc("cv_alpha_1", test_dataset={"accession": "SRR1", "description": "x"}),
        version_doc("cv_alpha_2", "b", parent="cv_alpha_1", kind="optimization", improvement=""),
        version_doc("cv_alpha_3", "c", parent="cv_alpha_1", kind="optimization"),
    ])
    del doc["kind"]
    del doc["versions"][2]["improvement"]
    write_registry(tmp_path, doc)

    issues = _issues(tmp_path)

    assert _rules(issues) == ["R1"]
    pointers = {issue.pointer for issue in issues}
    assert {"/", "/versions/0", "/versions/1/improvement", "/versions/2"} <= pointers
    assert any("kind" in issue.message for issue in issues if issue.pointer == "/")


def test_r1_test_dataset_and_effect_shapes(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha", versions=[
        version_doc("cv_alpha_1"),
        version_doc("cv_alpha_2", "b", parent="cv_alpha_1", kind="optimization",
                    test_dataset={"accession": "not-an-accession", "description": "x"},
                    improvement_effect={}),
        version_doc("cv_alpha_3", "c", parent="cv_alpha_1", kind="optimization",
                    test_dataset={"description": "no accession or url"},
                    improvement_effect={"metrics": [{"name": "Peak RSS", "value": "14"}]}),
    ]))
    pointers = {issue.pointer for issue in _issues(tmp_path)}
    assert {"/versions/1/test_dataset/accession", "/versions/1/improvement_effect",
            "/versions/2/test_dataset", "/versions/2/improvement_effect/metrics/0/name",
            "/versions/2/improvement_effect/metrics/0/value"} <= pointers


def test_r1_id_must_match_file_name(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"), stems={"cp_alpha": "cp_other"})
    (issue,) = _issues(tmp_path)
    assert (issue.file, issue.pointer, issue.rule) == ("pipelines/cp_other.yaml", "/id", "R1")


def test_r1_unreadable_yaml(tmp_path):
    (tmp_path / "pipelines").mkdir()
    (tmp_path / "pipelines" / "cp_bad.yaml").write_text("id: [", encoding="utf-8")
    (issue,) = _issues(tmp_path)
    assert issue.rule == "R1" and "not valid YAML" in issue.message


def test_r1_moved_stub_takes_no_other_fields(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"),
                   {"schema_version": 1, "id": "cp_old", "moved_to": "cp_alpha", "name": "x"})
    assert _rules(_issues(tmp_path)) == ["R1"]


def test_issue_formats():
    issue = Issue("pipelines/cp_a.yaml", "/versions/0/commit", "R1", "bad")
    assert str(issue) == "pipelines/cp_a.yaml:/versions/0/commit: R1: bad"
    assert issue.annotation() == "::error file=pipelines/cp_a.yaml::/versions/0/commit: R1: bad"
