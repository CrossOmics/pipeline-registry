"""The public risk ranking page and the Pages landing page (SPEC-02 §3.7), rendered from the built index alone.
Static English HTML: inline CSS, no scripts, no external requests, deterministic for a given index."""

from html import escape
from pathlib import Path
from typing import Any, Dict, List

from registry_tools.model import primary_repository

REPOSITORY_URL = "https://github.com/CrossOmics/pipeline-registry"
COMMUNITY_UPDATES_URL = "https://github.com/BioCode-Commons"
TITLE = "Pipelines that may need community attention"
REASONS = {
    "deprecated": "deprecated",
    "no_paper": "no paper registered",
    "no_citation_data": "no citation data for its papers",
    "no_repo": "no repository registered",
    "unsupported_host": "repository is not on GitHub",
    "repo_unreachable": "repository could not be read",
}
_STYLE = (
    "body{font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:72rem;padding:1.5rem 1rem;"
    "background:#fff;color:#1d1d1f}"
    ".wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}"
    "th,td{border-bottom:1px solid #ddd;padding:.4rem .5rem;text-align:left;white-space:nowrap}"
    ".n{text-align:right}"
    ".badge{border:1px solid #999;border-radius:.6rem;font-size:.75rem;margin-left:.3rem;padding:0 .4rem}"
    "@media (prefers-color-scheme:dark){body{background:#111;color:#eee}th,td{border-color:#333}a{color:#8ab4f8}}"
)


def _page(title: str, body: str) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{escape(title)}</title><style>{_STYLE}</style></head>\n<body>\n{body}\n</body></html>\n")


def _badges(item: Dict[str, Any]) -> str:
    metrics = item["metrics"]
    activity = metrics.get("activity") or {}
    names = [name for name, on in (("archived", activity.get("archived")), ("moved", activity.get("moved_to_url")),
                                   ("stale", metrics.get("stale_since"))) if on]
    return "".join(f'<span class="badge">{name}</span>' for name in names)


def _maintenance(item: Dict[str, Any]) -> str:
    record = item.get("biocode_maintenance")
    if not record:
        return "Not registered"
    if record["status"] == "planned":
        return "Planned"
    return f'<a href="{escape(record["repository"], quote=True)}">Available</a>'


def _table(items: List[Dict[str, Any]], years: List[int]) -> str:
    if not items:
        return "<p>None.</p>"
    labels = [f"{year} (YTD)" if year == years[-1] else str(year) for year in years]
    head = ('<tr><th class="n">#</th><th>Pipeline</th><th>Kind</th><th class="n">Risk score</th>'
            "<th>Original GitHub update</th><th>BioCode maintenance</th>" + "".join(f'<th class="n">Citations {label}</th>' for label in labels)
            + "<th>Commits / releases / merged PRs / closed issues</th></tr>")
    rows = []
    for rank, item in enumerate(items, start=1):
        metrics, activity = item["metrics"], item["metrics"]["activity"]
        by_year = metrics.get("citations_by_year") or {}
        link = f"{REPOSITORY_URL}/blob/main/pipelines/{item['id']}.yaml"
        date = escape((activity.get("last_commit_at") or "")[:10]) or "—"
        upstream = primary_repository(item)
        updated = f'<a href="{escape(upstream, quote=True)}">{date}</a>' if upstream else date
        rows.append(
            f'<tr><td class="n">{rank}</td><td><a href="{escape(link)}">{escape(item["name"])}</a>{_badges(item)}</td>'
            f'<td>{escape(item["kind"])}</td><td class="n">{metrics["priority"]:.4f}</td>'
            f'<td>{updated}</td><td>{_maintenance(item)}</td>'
            + "".join(f'<td class="n">{int(by_year.get(str(year), 0))}</td>' for year in years)
            + f'<td>{activity["commits"]} / {activity["releases"]} / {activity["merged_prs"]} / '
              f'{activity["closed_issues"]}</td></tr>')
    return '<div class="wrap"><table>\n' + head + "\n" + "\n".join(rows) + "\n</table></div>"


