import shutil

from helpers import REPO_ROOT, pipeline_doc, version_doc, write_registry
from registry_tools.cli import main


def _registry(tmp_path, *docs):
    (tmp_path / "schema").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "schema" / "vocab.yaml", tmp_path / "schema" / "vocab.yaml")
    assert main(["gen-schema", "--root", str(tmp_path)]) == 0
    return write_registry(tmp_path, *docs)


def test_validate_passes_on_a_clean_registry(tmp_path, capsys):
    root = _registry(tmp_path, pipeline_doc("cp_alpha"))
    assert main(["validate", "--root", str(root)]) == 0
    assert "1 pipeline file(s) OK" in capsys.readouterr().out


def test_validate_prints_issues_and_annotations(tmp_path, capsys):
    root = _registry(tmp_path, pipeline_doc("cp_alpha", versions=[version_doc("cv_alpha_1", parent="cv_x_1")]))
    assert main(["validate", "--root", str(root), "--github-annotations"]) == 1
    out = capsys.readouterr().out
    assert "pipelines/cp_alpha.yaml:/versions/0/parent: R3:" in out
    assert "::error file=pipelines/cp_alpha.yaml::/versions/0/parent: R3:" in out


def test_validate_reports_a_stale_schema(tmp_path, capsys):
    root = _registry(tmp_path, pipeline_doc("cp_alpha"))
    (root / "schema" / "pipeline.schema.json").write_text("{}\n", encoding="utf-8")
    assert main(["validate", "--root", str(root)]) == 1
    assert "gen-schema" in capsys.readouterr().out


def test_validate_with_base_applies_r8(tmp_path, capsys):
    base = write_registry(tmp_path / "base", pipeline_doc("cp_alpha"), pipeline_doc("cp_beta",
                          versions=[version_doc("cv_beta_1", "b")]))
    root = _registry(tmp_path / "head", pipeline_doc("cp_alpha"))
    assert main(["validate", "--root", str(root), "--base", str(base)]) == 1
    assert "R8" in capsys.readouterr().out


def test_fmt_rewrites_files_to_canonical_form(tmp_path, capsys):
    root = _registry(tmp_path, pipeline_doc("cp_alpha"), pipeline_doc("cp_beta", versions=[version_doc("cv_beta_1", "b")]))
    alpha = root / "pipelines" / "cp_alpha.yaml"
    canonical = alpha.read_text(encoding="utf-8")
    alpha.write_text("# note\n" + canonical, encoding="utf-8")
    assert main(["fmt", "--check", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "pipelines/cp_alpha.yaml" in out and "cp_beta" not in out
    assert alpha.read_text(encoding="utf-8") == "# note\n" + canonical
    assert main(["fmt", "--root", str(root)]) == 0
    assert alpha.read_text(encoding="utf-8") == canonical
    assert main(["fmt", "--check", "--root", str(root)]) == 0
