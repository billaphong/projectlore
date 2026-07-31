"""Command-line entry point for ProjectLore."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import yaml

from projectlore import __version__
from projectlore.assurance_report import IntegrationEvidence, assess_assurance
from projectlore.doctor import run_doctor
from projectlore.evaluation import evaluate_once
from projectlore.integration import apply_instruction_previews, instruction_previews
from projectlore.mcp_server import create_server
from projectlore.onboarding import (
    INIT_VERSION,
    apply_initialization,
    initialization_previews,
)
from projectlore.policy import PolicyRequest, policy_check
from projectlore.schema import render_json_schema, schema_matches
from projectlore.scope_cache import (
    configure_local_scope,
    configure_scope_target,
    load_scope_target,
    refresh_scope_from_environment,
)
from projectlore.service import InvalidModelError, ModelService
from projectlore.source_gate import (
    evaluate_source_gate,
    source_gate_exit_code,
    write_source_gate_evidence,
)
from projectlore.source_policy import (
    configured_source_paths,
    load_scope_snapshot,
)
from projectlore.trust import issue_receipt, write_receipt
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

    initialize = subparsers.add_parser(
        "init",
        help="Preview initialization of a ProjectLore-enabled repository.",
    )
    initialize.add_argument("--apply", action="store_true")
    initialize.add_argument(
        "--name",
        default=Path.cwd().name,
        help="Project display name; defaults to the current directory name.",
    )
    initialize.add_argument(
        "--model",
        type=Path,
        default=Path("projectlore.yaml"),
        help="Canonical model path: projectlore.yaml or .projectlore/model.yaml.",
    )

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

    integrate = subparsers.add_parser(
        "integrate",
        help="Preview managed AGENTS.md and CLAUDE.md instruction blocks.",
    )
    integrate.add_argument("--apply", action="store_true")

    integration = subparsers.add_parser(
        "integration",
        help="Inspect achieved integration assurance.",
    )
    integration_subparsers = integration.add_subparsers(
        dest="integration_command", required=True
    )
    integration_check = integration_subparsers.add_parser(
        "check",
        help="Report achieved assurance and explicit missing requirements.",
    )
    integration_check.add_argument("model", type=Path)
    integration_check.add_argument("--evidence", type=Path)

    trust = subparsers.add_parser(
        "trust",
        help="Record explicit review of current client integration files.",
    )
    trust.add_argument("client", choices=("claude_code", "codex_cli"))
    trust.add_argument("--client-version", required=True)
    trust.add_argument("--confirm-reviewed", action="store_true")

    scope = subparsers.add_parser(
        "scope",
        help="Configure and refresh local Fraimed workflow scope.",
    )
    scope_subparsers = scope.add_subparsers(
        dest="scope_command",
        required=True,
    )
    scope_target = scope_subparsers.add_parser(
        "target",
        help="Set the non-secret local Fraimed Frame and Space target.",
    )
    scope_target.add_argument("frame_id")
    scope_target.add_argument("space_id")
    scope_target.add_argument("--root", type=Path, default=Path.cwd())
    scope_refresh = scope_subparsers.add_parser(
        "refresh",
        help="Refresh the configured target through Fraimed MCP.",
    )
    scope_refresh.add_argument("--root", type=Path, default=Path.cwd())
    scope_status = scope_subparsers.add_parser(
        "status",
        help="Inspect the configured target and local scope snapshot.",
    )
    scope_status.add_argument("--root", type=Path, default=Path.cwd())
    scope_local = scope_subparsers.add_parser(
        "local",
        help="Set standalone local workflow context without a hosted provider.",
    )
    scope_local.add_argument("scope_id")
    scope_local.add_argument("--title", required=True)
    scope_local.add_argument("--status", default="in_progress")
    scope_local.add_argument("--root", type=Path, default=Path.cwd())

    source_gate = subparsers.add_parser(
        "source-gate",
        help="Evaluate configured checked-out source through policy.",
    )
    source_gate.add_argument("model", type=Path)
    source_selection = source_gate.add_mutually_exclusive_group(required=True)
    source_selection.add_argument(
        "--changed-file",
        action="append",
        dest="changed_files",
    )
    source_selection.add_argument("--all-configured", action="store_true")
    source_gate.add_argument(
        "--assurance-scope",
        choices=("local_advisory", "ci_job_result"),
        default="local_advisory",
    )
    source_gate.add_argument(
        "--output",
        type=Path,
        default=Path(".projectlore/evidence/source-gate.json"),
    )
    source_gate.add_argument("--root", type=Path, default=Path.cwd())

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
        "relationships": (len(relationships) if isinstance(relationships, list) else 0),
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

    if args.command == "init":
        try:
            init_previews = initialization_previews(
                Path.cwd(),
                project_name=args.name,
                model_path=args.model,
            )
            if args.apply:
                apply_initialization(init_previews)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        result = {
            "preview_version": INIT_VERSION,
            "applied": bool(args.apply),
            "conflicts": [
                {"path": str(item.path), "reason": item.conflict}
                for item in init_previews
                if item.conflict is not None
            ],
            "files": [
                {
                    "path": str(item.path),
                    "before_digest": item.before_digest,
                    "after_digest": item.after_digest,
                    "changed": item.changed,
                    "content": item.content,
                }
                for item in init_previews
            ],
        }
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "integrate":
        integration_previews = instruction_previews(Path.cwd())
        result = {
            "preview_version": "projectlore-integration-preview/0.1.0",
            "applied": bool(args.apply),
            "files": [
                {
                    "path": str(item.path),
                    "before_digest": item.before_digest,
                    "after_digest": item.after_digest,
                    "changed": item.changed,
                    "content": item.content,
                }
                for item in integration_previews
            ],
        }
        if args.apply:
            apply_instruction_previews(integration_previews)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "integration":
        try:
            service = ModelService(args.model)
            evidence = (
                IntegrationEvidence.model_validate_json(
                    args.evidence.read_text(encoding="utf-8")
                )
                if args.evidence is not None
                else None
            )
        except (FileNotFoundError, OSError, ValueError, InvalidModelError) as error:
            parser.error(str(error))
        assurance_report = assess_assurance(service.project.digest, evidence)
        print(json.dumps(assurance_report.model_dump(mode="json"), indent=2))
        return 0 if not assurance_report.missing_requirements else 2

    if args.command == "trust":
        if not args.confirm_reviewed:
            parser.error(
                "--confirm-reviewed is required after reviewing trust in the client."
            )
        receipt = issue_receipt(Path.cwd(), args.client, args.client_version)
        path = write_receipt(Path.cwd(), receipt)
        print(
            json.dumps(
                {
                    "receipt_version": receipt.receipt_version,
                    "client": receipt.client,
                    "path": str(path),
                    "config_digests": receipt.config_digests,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "scope":
        root = args.root.resolve()
        try:
            if args.scope_command == "target":
                path, target = configure_scope_target(
                    root,
                    frame_id=args.frame_id,
                    space_id=args.space_id,
                )
                result = {
                    "configured": True,
                    "path": str(path),
                    "target": target.model_dump(mode="json"),
                    "credential_stored": False,
                }
            elif args.scope_command == "refresh":
                path, snapshot = asyncio.run(
                    refresh_scope_from_environment(root)
                )
                result = {
                    "refreshed": True,
                    "path": str(path),
                    "scope": snapshot.model_dump(mode="json"),
                }
            elif args.scope_command == "local":
                path, local_scope_snapshot = configure_local_scope(
                    root,
                    scope_id=args.scope_id,
                    title=args.title,
                    status=args.status,
                )
                result = {
                    "configured": True,
                    "path": str(path),
                    "scope": local_scope_snapshot.model_dump(mode="json"),
                    "network_required": False,
                }
            else:
                scope_target = load_scope_target(root, required=False)
                scope_error = None
                try:
                    status_scope_snapshot = load_scope_snapshot(root)
                except ValueError as error:
                    status_scope_snapshot = None
                    scope_error = str(error)
                result = {
                    "target": (
                        scope_target.model_dump(mode="json")
                        if scope_target is not None
                        else None
                    ),
                    "scope": (
                        status_scope_snapshot.model_dump(mode="json")
                        if status_scope_snapshot is not None
                        else None
                    ),
                    "scope_error": scope_error,
                }
        except (OSError, RuntimeError, TimeoutError, ValueError) as error:
            parser.error(str(error))
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "source-gate":
        root = args.root.resolve()
        try:
            service = ModelService(args.model)
            paths = (
                configured_source_paths(root)
                if args.all_configured
                else tuple(args.changed_files or ())
            )
            gate_evidence = evaluate_source_gate(
                root,
                service,
                paths,
                assurance_scope=args.assurance_scope,
            )
            write_source_gate_evidence(args.output, gate_evidence)
        except (
            FileNotFoundError,
            OSError,
            ValueError,
            InvalidModelError,
        ) as error:
            parser.error(str(error))
        print(gate_evidence.model_dump_json(indent=2))
        return source_gate_exit_code(gate_evidence)

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
            result = run_doctor(Path.cwd(), args.model)
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