def _method(index: Dict[str, Any]) -> str:
    years = index["config"]["citation_years"]
    days = index["config"]["activity_window_days"]
    return (
        "<p><strong>Risk score = CitationScore × (1 − ActivityScore)</strong>, rounded to four decimals.</p>\n<ul>"
        "<li>Both scores are mid-rank percentiles among the ranked pipelines: (number of pipelines below + half "
        "the number tied with it) / (number ranked − 1), or 0.5 when only one pipeline is ranked.</li>"
        f"<li>CitationScore uses the citations of the pipeline's papers in {years[0]}–{years[-1]} "
        f"({years[-1]} to date), from OpenAlex, or Semantic Scholar when OpenAlex has no record. "
        "A paper listed twice counts once.</li>"
        f"<li>ActivityScore uses the original author's primary GitHub repository over the last {days} days: commits + 5 × releases "
        "+ 2 × merged PRs + closed issues. An archived repository counts as 0.</li>"
        "<li>Pipelines without a paper with citation data, or without a readable GitHub repository, are not "
        "ranked, and neither are deprecated ones.</li>"
        "<li>BioCode maintenance is registered separately: Available links to a published replacement; Planned "
        "is not yet available; Not registered means no replacement has been recorded. "
        "A replacement's activity never changes the original repository's score.</li></ul>"
    )


def render_ranking_page(index: Dict[str, Any]) -> str:
    years = index["config"]["citation_years"]
    pipelines = index["pipelines"]
    eligible = [item for item in pipelines if item["metrics"]["priority_reason"] is None]
    def order(item: Dict[str, Any]) -> tuple:
        return -item["metrics"]["priority"], item["name"]

    ranked = sorted((item for item in eligible if item["status"] != "stable"), key=order)
    stable = sorted((item for item in eligible if item["status"] == "stable"), key=order)
    excluded = sorted((item for item in pipelines if item["metrics"]["priority_reason"] is not None),
                      key=lambda item: item["name"])
    commit = index["registry_commit"]
    collected = index.get("metrics_collected_at") or "not yet"
    not_ranked = ("<ul>" + "".join(
        f"<li>{escape(item['name'])}: {escape(REASONS.get(item['metrics']['priority_reason'], item['metrics']['priority_reason']))}</li>"
        for item in excluded) + "</ul>") if excluded else "<p>None.</p>"
    body = (
        f"<h1>{TITLE}</h1>\n"
        f"<p>Metrics collected {escape(collected)} · registry commit "
        f'<a href="{REPOSITORY_URL}/commit/{escape(commit)}">{escape(commit[:7])}</a></p>\n'
        "<p>Pipelines whose papers are widely cited while their repositories have seen little recent activity "
        "rank highest: the community may want to take a look at them.</p>\n"
        '<p><strong>Community updates:</strong> '
        f'<a href="{COMMUNITY_UPDATES_URL}">BioCode Commons</a>. '
        'New versions of pipelines that need maintenance will be shared here, '
        'starting with STAR and MAFFT.</p>\n'
        f"<h2>Ranking</h2>\n{_table(ranked, years)}\n"
        "<h2>Mature (stable) pipelines</h2>\n<p>Marked stable by their maintainers, so little activity is "
        f"expected.</p>\n{_table(stable, years)}\n"
        f"<h2>Not ranked</h2>\n{not_ranked}\n"
        f"<h2>How the score is computed</h2>\n{_method(index)}"
    )
    return _page(TITLE, body)


def render_landing(index: Dict[str, Any]) -> str:
    body = (
        "<h1>CrossOmics community pipeline registry</h1>\n"
        f"<p>{len(index['pipelines'])} registered pipelines.</p>\n<ul>"
        f'<li><a href="ranking/">{TITLE}</a></li>'
        '<li><a href="index.json">index.json</a> (<a href="index.json.sha256">sha256</a>)</li>'
        f'<li><a href="{REPOSITORY_URL}">Registry repository</a></li>'
        f'<li><a href="{COMMUNITY_UPDATES_URL}">BioCode Commons</a> — community updates '
        '(STAR and MAFFT coming soon)</li></ul>'
    )
    return _page("CrossOmics pipeline registry", body)


def write_pages(index: Dict[str, Any], out_dir: Path) -> None:
    (out_dir / "ranking").mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render_landing(index), encoding="utf-8")
    (out_dir / "ranking" / "index.html").write_text(render_ranking_page(index), encoding="utf-8")
