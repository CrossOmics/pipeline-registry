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
def test_r2_duplicate_version_id_across_files(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"),
                   pipeline_doc("cp_beta", versions=[version_doc("cv_alpha_1", "b", repo="https://github.com/org/beta")]))
    assert _rules(_issues(tmp_path)) == ["R2"]


def test_r3_parent_must_be_in_the_same_file(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"), pipeline_doc("cp_beta", versions=[
        version_doc("cv_beta_1", "b"),
        version_doc("cv_beta_2", "c", parent="cv_alpha_1", kind="optimization"),
        version_doc("cv_beta_3", "d", parent="cv_nope_1", kind="optimization"),
    ]))
    issues = _issues(tmp_path)
    assert [(issue.file, issue.rule, issue.pointer) for issue in issues] == [
        ("pipelines/cp_beta.yaml", "R3", "/versions/1/parent"), ("pipelines/cp_beta.yaml", "R3", "/versions/2/parent")]
    assert "same file" in issues[0].message


def test_r4_cycle_is_reported_once(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha", versions=[
        version_doc("cv_alpha_1", "a"),
        version_doc("cv_alpha_2", "b", parent="cv_alpha_3"),
        version_doc("cv_alpha_3", "c", parent="cv_alpha_2"),
    ]))
    issues = _issues(tmp_path)
    assert [issue.rule for issue in issues] == ["R4"]
    assert "cv_alpha_2" in issues[0].message and "cv_alpha_3" in issues[0].message


def test_r5_same_commit_registered_twice_after_url_normalization(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha", versions=[
        version_doc("cv_alpha_1", "a", repo="https://github.com/Org/Alpha.git"),
        version_doc("cv_alpha_2", "a", repo="https://github.com/org/alpha", parent="cv_alpha_1"),
    ]))
    (issue,) = _issues(tmp_path)
    assert (issue.rule, issue.pointer) == ("R5", "/versions/1/commit")


def test_r6_exactly_one_primary_repository(tmp_path):
    write_registry(tmp_path,
                   pipeline_doc("cp_alpha", repositories=[{"url": "https://github.com/a/b"}]),
                   pipeline_doc("cp_beta", versions=[version_doc("cv_beta_1", "b")], repositories=[
                       {"url": "https://github.com/a/c", "primary": True},
                       {"url": "https://github.com/a/d", "primary": True}]))
    assert [issue.rule for issue in _issues(tmp_path)] == ["R6", "R6"]


def test_r7_moved_to_must_name_a_pipeline_that_is_not_moved(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"),
                   {"schema_version": 1, "id": "cp_old", "moved_to": "cp_mid"},
                   {"schema_version": 1, "id": "cp_mid", "moved_to": "cp_alpha"},
                   {"schema_version": 1, "id": "cp_gone", "moved_to": "cp_nowhere"})
    issues = _issues(tmp_path)
    assert sorted((issue.file, issue.rule) for issue in issues) == [
        ("pipelines/cp_gone.yaml", "R7"), ("pipelines/cp_old.yaml", "R7")]


def test_r9_digest_format_and_no_digest_in_ref(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha", versions=[
        version_doc("cv_alpha_1", "a", gardener_package={"ref": "ghcr.io/x/y@sha256:" + "a" * 64,
                                                          "digest": "sha256:" + "a" * 64}),
        version_doc("cv_alpha_2", "b", parent="cv_alpha_1",
                    gardener_package={"ref": "ghcr.io/x/y:1", "digest": "sha256:ABC"}),
    ]))
    issues = _issues(tmp_path)
    assert [(issue.rule, issue.pointer) for issue in issues] == [
        ("R9", "/versions/0/gardener_package/ref"), ("R9", "/versions/1/gardener_package/digest")]


def test_r10_doi_must_be_normalized_and_unique(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha", papers=[
        {"doi": "https://doi.org/10.1/ABC"}, {"doi": "10.1/abc"}]))
    issues = _issues(tmp_path)
    assert [(issue.rule, issue.pointer) for issue in issues] == [
        ("R10", "/papers/0/doi"), ("R10", "/papers/1/doi")]


