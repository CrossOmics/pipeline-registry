from registry_tools.ranking_page import render_landing, render_ranking_page, write_pages

YEARS = [2024, 2025, 2026]


def _item(pid, name, priority, *, status="active", reason=None, kind="tool", stale_since=None, archived=False):
    activity = None if reason else {"commits": 3, "releases": 1, "merged_prs": 2, "closed_issues": 4, "raw": 16,
                                    "last_commit_at": "2026-03-09T10:00:00Z", "archived": archived, "stars": 1,
                                    "moved_to_url": None, "error": None}
    return {"id": pid, "name": name, "kind": kind, "status": status, "metrics": {
        "priority": priority, "priority_reason": reason, "stale_since": stale_since, "activity": activity,
        "citations_by_year": None if reason else {"2024": 120, "2025": 90, "2026": 31}}}


def _index(*items):
    return {"registry_commit": "abc1234" + "0" * 33, "metrics_collected_at": "2026-11-02T03:05:10Z",
            "config": {"citation_window_years": 3, "citation_years": YEARS, "activity_window_days": 365},
            "pipelines": list(items)}


def _section(html, heading, next_heading):
    return html.split(f"<h2>{heading}</h2>", 1)[1].split(f"<h2>{next_heading}</h2>", 1)[0]


def test_ranking_is_ordered_by_risk_score_then_name():
    html = render_ranking_page(_index(_item("cp_a", "Zeta", 0.2), _item("cp_b", "Beta", 0.8),
                                      _item("cp_c", "Alpha", 0.8, kind="workflow", stale_since="2026-10-26T03:00:00Z",
                                            archived=True)))
    ranking = _section(html, "Ranking", "Mature (stable) pipelines")
    assert ranking.index(">Alpha<") < ranking.index(">Beta<") < ranking.index(">Zeta<")
    assert "0.8000" in ranking and "workflow" in ranking and "2026-03-09" in ranking
    assert "3 / 1 / 2 / 4" in ranking
    assert '<span class="badge">archived</span><span class="badge">stale</span>' in ranking
    assert 'href="https://github.com/CrossOmics/pipeline-registry/blob/main/pipelines/cp_c.yaml"' in ranking


def test_stable_pipelines_have_their_own_table():
    html = render_ranking_page(_index(_item("cp_a", "Alpha", 0.5), _item("cp_s", "Steady", 0.9, status="stable")))
    assert ">Steady<" not in _section(html, "Ranking", "Mature (stable) pipelines")
    assert ">Steady<" in _section(html, "Mature (stable) pipelines", "Not ranked")


def test_not_ranked_lists_each_pipeline_with_its_reason():
    html = render_ranking_page(_index(_item("cp_a", "Alpha", 0.5), _item("cp_n", "Nopaper", None, reason="no_paper"),
                                      _item("cp_u", "Gitlab", None, reason="unsupported_host")))
    not_ranked = _section(html, "Not ranked", "How the score is computed")
    assert "<li>Gitlab: repository is not on GitHub</li>" in not_ranked
    assert "<li>Nopaper: no paper registered</li>" in not_ranked
    assert ">Nopaper<" not in _section(html, "Ranking", "Mature (stable) pipelines")


def test_citation_columns_follow_the_window_and_label_the_current_year():
    html = render_ranking_page(_index(_item("cp_a", "Alpha", 0.5)))
    assert "<th class=\"n\">Citations 2024</th><th class=\"n\">Citations 2025</th>" in html
    assert "<th class=\"n\">Citations 2026 (YTD)</th>" in html
    assert '<td class="n">120</td><td class="n">90</td><td class="n">31</td>' in html
    assert "2024–2026 (2026 to date)" in html.split("<h2>How the score is computed</h2>", 1)[1]


def test_page_is_static_escaped_and_deterministic():
    index = _index(_item("cp_a", "<b>A&B</b>", 0.5))
    html = render_ranking_page(index)
    assert "&lt;b&gt;A&amp;B&lt;/b&gt;" in html and "<b>A&B</b>" not in html
    assert "<script" not in html and "<link" not in html and " src=" not in html
    assert "Pipelines that may need community attention" in html
    assert 'href="https://github.com/CrossOmics/pipeline-registry/commit/abc1234' in html
    assert render_ranking_page(index) == html


def test_write_pages_writes_the_landing_and_ranking_pages(tmp_path):
    index = _index(_item("cp_a", "Alpha", 0.5))
    write_pages(index, tmp_path)
    assert (tmp_path / "ranking" / "index.html").read_text(encoding="utf-8") == render_ranking_page(index)
    landing = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert landing == render_landing(index)
    assert 'href="ranking/"' in landing and 'href="index.json"' in landing
