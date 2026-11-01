"""Registry files and the normalizations every other module relies on (SPEC-02 §2)."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps `2024-09-12` a string, so documents stay JSON-compatible."""


_Loader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")

PIPELINE_KEYS = ("schema_version", "id", "name", "kind", "description", "domain", "modalities", "inputs",
                 "outputs", "algorithms", "keywords", "status", "repositories", "papers", "contributors", "versions")
MOVED_KEYS = ("schema_version", "id", "moved_to")
VERSION_KEYS = ("id", "kind", "label", "repo", "commit", "parent", "released_at", "contributors", "improvement",
                "test_dataset", "improvement_effect", "gardener_package", "withdrawn")
_NESTED_KEYS = {
    "contributors": ("name", "github", "orcid", "role"),
    "repositories": ("url", "primary"),
    "papers": ("doi", "url", "title"),
    "gardener_package": ("ref", "digest"),
    "test_dataset": ("accession", "url", "sha256", "description"),
    "improvement_effect": ("summary", "metrics"),
    "metrics": ("name", "value", "baseline", "unit"),
}
_ALWAYS_WRITTEN = {"parent"}


def load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=_Loader)


def _canonical(key: str, value: Any) -> Any:
    if key == "versions" and isinstance(value, list):
        return [_ordered(item, VERSION_KEYS) if isinstance(item, dict) else item for item in value]
    nested = _NESTED_KEYS.get(key)
    if nested and isinstance(value, list):
        return [_ordered(item, nested) if isinstance(item, dict) else item for item in value]
    if nested and isinstance(value, dict):
        return _ordered(value, nested)
    return value


def _ordered(mapping: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
    """Known keys in canonical order, then unknown ones as written; empty optional values dropped."""
    out: Dict[str, Any] = {}
    for key in list(keys) + [k for k in mapping if k not in keys]:
        if key not in mapping:
            continue
        value = mapping[key]
        if key not in _ALWAYS_WRITTEN and (value is None or value == [] or (key == "withdrawn" and value is False)):
            continue
        out[key] = _canonical(key, value)
    return out


def dump_pipeline(doc: Dict[str, Any]) -> str:
    """The canonical text of a pipeline file (SPEC-02 §2.5); R13 requires every file to equal it."""
    keys = MOVED_KEYS if "moved_to" in doc else PIPELINE_KEYS
    return yaml.safe_dump(_ordered(doc, keys), sort_keys=False, allow_unicode=True, default_flow_style=False,
                          width=4096, indent=2)


def normalize_doi(doi: str) -> str:
    text = doi.strip().lower()
    for prefix in _DOI_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def normalize_repo_url(url: str) -> str:
    match = re.match(r"^https?://([^/]+)/(.*)$", url.strip())
    if match is None:
        return url.strip().rstrip("/")
    host, path = match.groups()
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return f"https://{host.lower()}/{path.lower()}"


def github_owner_name(url: str) -> Optional[Tuple[str, str]]:
    match = re.match(r"^https://github\.com/([^/]+)/([^/]+)$", normalize_repo_url(url))
    return (match.group(1), match.group(2)) if match else None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def contributor_id(contributor: Dict[str, Any]) -> str:
    if contributor.get("github"):
        return f"ctr_gh_{contributor['github'].lower()}"
    if contributor.get("orcid"):
        return f"ctr_orcid_{contributor['orcid']}"
    return f"ctr_name_{_slug(contributor['name'])}"


def paper_key(paper: Dict[str, Any]) -> str:
    """Stable key for a paper's collected citations: its DOI, or its URL when it has none."""
    if paper.get("doi"):
        return f"doi:{normalize_doi(paper['doi'])}"
    return f"url:{paper['url']}"


def primary_repository(pipeline: Dict[str, Any]) -> Optional[str]:
    for repository in pipeline.get("repositories") or []:
        if repository.get("primary"):
            return repository["url"]
    return None


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RegistryFile:
    path: Path
    doc: Any
    error: Optional[str] = None
    text: str = ""

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def is_moved(self) -> bool:
        return isinstance(self.doc, dict) and "moved_to" in self.doc


@dataclass
class Registry:
    root: Path
    files: List[RegistryFile]

    def pipelines(self) -> List[Dict[str, Any]]:
        """Pipeline documents ordered by id; moved stubs and unreadable files are left out."""
        docs = [f.doc for f in self.files if f.error is None and isinstance(f.doc, dict) and not f.is_moved]
        return sorted(docs, key=lambda doc: str(doc.get("id")))

    def moved(self) -> Dict[str, str]:
        return {f.doc["id"]: f.doc["moved_to"] for f in self.files if f.error is None and f.is_moved}

    def versions(self) -> Iterator[Tuple[Dict[str, Any], Dict[str, Any]]]:
        for pipeline in self.pipelines():
            for version in pipeline.get("versions") or []:
                yield pipeline, version


def load_registry(root: Path) -> Registry:
    files = []
    for path in sorted((root / "pipelines").glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        try:
            files.append(RegistryFile(path, load_yaml(text), text=text))
        except yaml.YAMLError as exc:
            files.append(RegistryFile(path, None, error=str(exc).replace("\n", " "), text=text))
    return Registry(root, files)
