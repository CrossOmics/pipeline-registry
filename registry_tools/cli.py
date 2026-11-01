"""`python -m registry_tools validate | fmt | gen-schema | collect | build` (SPEC-02 §3.6)."""

import argparse
from pathlib import Path
from typing import Callable, Dict, List, Optional

from registry_tools.model import dump_pipeline, load_registry
from registry_tools.schema import load_schema, render_schema
from registry_tools.validate import Issue, validate_registry

SCHEMA_FILE = Path("schema") / "pipeline.schema.json"


def _schema_issues(root: Path) -> List[Issue]:
    committed = root / SCHEMA_FILE
    expected = render_schema(load_schema(root))
    if not committed.exists() or committed.read_text(encoding="utf-8") != expected:
        return [Issue(str(SCHEMA_FILE), "/", "R1",
                      "schema is stale; run `uv run python -m registry_tools gen-schema` and commit it")]
    return []


def run_validation(root: Path, base: Optional[Path] = None) -> List[Issue]:
    registry = load_registry(root)
    issues = _schema_issues(root)
    issues += validate_registry(registry, load_schema(root), base=load_registry(base) if base else None)
    return issues


def _validate(args: argparse.Namespace) -> int:
    issues = run_validation(args.root, args.base)
    for issue in issues:
        print(issue)
        if args.github_annotations:
            print(issue.annotation())
    if issues:
        print(f"{len(issues)} issue(s)")
        return 1
    print(f"{len(load_registry(args.root).files)} pipeline file(s) OK")
    return 0


def _fmt(args: argparse.Namespace) -> int:
    """Rewrite every parsed pipeline file in canonical form (R13); with --check, only list the ones that differ."""
    changed = []
    for registry_file in load_registry(args.root).files:
        if registry_file.error is not None or not isinstance(registry_file.doc, dict):
            continue
        text = dump_pipeline(registry_file.doc)
        if registry_file.text == text:
            continue
        changed.append(f"pipelines/{registry_file.path.name}")
        if not args.check:
            registry_file.path.write_text(text, encoding="utf-8")
    for label in changed:
        print(label)
    if args.check and changed:
        print(f"{len(changed)} file(s) not in canonical form; run `uv run python -m registry_tools fmt`")
        return 1
    return 0


def _gen_schema(args: argparse.Namespace) -> int:
    (args.root / SCHEMA_FILE).write_text(render_schema(load_schema(args.root)), encoding="utf-8")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="registry_tools")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="check pipeline files (R1-R13)")
    validate.add_argument("--root", type=Path, default=Path("."))
    validate.add_argument("--base", type=Path, help="checkout of the base branch, enables R8")
    validate.add_argument("--github-annotations", action="store_true")
    fmt = sub.add_parser("fmt", help="rewrite pipeline files in canonical form (R13)")
    fmt.add_argument("--root", type=Path, default=Path("."))
    fmt.add_argument("--check", action="store_true", help="only list files that are not canonical; exit 1 if any")
    gen_schema = sub.add_parser("gen-schema", help="regenerate schema/pipeline.schema.json from vocab.yaml")
    gen_schema.add_argument("--root", type=Path, default=Path("."))
    return parser


COMMANDS: Dict[str, Callable[[argparse.Namespace], int]] = {
    "validate": _validate, "fmt": _fmt, "gen-schema": _gen_schema}


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)
