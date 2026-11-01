from helpers import REPO_ROOT
from registry_tools.schema import build_schema, load_schema, load_vocab, render_schema


def test_committed_schema_matches_the_vocabulary():
    expected = render_schema(build_schema(load_vocab(REPO_ROOT / "schema" / "vocab.yaml")))
    assert (REPO_ROOT / "schema" / "pipeline.schema.json").read_text(encoding="utf-8") == expected


def test_vocab_values_become_enums():
    schema = load_schema(REPO_ROOT)
    pipeline = schema["$defs"]["pipeline"]
    assert "scrna-seq" in pipeline["properties"]["modalities"]["items"]["enum"]
    assert pipeline["properties"]["domain"]["enum"][0] == "transcriptomics"
