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
        valid.append((label, registry_file.doc))
    return issues
