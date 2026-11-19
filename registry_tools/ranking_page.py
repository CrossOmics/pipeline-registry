"""The public risk ranking page and the Pages landing page (SPEC-02 §3.7), rendered from the built index alone.
Static English HTML: inline CSS, no scripts, no external requests, deterministic for a given index."""

from html import escape
from pathlib import Path
from typing import Any, Dict, List

from registry_tools.model import primary_repository

REPOSITORY_URL = "https://github.com/CrossOmics/pipeline-registry"
COMMUNITY_HOME_URL = "https://www.cross-omics.com/"
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
_STYLE = Path(__file__).with_name("ranking.css").read_text(encoding="utf-8")
_NAV = (
    ("Submit a Contribution", COMMUNITY_HOME_URL + "community/submit"),
    ("Explore Existing Tools", COMMUNITY_HOME_URL),
    ("Maintenance Needed", "https://crossomics.github.io/pipeline-registry/ranking/"),
    ("Tools Wanted", COMMUNITY_HOME_URL + "community/bounties"),
)


def _navigation(*, active: bool = False) -> str:
    return "".join(
        f'<a href="{url}"' + (' aria-current="page"' if active and label == "Maintenance Needed" else "")
        + f'>{label}</a>' for label, url in _NAV
    )


def _page(title: str, body: str, *, ranking: bool = False) -> str:
    navigation = (
        '<div class="breadcrumb"><a href="' + COMMUNITY_HOME_URL + '">Home</a><span>/</span>'
        '<span>Community Tracking</span></div>'
        '<nav class="community-nav" aria-label="Community">' + _navigation(active=ranking) + '</nav>'
    ) if ranking else ""
    main_class = "container" if ranking else "container landing"
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="color-scheme" content="only light">'
            f"<title>{escape(title)}</title><style>{_STYLE}</style></head>\n<body>\n"
            f'<header class="site-header"><div class="container"><a class="logo" href="{COMMUNITY_HOME_URL}">'
            'CrossOmics <small>Community</small></a></div></header>'
            f'<main class="{main_class}">{navigation}{body}</main>'
            '<footer class="site-footer"><div class="container"><nav aria-label="Footer">'
            + _navigation() + '</nav><a href="' + COMMUNITY_HOME_URL + '">Back to home</a></div></footer>'
            '\n</body></html>\n')


def _badges(item: Dict[str, Any]) -> str:
    metrics = item["metrics"]
    activity = metrics.get("activity") or {}
    names = [name for name, on in (("archived", activity.get("archived")), ("moved", activity.get("moved_to_url")),
                                   ("stale", metrics.get("stale_since"))) if on]
    return "".join(f'<span class="badge">{name}</span>' for name in names)


def _maintenance(item: Dict[str, Any]) -> str:
    record = item.get("biocode_maintenance")
    if not record:
        return '<span class="maintenance">Not registered</span>'
    if record["status"] == "planned":
        return '<span class="maintenance planned">Planned</span>'
    return f'<span class="maintenance available"><a href="{escape(record["repository"], quote=True)}">Available</a></span>'


def _table(items: List[Dict[str, Any]], years: List[int], label: str = "Ranking") -> str:
    if not items:
        return '<p class="empty">None.</p>'
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
            f'<td>{escape(item["kind"])}</td><td class="n score">{metrics["priority"]:.4f}'
            f'<span class="score-track" aria-hidden="true"><span style="width:{min(100, max(0, metrics["priority"] * 100)):.2f}%"></span></span></td>'
            f'<td>{updated}</td><td>{_maintenance(item)}</td>'
            + "".join(f'<td class="n">{int(by_year.get(str(year), 0))}</td>' for year in years)
            + f'<td>{activity["commits"]} / {activity["releases"]} / {activity["merged_prs"]} / '
              f'{activity["closed_issues"]}</td></tr>')
    return (f'<div class="wrap" role="region" aria-label="{escape(label, quote=True)} data" tabindex="0"><table>'
            f'<caption class="sr-only">{escape(label)}: maintenance priority, citations and original repository activity</caption>'
            + "<thead>" + head + "</thead><tbody>" + "\n".join(rows) + "</tbody></table></div>")


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
    not_ranked = ('<ul class="excluded">' + "".join(
        f"<li>{escape(item['name'])}: {escape(REASONS.get(item['metrics']['priority_reason'], item['metrics']['priority_reason']))}</li>"
        for item in excluded) + "</ul>") if excluded else "<p>None.</p>"
    body = (
        f'<a class="home-link" href="{COMMUNITY_HOME_URL}">&larr; Back to home</a>'
        '<section class="intro" aria-labelledby="page-title">'
        '<h1 id="page-title">Maintenance Needed</h1>'
        f'<p class="intro-subtitle">{TITLE}</p>'
        '<p>Pipelines whose papers are widely cited while their repositories have seen little recent activity '
        'rank highest: the community may want to take a look at them.</p></section>'
        '<p class="updates"><strong>Community updates:</strong> '
        f'<a href="{COMMUNITY_UPDATES_URL}">BioCode Commons</a>. '
        'New versions of pipelines that need maintenance will be shared here, '
        'starting with STAR and MAFFT.</p>'
        '<section class="ranking-section"><div class="section-top"><h2>Ranking</h2>'
        f'<p>{len(ranked)} ranked pipelines &middot; Highest priority first</p></div>'
        '<p class="section-description">Scroll the table horizontally to see all citation and activity metrics.</p>'
        f'{_table(ranked, years)}</section>'
        '<div class="supporting"><section class="ranking-section">'
        '<h2>Mature (stable) pipelines</h2><p class="section-description">Marked stable by their maintainers, so little activity is '
        f'expected.</p>{_table(stable, years, "Stable pipelines")}</section>'
        '<section class="ranking-section"><h2>Not ranked</h2>'
        '<p class="section-description">Entries without enough data to score, or marked deprecated.</p>'
        f'{not_ranked}</section></div>'
        '<details class="method"><summary><h2>How the score is computed</h2></summary>'
        f'<div class="method-content">{_method(index)}</div></details>'
    )
    return _page(TITLE, body, ranking=True)


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
