"""Recent citations per paper: OpenAlex first, Semantic Scholar as fallback (SPEC-02 §3.3)."""

import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional

import httpx

from registry_tools.http import request_json
from registry_tools.model import normalize_doi

OPENALEX = "https://api.openalex.org"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1"
PREPRINT_HOSTS = ("arxiv.org", "biorxiv.org", "medrxiv.org")
CITATION_CAP = 10_000
PAGE_SIZE = 1000


def window_years(today: date, window: int) -> List[int]:
    """`window` calendar years ending with the current one, which counts year to date: 3 -> [Y-2, Y-1, Y]."""
    return list(range(today.year - window + 1, today.year + 1))


@dataclass
class CitationResult:
    source: Optional[str]
    total: Optional[int] = None
    recent: Optional[int] = None
    by_year: Dict[str, int] = field(default_factory=dict)
    work_id: Optional[str] = None
    error: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


class OpenAlexClient:
    def __init__(self, http: httpx.Client, mailto: Optional[str], sleep: Callable[[float], None] = time.sleep):
        self.http, self.mailto, self.sleep = http, mailto, sleep

    def work(self, doi: str) -> Optional[Dict[str, Any]]:
        params = {"mailto": self.mailto} if self.mailto else {}
        return request_json(self.http, "GET", f"{OPENALEX}/works/doi:{doi}", params=params, sleep=self.sleep)


class SemanticScholarClient:
    def __init__(self, http: httpx.Client, api_key: Optional[str] = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.http, self.sleep = http, sleep
        self.headers = {"x-api-key": api_key} if api_key else {}
        self.interval = 0.0 if api_key else 1.0  # unauthenticated: about 1 request per second

    def _get(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.interval:
            self.sleep(self.interval)
        return request_json(self.http, "GET", url, params=params, headers=self.headers, sleep=self.sleep)

    def paper(self, key: str) -> Optional[Dict[str, Any]]:
        """`key` is `DOI:<doi>` or `URL:<url>`."""
        return self._get(f"{SEMANTIC_SCHOLAR}/paper/{key}", {"fields": "citationCount"})

    def citation_years(self, paper_id: str) -> List[Optional[int]]:
        years: List[Optional[int]] = []
        offset = 0
        while offset < CITATION_CAP:
            body = self._get(f"{SEMANTIC_SCHOLAR}/paper/{paper_id}/citations",
                             {"fields": "year", "limit": min(PAGE_SIZE, CITATION_CAP - offset), "offset": offset})
            if not body:
                break
            years += [(item.get("citingPaper") or {}).get("year") for item in body.get("data") or []]
            if body.get("next") is None:
                break
            offset = int(body["next"])
        return years[:CITATION_CAP]


class CitationCollector:
    def __init__(self, openalex: OpenAlexClient, semantic_scholar: SemanticScholarClient, years: List[int]):
        self.openalex, self.semantic_scholar, self.years = openalex, semantic_scholar, years

    def collect(self, paper: Dict[str, Any]) -> CitationResult:
        if paper.get("doi"):
            doi = normalize_doi(paper["doi"])
            work = self.openalex.work(doi)
            if work is not None:
                return self._from_openalex(work)
            return self._from_semantic_scholar(f"DOI:{doi}")
        url = paper.get("url") or ""
        if any(host in url for host in PREPRINT_HOSTS):
            return self._from_semantic_scholar(f"URL:{url}")
        return CitationResult(source=None, error="not_found")

    def _from_openalex(self, work: Dict[str, Any]) -> CitationResult:
        by_year = {str(year): 0 for year in self.years}
        for entry in work.get("counts_by_year") or []:
            if entry.get("year") in self.years:
                by_year[str(entry["year"])] = int(entry["cited_by_count"])
        return CitationResult("openalex", total=int(work.get("cited_by_count") or 0),
                              recent=sum(by_year.values()), by_year=by_year, work_id=work.get("id"))

    def _from_semantic_scholar(self, key: str) -> CitationResult:
        paper = self.semantic_scholar.paper(key)
        if paper is None:
            return CitationResult(source=None, error="not_found")
        by_year = {str(year): 0 for year in self.years}
        for year in self.semantic_scholar.citation_years(paper["paperId"]):
            if year in self.years:
                by_year[str(year)] += 1
        return CitationResult("semantic_scholar", total=int(paper.get("citationCount") or 0),
                              recent=sum(by_year.values()), by_year=by_year, work_id=f"s2:{paper['paperId']}")
