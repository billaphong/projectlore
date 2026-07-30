"""Command-line entry point for ProjectLore."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import yaml

from projectlore import __version__
from projectlore.evaluation import evaluate_once
from projectlore.mcp_server import create_server
from projectlore.policy import PolicyRequest, policy_check
from projectlore.schema import render_json_schema, schema_matches
from projectlore.service import InvalidModelError, ModelService
from projectlore.validation import load_document, validate_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lore",
        description="Inspect and serve ProjectLore project knowledge models.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser(
        "status",
        help="Show basic information about a project knowledge model.",
    )
    status.add_argument("model", type=Path)
    status.add_argument("--json", action="store_true", dest="as_json")

    validate = subparsers.add_parser(
        "validate",
        help="Validate a project knowledge model.",
    )
    validate.add_argument("model", type=Path)
    validate.add_argument("--json", action="store_true", dest="as_json")

    schema = subparsers.add_parser(
        "schema",
        help="Generate or check the portable JSON Schema.",
    )
    schema.add_argument("output", type=Path)
    schema.add_argument("--check", action="store_true")

    service_status = subparsers.add_parser(
        "model-status",
        help="Return the stable ProjectLore service status contract.",
    )
    service_status.add_argument("model", type=Path)

    context = subparsers.add_parser(
        "context-for-task",
        help="Return compact rules and provenance relevant to a task.",
    )
    context.add_argument("model", type=Path)
    context.add_argument("task")

    context_short = subparsers.add_parser(
        "context",
        help="Return rules and provenance relevant to a task.",
    )
    context_short.add_argument("model", type=Path)
    context_short.add_argument("task")

    for command, help_text in (
        ("check", "Run deterministic policy checks from a JSON request."),
        ("gate", "Evaluate a policy request as a blocking gate."),
    ):
        policy_parser = subparsers.add_parser(command, help=help_text)
        policy_parser.add_argument("model", type=Path)
        policy_parser.add_argument("request", type=Path)

    doctor = subparsers.add_parser(
        "doctor",
        help="Check model validity and local ProjectLore configuration.",
    )
    doctor.add_argument("model", type=Path)

    serve = subparsers.add_parser(
        "serve",
        help="Serve the read-only ProjectLore MCP over stdio.",
    )
    serve.add_argument("model", type=Path)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Run a frozen pilot corpus once and retain its evidence.",
    )
    evaluate.add_argument("corpus", type=Path)
    evaluate.add_argument("frame_id")
    evaluate.add_argument("space_id")
    evaluate.add_argument("output", type=Path)
    return parser


def model_status(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"Project knowledge model not found: {path}")

    document = load_document(path)

    if not isinstance(document, dict):
        raise ValueError("Project knowledge model must be a YAML mapping.")

    domains = document.get("domains", [])
    concepts = document.get("concepts", [])
    relationships = document.get("relationships", [])
    return {
        "path": str(path.resolve()),
        "project": document.get("name"),
        "domains": len(domains) if isinstance(domains, list) else 0,
        "concepts": len(concepts) if isinstance(concepts, list) else 0,
        "relationships": (
            len(relationships) if isinstance(relationships, list) else 0
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        try:
            service_result = ModelService(args.model).model_status()
        except (
            FileNotFoundError,
            OSError,
            ValueError,
            yaml.YAMLError,
            InvalidModelError,
        ) as error:
            parser.error(str(error))

        if args.as_json:
            print(json.dumps(service_result, indent=2))
        else:
            counts = service_result["counts"]
            print(f"Project: {service_result['model_id']}")
            print(f"Domains: {counts['domains']}")
            print(f"Concepts: {counts['concepts']}")
            print(f"Relationships: {counts['relationships']}")
        return 0

    if args.command == "validate":
        try:
            _, report = validate_path(args.model)
        except (FileNotFoundError, OSError) as error:
            parser.error(str(error))
        if args.as_json:
            print(json.dumps(report.to_dict(), indent=2))
        elif report.valid:
            print(f"Valid: {args.model}")
        else:
            for diagnostic in report.diagnostics:
                print(f"{diagnostic.code} {diagnostic.path}: {diagnostic.message}")
        return 0 if report.valid else 1

    if args.command == "schema":
        if args.check:
            if schema_matches(args.output):
                print(f"Schema is current: {args.output}")
                return 0
            print(f"Schema drift detected: {args.output}")
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_json_schema(), encoding="utf-8")
        print(f"Wrote schema: {args.output}")
        return 0

    if args.command in {
        "model-status",
        "context-for-task",
        "context",
        "check",
        "gate",
        "doctor",
        "serve",
    }:
        try:
            service = ModelService(args.model)
        except (FileNotFoundError, OSError, InvalidModelError) as error:
            parser.error(str(error))
        if args.command == "model-status":
            print(json.dumps(service.model_status(), indent=2))
            return 0
        if args.command in {"context-for-task", "context"}:
            print(json.dumps(service.context_for_task(args.task), indent=2))
            return 0
        if args.command == "doctor":
            result = service.model_status()
            checks = {
                "model_valid": True,
                "schema_version_supported": service.model.schema_version
                in {"0.1.0", "1.0.0"},
                "canonical_model_read_only": True,
            }
            result["checks"] = checks
            result["healthy"] = all(checks.values())
            print(json.dumps(result, indent=2))
            return 0 if result["healthy"] else 2
        if args.command == "serve":
            create_server(args.model).run(transport="stdio")
            return 0
        try:
            request = PolicyRequest.model_validate_json(
                args.request.read_text(encoding="utf-8")
            )
            result = policy_check(service, request)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        print(json.dumps(result, indent=2))
        if result["decision"] == "fail":
            return 1
        if result["decision"] == "indeterminate":
            return 2
        return 0

    if args.command == "evaluate":
        try:
            result = asyncio.run(
                evaluate_once(
                    args.corpus,
                    args.frame_id,
                    args.space_id,
                    args.output,
                )
            )
        except (FileExistsError, FileNotFoundError, OSError, ValueError) as error:
            parser.error(str(error))
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
