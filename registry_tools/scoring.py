"""Percentile scores and the risk score, stored as `priority` (SPEC-02 §3.4)."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ScoreInput:
    pipeline_id: str
    status: str
    paper_count: int
    recent_citations: Optional[int]  # None when no paper had citation data
    activity_raw: Optional[int]  # None when the primary repo was not collected
    activity_reason: Optional[str]  # why activity_raw is None: no_repo | unsupported_host | repo_unreachable


def priority_reason(item: ScoreInput) -> Optional[str]:
    if item.status == "deprecated":
        return "deprecated"
    if item.paper_count == 0:
        return "no_paper"
    if item.recent_citations is None:
        return "no_citation_data"
    if item.activity_raw is None:
        return item.activity_reason or "repo_unreachable"
    return None


def percentile_ranks(values: Dict[str, float]) -> Dict[str, float]:
    """Mid-rank percentile in [0, 1]; ties share a rank, a single value is 0.5."""
    n = len(values)
    if n == 1:
        return {key: 0.5 for key in values}
    population = list(values.values())
    ranks = {}
    for key, value in values.items():
        less = sum(1 for other in population if other < value)
        equal = sum(1 for other in population if other == value)
        ranks[key] = (less + 0.5 * (equal - 1)) / (n - 1)
    return ranks


def score_all(items: List[ScoreInput]) -> Dict[str, Dict[str, Any]]:
    reasons = {item.pipeline_id: priority_reason(item) for item in items}
    eligible = [item for item in items if reasons[item.pipeline_id] is None]
    citation = percentile_ranks({i.pipeline_id: i.recent_citations for i in eligible}) if eligible else {}
    activity = percentile_ranks({i.pipeline_id: i.activity_raw for i in eligible}) if eligible else {}
    scores: Dict[str, Dict[str, Any]] = {}
    for item in items:
        pid = item.pipeline_id
        if reasons[pid] is not None:
            scores[pid] = {"citation_score": None, "activity_score": None, "priority": None,
                           "priority_reason": reasons[pid]}
            continue
        scores[pid] = {
            "citation_score": round(citation[pid], 4),
            "activity_score": round(activity[pid], 4),
            "priority": round(citation[pid] * (1 - activity[pid]), 4),
            "priority_reason": None,
        }
    return scores
