"""The published index.json (SPEC-02 §4): registry content plus metrics and scores."""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from registry_tools import CITATION_WINDOW_YEARS, CONFIG, SCHEMA_VERSION
from registry_tools.citations import window_years
from registry_tools.model import Registry, contributor_id, iso, normalize_doi, paper_key
from registry_tools.scoring import ScoreInput, score_all

_PIPELINE_FIELDS = ("id", "name", "kind", "description", "domain", "status")
_LIST_FIELDS = ("modalities", "inputs", "outputs", "algorithms", "keywords", "repositories")
_TEST_DATASET_KEYS = ("accession", "url", "sha256", "description")
_EFFECT_METRIC_KEYS = ("name", "value", "baseline", "unit")


class _Contributors:
    """First occurrence wins; later spellings of the same id only warn (SPEC-02 §4)."""

    def __init__(self) -> None:
        self.by_id: Dict[str, Dict[str, Any]] = {}

    def refs(self, contributors: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
        refs = []
        for contributor in contributors or []:
            cid = contributor_id(contributor)
            known = self.by_id.get(cid)
            if known is None:
                self.by_id[cid] = {"id": cid, "name": contributor["name"], "github": contributor.get("github"),
                                   "orcid": contributor.get("orcid")}
            elif known["name"] != contributor["name"]:
                print(f"warning: {cid} is named both {known['name']!r} and {contributor['name']!r}; "
                      f"using the first", file=sys.stderr)
            refs.append({"contributor_id": cid, "role": contributor["role"]})
        return refs


def _paper(paper: Dict[str, Any], collected: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {"doi": normalize_doi(paper["doi"]) if paper.get("doi") else None, "url": paper.get("url"),
            "title": paper.get("title"), "citations": collected}


def _citations_by_year(papers: List[Dict[str, Any]], years: List[int]) -> Optional[Dict[str, int]]:
    """Per-year citations over papers with data, zero-filled for every window year; a work that two papers
    resolve to counts once. None when no paper has data."""
    by_year: Optional[Dict[str, int]] = None
    works = set()
    for paper in papers:
        citations = paper["citations"]
        if not citations or citations.get("source") is None:
            continue
        work_id = citations.get("work_id")
        if work_id and work_id in works:
            continue
        if work_id:
            works.add(work_id)
        if by_year is None:
            by_year = {str(year): 0 for year in years}
        for year, count in (citations.get("by_year") or {}).items():
            if year in by_year:
                by_year[year] += int(count)
    return by_year


def _test_dataset(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return {key: value.get(key) for key in _TEST_DATASET_KEYS} if value else None


def _improvement_effect(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    return {"summary": value.get("summary"),
            "metrics": [{key: metric.get(key) for key in _EFFECT_METRIC_KEYS} for metric in value.get("metrics") or []]}


def _version(version: Dict[str, Any], contributors: _Contributors) -> Dict[str, Any]:
    return {
        "id": version["id"], "kind": version["kind"], "label": version["label"], "repo": version["repo"],
        "commit": version["commit"], "parent": version["parent"], "released_at": version.get("released_at"),
        "contributors": contributors.refs(version.get("contributors")),
        "improvement": version.get("improvement"),
        "test_dataset": _test_dataset(version.get("test_dataset")),
        "improvement_effect": _improvement_effect(version.get("improvement_effect")),
        "gardener_package": version.get("gardener_package"),
        "withdrawn": bool(version.get("withdrawn", False)),
    }


def _citation_years(metrics: Optional[Dict[str, Any]], now: datetime) -> List[int]:
    collected_at = (metrics or {}).get("collected_at")
    moment = datetime.fromisoformat(collected_at.replace("Z", "+00:00")) if collected_at else now
    return window_years(moment.date(), CITATION_WINDOW_YEARS)


def build_index(registry: Registry, metrics: Optional[Dict[str, Any]], registry_commit: str,
                now: datetime, vocab: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    collected = (metrics or {}).get("pipelines") or {}
    years = _citation_years(metrics, now)
    contributors = _Contributors()
    drafts = []
    inputs = []
    for pipeline in registry.pipelines():
        pid = pipeline["id"]
        entry = collected.get(pid) or {}
        papers = [_paper(paper, (entry.get("papers") or {}).get(paper_key(paper)))
                  for paper in pipeline.get("papers") or []]
        by_year = _citations_by_year(papers, years)
        recent = sum(by_year.values()) if by_year is not None else None
        activity = entry.get("activity")
        inputs.append(ScoreInput(pid, pipeline["status"], len(papers), recent,
                                 activity["raw"] if activity else None, entry.get("activity_reason")))
        item = {name: pipeline[name] for name in _PIPELINE_FIELDS}
        item.update({name: list(pipeline.get(name) or []) for name in _LIST_FIELDS})
        item["papers"] = papers
        item["contributors"] = contributors.refs(pipeline.get("contributors"))
        item["versions"] = [_version(version, contributors) for version in pipeline["versions"]]
        item["metrics"] = {"collected_at": entry.get("collected_at"), "stale_since": entry.get("stale_since"),
                           "recent_citations": recent, "citations_by_year": by_year, "activity": activity}
        drafts.append(item)
    scores = score_all(inputs)
    for item in drafts:
        item["metrics"].update(scores[item["id"]])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso(now),
        "registry_commit": registry_commit,
        "metrics_collected_at": (metrics or {}).get("collected_at"),
        "config": {**CONFIG, "citation_years": years},
        "vocab": dict(vocab or {}),
        "pipelines": drafts,
        "contributors": list(contributors.by_id.values()),
        "moved": dict(sorted(registry.moved().items())),
    }


def serialize(index: Dict[str, Any]) -> bytes:
    return json.dumps(index, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def write_dist(index: Dict[str, Any], out_dir: Path) -> str:
    body = serialize(index)
    digest = hashlib.sha256(body).hexdigest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.json").write_bytes(body)
    (out_dir / "index.json.sha256").write_text(digest + "\n", encoding="utf-8")
    return digest
