"""One collection run over every pipeline; a failed pipeline keeps its last metrics (SPEC-02 §3.5)."""

import sys
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from registry_tools import CONFIG
from registry_tools.http import CollectError
from registry_tools.model import Registry, iso, paper_key, primary_repository


def _collect_one(pipeline: Dict[str, Any], github, citations, now: datetime) -> Dict[str, Any]:
    papers = {paper_key(paper): citations.collect(paper).to_json() for paper in pipeline.get("papers") or []}
    repository = primary_repository(pipeline)
    if repository is None:
        activity, reason = None, "no_repo"
    else:
        activity, reason = github.collect(repository, now)
    return {"papers": papers, "activity": activity, "activity_reason": reason}


def collect_metrics(registry: Registry, previous: Optional[Dict[str, Any]], github, citations,
                    now: datetime) -> Tuple[Dict[str, Any], int, int]:
    """(metrics, failed, attempted). `github` and `citations` are a GitHubCollector and a CitationCollector."""
    earlier = (previous or {}).get("pipelines") or {}
    collected_at = iso(now)
    pipelines: Dict[str, Dict[str, Any]] = {}
    failed = 0
    for pipeline in registry.pipelines():
        pid = pipeline["id"]
        try:
            pipelines[pid] = {**_collect_one(pipeline, github, citations, now),
                              "collected_at": collected_at, "stale_since": None, "error": None}
        except CollectError as exc:
            failed += 1
            print(f"{pid}: {exc}", file=sys.stderr)
            if pid in earlier:
                pipelines[pid] = {**earlier[pid], "stale_since": earlier[pid].get("stale_since") or collected_at}
            else:
                pipelines[pid] = {"papers": {}, "activity": None, "activity_reason": None, "collected_at": None,
                                  "stale_since": collected_at, "error": str(exc)}
    return {"collected_at": collected_at, "config": CONFIG, "pipelines": pipelines}, failed, len(pipelines)
