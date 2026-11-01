import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from jsonschema import Draft202012Validator

from registry_tools.model import Registry, dump_pipeline, normalize_doi, normalize_repo_url
"""Registry checks R1–R13 (SPEC-02 §2.3)."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

from registry_tools.model import Registry


@dataclass(frozen=True)
class Issue:
    file: str
    pointer: str
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.pointer}: {self.rule}: {self.message}"

    def annotation(self) -> str:
        return f"::error file={self.file}::{self.pointer}: {self.rule}: {self.message}"


Valid = List[Tuple[str, Dict[str, Any]]]


def _label(path) -> str:
    return f"pipelines/{path.name}"


def _pointer(parts) -> str:
    return "/" + "/".join(str(part) for part in parts) if parts else "/"


def validate_registry(registry: Registry, schema: Dict[str, Any], base: Optional[Registry] = None) -> List[Issue]:
    issues: List[Issue] = []
    validator = Draft202012Validator(schema)
    valid: Valid = []
    for registry_file in registry.files:
        label = _label(registry_file.path)
        if registry_file.error is not None:
            issues.append(Issue(label, "/", "R1", f"not valid YAML: {registry_file.error}"))
            continue
        errors = sorted(validator.iter_errors(registry_file.doc), key=lambda e: [str(p) for p in e.absolute_path])
        issues += [Issue(label, _pointer(list(e.absolute_path)), "R1", e.message) for e in errors]
        if errors:
            continue
        if registry_file.doc["id"] != registry_file.stem:
            issues.append(Issue(label, "/id", "R1",
                                f"id {registry_file.doc['id']!r} must equal the file name {registry_file.stem!r}"))
            continue
        if registry_file.text != dump_pipeline(registry_file.doc):
            issues.append(Issue(label, "/", "R13",
                                "not in canonical form; run `uv run python -m registry_tools fmt`"))
        valid.append((label, registry_file.doc))
    issues += _integrity(valid)
    if base is not None:
        issues += _append_only(registry, base)
    return issues

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
VersionIndex = Dict[str, Tuple[str, str, Dict[str, Any]]]  # version id -> (file, pointer, version)


def _integrity(valid: Valid) -> List[Issue]:
    issues: List[Issue] = []
    pipelines = {doc["id"] for _, doc in valid if "moved_to" not in doc}
    owners: Dict[str, str] = {}
    commits: Dict[Tuple[str, str], str] = {}
    for label, doc in valid:
        if "moved_to" in doc:
            if doc["moved_to"] not in pipelines:
                issues.append(Issue(label, "/moved_to", "R7",
                                    f"{doc['moved_to']!r} is not a pipeline in the registry, or is itself moved"))
            continue
        issues += _repositories(label, doc)
        issues += _papers(label, doc)
        local: VersionIndex = {}
        for index, version in enumerate(doc["versions"]):
            pointer = f"/versions/{index}"
            if version["id"] in owners:
                issues.append(Issue(label, f"{pointer}/id", "R2",
                                    f"version id {version['id']!r} is also used in {owners[version['id']]}"))
            else:
                owners[version["id"]] = label
            local.setdefault(version["id"], (label, pointer, version))
            key = (normalize_repo_url(version["repo"]), version["commit"])
            if key in commits:
                issues.append(Issue(label, f"{pointer}/commit", "R5",
                                    f"{key[0]}@{key[1]} is already registered as {commits[key]}"))
            else:
                commits[key] = version["id"]
            issues += _package(label, pointer, version.get("gardener_package"))
        issues += _lineage(label, local)
    return issues


def _lineage(label: str, versions: VersionIndex) -> List[Issue]:
    """R3, R11, R12 and R4 over one file's versions: parents are in the same file, there is exactly one root,
    the root is an original, and an original builds only on an original."""
    issues: List[Issue] = []
    roots: List[Tuple[str, Dict[str, Any]]] = []
    for _, pointer, version in versions.values():
        parent = version.get("parent")
        if parent is None:
            roots.append((pointer, version))
        elif parent not in versions:
            issues.append(Issue(label, f"{pointer}/parent", "R3",
                                f"parent {parent!r} is not a version in the same file"))
        elif version["kind"] == "original" and versions[parent][2]["kind"] != "original":
            issues.append(Issue(label, f"{pointer}/parent", "R12",
                                f"an original builds only on an original; {parent!r} is an optimization"))
    if not roots:
        issues.append(Issue(label, "/versions", "R11", "no root version; exactly one version must have no parent"))
    else:
        pointer, root = roots[0]
        if root["kind"] != "original":
            issues.append(Issue(label, f"{pointer}/kind", "R11", "the root version must be an original"))
        for pointer, version in roots[1:]:
            issues.append(Issue(label, f"{pointer}/parent", "R11",
                                f"only one root is allowed; give {version['id']!r} a parent"))
    issues += _cycles(versions)
    return issues


def _repositories(label: str, doc: Dict[str, Any]) -> List[Issue]:
    repositories = doc.get("repositories") or []
    primaries = sum(1 for repository in repositories if repository.get("primary"))
    if repositories and primaries != 1:
        return [Issue(label, "/repositories", "R6", f"exactly one repository must be primary, found {primaries}")]
    return []


def _papers(label: str, doc: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    seen: Set[str] = set()
    for index, paper in enumerate(doc.get("papers") or []):
        doi = paper.get("doi")
        if doi is None:
            continue
        normalized = normalize_doi(doi)
        if doi != normalized:
            issues.append(Issue(label, f"/papers/{index}/doi", "R10", f"write the DOI as {normalized!r}"))
        if normalized in seen:
            issues.append(Issue(label, f"/papers/{index}/doi", "R10", f"duplicate DOI {normalized!r}"))
        seen.add(normalized)
    return issues


def _package(label: str, pointer: str, package: Optional[Dict[str, Any]]) -> List[Issue]:
    if not package:
        return []
    issues: List[Issue] = []
    if "@" in package["ref"]:
        issues.append(Issue(label, f"{pointer}/gardener_package/ref", "R9",
                            "put the digest in `digest`; `ref` is name[:tag] only"))
    if not _DIGEST.fullmatch(package["digest"]):
        issues.append(Issue(label, f"{pointer}/gardener_package/digest", "R9",
                            "digest must be sha256:<64 lowercase hex>, the OCI manifest digest"))
    return issues


def _cycles(versions: VersionIndex) -> List[Issue]:
    issues: List[Issue] = []
    reported: Set[frozenset] = set()
    for start in versions:
        path: List[str] = []
        current: Optional[str] = start
        while current is not None and current in versions and current not in path:
            path.append(current)
            current = versions[current][2].get("parent")
        if current is None or current not in path:
            continue
        cycle = path[path.index(current):]
        if frozenset(cycle) in reported:
            continue
        reported.add(frozenset(cycle))
        first = min(cycle)
        label, pointer, _ = versions[first]
        ordered = cycle[cycle.index(first):] + cycle[:cycle.index(first)]
        issues.append(Issue(label, f"{pointer}/parent", "R4", "lineage cycle: " + " -> ".join(ordered + [first])))
    return issues

def _dict_docs(registry: Registry) -> List[Tuple[str, Dict[str, Any]]]:
    return [(_label(f.path), f.doc) for f in registry.files if f.error is None and isinstance(f.doc, dict)]


def _append_only(registry: Registry, base: Registry) -> List[Issue]:
    """R8: merged ids never disappear; a version's repo, commit, parent and kind never change; no un-withdrawing.
    Reads every parsed head file, even one failing R1, so a typo does not also report its versions as removed."""
    issues: List[Issue] = []
    head_ids = {doc.get("id") for _, doc in _dict_docs(registry)}
    head_versions: VersionIndex = {}
    for label, doc in _dict_docs(registry):
        for index, version in enumerate(doc.get("versions") or []):
            if isinstance(version, dict) and "id" in version:
                head_versions[version["id"]] = (label, f"/versions/{index}", version)
    for label, doc in _dict_docs(base):
        if doc.get("id") not in head_ids:
            issues.append(Issue(label, "/id", "R8",
                                f"pipeline {doc.get('id')!r} was removed; ids are permanent (rename with moved_to)"))
        for old in doc.get("versions") or []:
            found = head_versions.get(old.get("id"))
            if found is None:
                issues.append(Issue(label, "/versions", "R8",
                                    f"version {old.get('id')!r} was removed; mark it withdrawn instead"))
                continue
            head_label, pointer, new = found
            for name in ("repo", "commit", "parent", "kind"):
                if new.get(name) != old.get(name):
                    issues.append(Issue(head_label, f"{pointer}/{name}", "R8",
                                        f"{name} of merged version {old['id']!r} cannot change"))
            if old.get("withdrawn") and not new.get("withdrawn"):
                issues.append(Issue(head_label, f"{pointer}/withdrawn", "R8",
                                    f"version {old['id']!r} cannot be un-withdrawn"))
    return issues