def test_r11_exactly_one_root_and_it_is_an_original(tmp_path):
    write_registry(
        tmp_path,
        pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1", "a"), version_doc("cv_alpha_2", "b")]),
        pipeline_doc("cp_beta", versions=[version_doc("cv_beta_1", "c", kind="optimization")]),
        pipeline_doc("cp_gamma", versions=[version_doc("cv_gamma_1", "d", parent="cv_gamma_2"),
                                           version_doc("cv_gamma_2", "e", parent="cv_gamma_1")]),
    )
    issues = [issue for issue in _issues(tmp_path) if issue.rule == "R11"]
    assert [(issue.file, issue.pointer) for issue in issues] == [
        ("pipelines/cp_alpha.yaml", "/versions/1/parent"),
        ("pipelines/cp_beta.yaml", "/versions/0/kind"),
        ("pipelines/cp_gamma.yaml", "/versions"),
    ]


def test_r12_an_original_builds_only_on_an_original(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha", versions=[
        version_doc("cv_alpha_1", "a"),
        version_doc("cv_alpha_2", "b", parent="cv_alpha_1", kind="optimization"),
        version_doc("cv_alpha_3", "c", parent="cv_alpha_2"),
        version_doc("cv_alpha_4", "d", parent="cv_alpha_2", kind="optimization"),
    ]))
    (issue,) = _issues(tmp_path)
    assert (issue.rule, issue.pointer) == ("R12", "/versions/2/parent")


def test_r13_files_must_be_canonical(tmp_path):
    write_registry(tmp_path, pipeline_doc("cp_alpha"), pipeline_doc("cp_beta", versions=[version_doc("cv_beta_1", "b")]))
    alpha = tmp_path / "pipelines" / "cp_alpha.yaml"
    alpha.write_text("# a comment\n" + alpha.read_text(encoding="utf-8"), encoding="utf-8")
    beta = tmp_path / "pipelines" / "cp_beta.yaml"
    text = beta.read_text(encoding="utf-8")
    assert text.startswith("schema_version: 1\n")
    beta.write_text(text[len("schema_version: 1\n"):] + "schema_version: 1\n", encoding="utf-8")
    issues = _issues(tmp_path)
    assert [(issue.file, issue.rule) for issue in issues] == [
        ("pipelines/cp_alpha.yaml", "R13"), ("pipelines/cp_beta.yaml", "R13")]
    assert "registry_tools fmt" in issues[0].message
def _base_and_head(tmp_path, base_docs, head_docs):
    base, head = tmp_path / "base", tmp_path / "head"
    write_registry(base, *base_docs)
    write_registry(head, *head_docs)
    return head, base


def test_r8_appending_a_version_and_withdrawing_is_allowed(tmp_path):
    head, base = _base_and_head(
        tmp_path, [pipeline_doc("cp_alpha")],
        [pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1", withdrawn=True),
                                            version_doc("cv_alpha_2", "b", parent="cv_alpha_1")])])
    assert _issues(head, base) == []


def test_r8_rename_with_moved_to_keeps_ids(tmp_path):
    head, base = _base_and_head(
        tmp_path, [pipeline_doc("cp_alpha")],
        [{"schema_version": 1, "id": "cp_alpha", "moved_to": "cp_alpha_two"},
         pipeline_doc("cp_alpha_two", versions=[version_doc("cv_alpha_1")])])
    assert _issues(head, base) == []


def test_r8_removed_pipeline_and_version(tmp_path):
    head, base = _base_and_head(
        tmp_path,
        [pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1"),
                                            version_doc("cv_alpha_2", "b", parent="cv_alpha_1")]),
         pipeline_doc("cp_beta", versions=[version_doc("cv_beta_1", "c")])],
        [pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1")])])
    messages = [issue.message for issue in _issues(head, base)]
    assert any("cp_beta" in m for m in messages)
    assert any("cv_alpha_2" in m for m in messages)
    assert {issue.rule for issue in _issues(head, base)} == {"R8"}


def test_r8_changed_commit_parent_repo_kind_and_unwithdraw(tmp_path):
    head, base = _base_and_head(
        tmp_path,
        [pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1", withdrawn=True),
                                            version_doc("cv_alpha_2", "b", parent="cv_alpha_1")])],
        [pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1", "e"),
                                            version_doc("cv_alpha_2", "b", parent=None, kind="optimization",
                                                        repo="https://github.com/org/fork")])])
    pointers = sorted(issue.pointer for issue in _issues(head, base) if issue.rule == "R8")
    assert pointers == ["/versions/0/commit", "/versions/0/withdrawn",
                        "/versions/1/kind", "/versions/1/parent", "/versions/1/repo"]
