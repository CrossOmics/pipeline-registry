"""Builders for registry documents used across the tests."""

import copy
from pathlib import Path
from typing import Any, Dict, Optional

from registry_tools.model import dump_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = REPO_ROOT / "tests" / "golden"


def version_doc(version_id: str, commit_char: str = "a", *, parent: Optional[str] = None,
                repo: str = "https://github.com/org/alpha", kind: str = "original",
                **overrides: Any) -> Dict[str, Any]:
    doc = {"id": version_id, "kind": kind, "label": "1.0", "repo": repo, "commit": commit_char * 40,
           "parent": parent}
    if kind == "optimization":
        doc["improvement"] = "Faster."
    doc.update(overrides)
    return doc


def pipeline_doc(pipeline_id: str = "cp_alpha", *, versions=None, **overrides: Any) -> Dict[str, Any]:
    doc = {
        "schema_version": 1,
        "id": pipeline_id,
        "name": pipeline_id.replace("cp_", "").replace("_", " ").title(),
        "kind": "tool",
        "description": "A test pipeline.",
        "domain": "transcriptomics",
        "modalities": ["scrna-seq"],
        "inputs": ["fastq"],
        "outputs": ["h5ad"],
        "status": "active",
        "repositories": [{"url": f"https://github.com/org/{pipeline_id[3:]}", "primary": True}],
        "papers": [{"doi": "10.1000/" + pipeline_id[3:]}],
        "contributors": [{"name": "Jane Doe", "github": "janedoe", "role": "creator"}],
        "versions": versions if versions is not None else [version_doc(f"cv_{pipeline_id[3:]}_1")],
    }
    doc.update(overrides)
    return doc


def write_registry(root: Path, *docs: Dict[str, Any], stems: Optional[Dict[str, str]] = None) -> Path:
    """Write each doc, in canonical form, to pipelines/<id>.yaml (or the stem given in `stems`) under root."""
    (root / "pipelines").mkdir(parents=True, exist_ok=True)
    for doc in docs:
        stem = (stems or {}).get(doc["id"], doc["id"])
        (root / "pipelines" / f"{stem}.yaml").write_text(dump_pipeline(doc), encoding="utf-8")
    return root


# The SPEC-02 §2.2 example. tests/golden/ holds its canonical text; Gardener's submission
# code copies those files to check that it writes byte-identical YAML.
GOLDEN_STAR: Dict[str, Any] = {
    "schema_version": 1,
    "id": "cp_star",
    "name": "STAR",
    "kind": "tool",
    "description": "Spliced Transcripts Alignment to a Reference; ultrafast RNA-seq read aligner.",
    "domain": "transcriptomics",
    "modalities": ["bulk-rna-seq", "scrna-seq"],
    "inputs": ["fastq"],
    "outputs": ["bam"],
    "algorithms": ["suffix array", "seed-and-extend"],
    "keywords": ["alignment", "rna-seq", "splice-aware"],
    "status": "active",
    "repositories": [{"url": "https://github.com/alexdobin/STAR", "primary": True}],
    "papers": [{"doi": "10.1093/bioinformatics/bts635", "title": "STAR: ultrafast universal RNA-seq aligner"}],
    "contributors": [{"name": "Alexander Dobin", "github": "alexdobin", "role": "creator"}],
    "versions": [
        {"id": "cv_star_1", "kind": "original", "label": "2.7.10b", "repo": "https://github.com/alexdobin/STAR",
         "commit": "3f1c0a4b9e2d7c6a5b4f3e2d1c0b9a8f7e6d5c4b", "parent": None, "released_at": "2022-11-01",
         "contributors": [{"name": "Alexander Dobin", "github": "alexdobin", "role": "maintainer"}]},
        {"id": "cv_star_2", "kind": "original", "label": "2.7.11b", "repo": "https://github.com/alexdobin/STAR",
         "commit": "5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f", "parent": "cv_star_1", "released_at": "2024-01-25"},
    ],
}

GOLDEN_STAR_APPENDED = copy.deepcopy(GOLDEN_STAR)
GOLDEN_STAR_APPENDED["versions"].append({
    "id": "cv_star_3", "kind": "optimization", "label": "2.7.11b-lowmem", "repo": "https://github.com/alexkim/STAR",
    "commit": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b", "parent": "cv_star_2", "released_at": "2026-10-20",
    "contributors": [{"name": "Alex Kim", "github": "alexkim", "role": "developer"}],
    "improvement": "Sparse suffix array by default; genome generation fits in 16 GB.",
    "test_dataset": {"accession": "SRR6750041", "description": "10x PBMC 1k, read 2 only"},
    "improvement_effect": {"summary": "Peak RSS 31 GB → 14 GB; 0.2% more uniquely mapped reads.",
                           "metrics": [{"name": "peak_rss_gb", "value": 14, "baseline": 31},
                                       {"name": "unique_mapped_pct", "value": 89.3, "baseline": 89.1}]},
    "gardener_package": {"ref": "ghcr.io/alexkim/pipelines/star-lowmem:2.7.11b", "digest": "sha256:" + "4c" * 32},
})
