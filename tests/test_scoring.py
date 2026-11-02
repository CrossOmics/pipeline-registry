import pytest

from registry_tools.scoring import ScoreInput, percentile_ranks, priority_reason, score_all


def _item(pid, citations=10, activity=10, status="active", papers=1, reason=None):
    return ScoreInput(pid, status, papers, citations, activity, reason)


def test_percentiles_single_ties_and_spread():
    assert percentile_ranks({"a": 3}) == {"a": 0.5}
    assert percentile_ranks({"a": 1, "b": 1, "c": 1}) == {"a": 0.5, "b": 0.5, "c": 0.5}
    assert percentile_ranks({"a": 1, "b": 2, "c": 3}) == {"a": 0.0, "b": 0.5, "c": 1.0}
    assert percentile_ranks({"a": 1, "b": 2, "c": 2}) == {"a": 0.0, "b": 0.75, "c": 0.75}


@pytest.mark.parametrize("item, reason", [
    (_item("x", status="deprecated", papers=0), "deprecated"),
    (_item("x", papers=0, citations=None), "no_paper"),
    (_item("x", citations=None, activity=None, reason="no_repo"), "no_citation_data"),
    (_item("x", activity=None, reason="no_repo"), "no_repo"),
    (_item("x", activity=None, reason="unsupported_host"), "unsupported_host"),
    (_item("x", activity=None, reason="repo_unreachable"), "repo_unreachable"),
    (_item("x", activity=None, reason=None), "repo_unreachable"),
    (_item("x", status="stable"), None),
])
def test_priority_reason_order(item, reason):
    assert priority_reason(item) == reason


def test_high_citation_low_activity_ranks_first():
    scores = score_all([
        _item("quiet_famous", citations=100, activity=1),
        _item("busy_famous", citations=90, activity=500),
        _item("obscure", citations=5, activity=50),
        _item("no_paper", papers=0, citations=None),
    ])
    ranked = sorted((pid for pid in scores if scores[pid]["priority"] is not None),
                    key=lambda pid: -scores[pid]["priority"])
    assert ranked[0] == "quiet_famous"
    assert scores["quiet_famous"] == {"citation_score": 1.0, "activity_score": 0.0, "priority": 1.0,
                                      "priority_reason": None}
    assert scores["no_paper"] == {"citation_score": None, "activity_score": None, "priority": None,
                                  "priority_reason": "no_paper"}


def test_ineligible_items_do_not_shift_percentiles():
    with_extra = score_all([_item("a", 1, 1), _item("b", 2, 2), _item("dead", status="deprecated")])
    without = score_all([_item("a", 1, 1), _item("b", 2, 2)])
    assert with_extra["a"] == without["a"] and with_extra["b"] == without["b"]
