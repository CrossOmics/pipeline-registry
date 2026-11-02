"""JSON Schema for pipeline files, generated from the vocabularies (SPEC-02 §2.2, §2.4)."""

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

PIPELINE_ID = r"^cp_[a-z0-9]+(_[a-z0-9]+)*$"
VERSION_ID = r"^cv_[a-z0-9]+(_[a-z0-9]+)*$"
ACCESSION = r"^(SRR|ERR|DRR|SRX|ERX|GSE|GSM|PRJNA|PRJEB|E-MTAB-)[0-9A-Z-]+$"
ROLES = ["creator", "author", "maintainer", "developer"]
STATUSES = ["active", "stable", "deprecated", "archived"]
PIPELINE_KINDS = ["tool", "workflow"]
VERSION_KINDS = ["original", "optimization"]
_URL = {"type": "string", "pattern": "^https?://"}
BIOCODE_REPOSITORY = (r"^https://github\.com/[Bb][Ii][Oo][Cc][Oo][Dd][Ee]-"
                     r"[Cc][Oo][Mm][Mm][Oo][Nn][Ss]/[A-Za-z0-9_-][A-Za-z0-9_.-]*/?$")


def load_vocab(path: Path) -> Dict[str, List[str]]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_schema(vocab: Dict[str, List[str]]) -> Dict[str, Any]:
    def enum_list(name: str) -> Dict[str, Any]:
        return {"type": "array", "items": {"enum": vocab[name]}, "uniqueItems": True}

    text_list = {"type": "array", "items": {"type": "string", "minLength": 1}}
    pipeline_id = {"type": "string", "pattern": PIPELINE_ID, "minLength": 4, "maxLength": 64}
    contributor = {
        "type": "object", "additionalProperties": False, "required": ["name", "role"],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "github": {"type": "string", "pattern": r"^[A-Za-z0-9-]{1,39}$"},
            "orcid": {"type": "string", "pattern": r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"},
            "role": {"enum": ROLES},
        },
    }
    paper = {
        "type": "object", "additionalProperties": False,
        "properties": {"doi": {"type": "string", "minLength": 3}, "url": _URL, "title": {"type": "string"}},
        "anyOf": [{"required": ["doi"]}, {"required": ["url"]}],
    }
    repository = {
        "type": "object", "additionalProperties": False, "required": ["url"],
        "properties": {"url": _URL, "primary": {"type": "boolean"}},
    }
    biocode_maintenance = {
        "type": "object", "additionalProperties": False, "required": ["status"],
        "properties": {
            "status": {"enum": ["planned", "available"]},
            "repository": {"type": "string", "pattern": BIOCODE_REPOSITORY},
        },
        "if": {"properties": {"status": {"const": "available"}}},
        "then": {"required": ["repository"]},
    }
    package = {
        "type": "object", "additionalProperties": False, "required": ["ref", "digest"],
        "properties": {"ref": {"type": "string", "minLength": 1}, "digest": {"type": "string"}},
    }
    test_dataset = {
        "type": "object", "additionalProperties": False, "required": ["description"],
        "properties": {
            "accession": {"type": "string", "pattern": ACCESSION},
            "url": _URL,
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "description": {"type": "string", "minLength": 1, "maxLength": 2000},
        },
        "anyOf": [{"required": ["accession"]}, {"required": ["url"]}],
    }
    effect_metric = {
        "type": "object", "additionalProperties": False, "required": ["name", "value"],
        "properties": {
            "name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
            "value": {"type": "number"},
            "baseline": {"type": "number"},
            "unit": {"type": "string", "minLength": 1},
        },
    }
    improvement_effect = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
            "metrics": {"type": "array", "minItems": 1, "items": effect_metric},
        },
        "anyOf": [{"required": ["summary"]}, {"required": ["metrics"]}],
    }
    version = {
        "type": "object", "additionalProperties": False,
        "required": ["id", "kind", "label", "repo", "commit", "parent"],
        "properties": {
            "id": {"type": "string", "pattern": VERSION_ID, "minLength": 4, "maxLength": 80},
            "kind": {"enum": VERSION_KINDS},
            "label": {"type": "string", "minLength": 1},
            "repo": _URL,
            "commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "parent": {"type": ["string", "null"], "pattern": VERSION_ID},
            "released_at": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            "contributors": {"type": "array", "items": contributor},
            "improvement": {"type": ["string", "null"], "maxLength": 4000},
            "test_dataset": test_dataset,
            "improvement_effect": improvement_effect,
            "gardener_package": {"anyOf": [{"type": "null"}, package]},
            "withdrawn": {"type": "boolean"},
        },
        # SPEC-02 §2.2: an optimization says what it improves; only an optimization carries test data.
        "if": {"required": ["kind"], "properties": {"kind": {"const": "optimization"}}},
        "then": {"required": ["improvement"], "properties": {"improvement": {"type": "string", "minLength": 1}}},
        "else": {"not": {"anyOf": [{"required": ["test_dataset"]}, {"required": ["improvement_effect"]}]}},
    }
    pipeline = {
        "type": "object", "additionalProperties": False,
        "required": ["schema_version", "id", "name", "kind", "description", "domain", "status", "versions"],
        "properties": {
            "schema_version": {"const": 1},
            "id": pipeline_id,
            "name": {"type": "string", "minLength": 1},
            "kind": {"enum": PIPELINE_KINDS},
            "description": {"type": "string", "minLength": 1, "maxLength": 2000},
            "domain": {"enum": vocab["domain"]},
            "modalities": enum_list("modalities"),
            "inputs": enum_list("inputs"),
            "outputs": enum_list("outputs"),
            "algorithms": text_list,
            "keywords": text_list,
            "status": {"enum": STATUSES},
            "repositories": {"type": "array", "items": repository},
            "biocode_maintenance": biocode_maintenance,
            "papers": {"type": "array", "items": paper},
            "contributors": {"type": "array", "items": contributor},
            "versions": {"type": "array", "minItems": 1, "items": version},
        },
    }
    moved = {
        "type": "object", "additionalProperties": False, "required": ["schema_version", "id", "moved_to"],
        "properties": {"schema_version": {"const": 1}, "id": pipeline_id, "moved_to": pipeline_id},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://crossomics.github.io/pipeline-registry/pipeline.schema.json",
        "title": "Community Pipeline",
        "$defs": {"pipeline": pipeline, "moved": moved},
        "if": {"type": "object", "required": ["moved_to"]},
        "then": {"$ref": "#/$defs/moved"},
        "else": {"$ref": "#/$defs/pipeline"},
    }


def render_schema(schema: Dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_schema(root: Path) -> Dict[str, Any]:
    return build_schema(load_vocab(root / "schema" / "vocab.yaml"))
