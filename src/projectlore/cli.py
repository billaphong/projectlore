"""Command-line entry point for ProjectLore."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import yaml

from projectlore import __version__
from projectlore.assurance_report import IntegrationEvidence, assess_assurance
from projectlore.doctor import run_doctor
from projectlore.evaluation import evaluate_once
from projectlore.integration import apply_instruction_previews, instruction_previews
from projectlore.loader import discover_model, project_root_for_model
from projectlore.mcp_server import create_server
from projectlore.onboarding import (
    INIT_VERSION,
    apply_initialization,
    initialization_previews,
)
from projectlore.policy import PolicyRequest, load_policy_registry, policy_check
from projectlore.removal import apply_removal, removal_previews
from projectlore.schema import render_json_schema, schema_matches
from projectlore.scope_cache import (
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
from projectlore.workflow import DeclaredWorkflowContext, WorkflowTarget
from projectlore.workflow_state import (
    apply_clear,
    apply_legacy_local_migration,
    apply_local_declaration,
    load_workflow_context,
    preview_clear,
    preview_legacy_local_migration,
    preview_local_declaration,
)
from projectlore.workflow_target import (
    configure_workflow_target,
    load_workflow_target,
)


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

    remove = subparsers.add_parser(
        "remove",
        help="Preview removal of generated integration and disposable state.",
    )
    remove.add_argument("--apply", action="store_true")

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
        help="Manage provider-neutral workflow context.",
    )
    scope_subparsers = scope.add_subparsers(
        dest="scope_command",
        required=True,
    )
    scope_target = scope_subparsers.add_parser(
        "target",
        help="Configure an explicit external workflow target.",
    )
    scope_target.add_argument("scope_id")
    scope_target.add_argument("container_id")
    scope_target.add_argument("--provider", required=True, choices=("fraimed",))
    scope_target.add_argument("--apply", action="store_true")
    scope_target.add_argument("--root", type=Path, default=Path.cwd())
    scope_refresh = scope_subparsers.add_parser(
        "refresh",
        help="Refresh the explicitly configured external target.",
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
    scope_local.add_argument("--expires-at", type=datetime.fromisoformat)
    scope_local.add_argument("--apply", action="store_true")
    scope_local.add_argument("--root", type=Path, default=Path.cwd())
    scope_clear = scope_subparsers.add_parser(
        "clear",
        help="Preview removal of exact-digest workflow state.",
    )
    scope_clear.add_argument("--target-digest", required=True)
    scope_clear.add_argument("--apply", action="store_true")
    scope_clear.add_argument("--root", type=Path, default=Path.cwd())
    scope_migrate = scope_subparsers.add_parser(
        "migrate",
        help="Preview migration of a legacy local declaration.",
    )
    scope_migrate.add_argument("--apply", action="store_true")
    scope_migrate.add_argument("--root", type=Path, default=Path.cwd())

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
    evaluate.add_argument("output", type=Path)
    evaluate.add_argument("--provider", choices=("fraimed",))
    evaluate.add_argument("--scope-id")
    evaluate.add_argument("--container-id")
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

    if args.command == "remove":
        previews = removal_previews(Path.cwd())
        result = {
            "preview_version": "projectlore-removal-preview/1.0.0",
            "applied": bool(args.apply),
            "files": [
                {
                    "path": str(item.path),
                    "before_digest": item.before_digest,
                    "delete": item.delete,
                    "content": item.content,
                }
                for item in previews
            ],
        }
        if args.apply:
            apply_removal(previews)
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
                model_path = discover_model(root)
                service = ModelService(model_path)
                workflow_target = WorkflowTarget(
                    target_version="projectlore-workflow-target/1.0.0",
                    project_id=service.model.id,
                    model_entrypoint=model_path.relative_to(root).as_posix(),
                    provider_id=args.provider,
                    scope_id=args.scope_id,
                    container_id=args.container_id,
                )
                try:
                    current_context = load_workflow_context(root)
                except ValueError:
                    current_context = None
                if isinstance(current_context, DeclaredWorkflowContext):
                    raise ValueError(
                        "Clear the current local workflow context before "
                        "configuring an external target."
                    )
                path = root / ".projectlore" / "workflow-target.json"
                if args.apply:
                    path = configure_workflow_target(root, workflow_target)
                    # Old evidence is rejected after target activation even if
                    # interruption occurs before this cleanup.
                    (root / ".projectlore" / "scope.json").unlink(
                        missing_ok=True
                    )
                    (root / ".projectlore" / "workflow-context.json").unlink(
                        missing_ok=True
                    )
                result = {
                    "configured": bool(args.apply),
                    "applied": bool(args.apply),
                    "path": str(path),
                    "target": workflow_target.model_dump(mode="json"),
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
                model_path = discover_model(root)
                service = ModelService(model_path)
                workflow_target = WorkflowTarget(
                    target_version="projectlore-workflow-target/1.0.0",
                    project_id=service.model.id,
                    model_entrypoint=model_path.relative_to(root).as_posix(),
                    provider_id="local",
                    scope_id=args.scope_id,
                    container_id=None,
                )
                preview = preview_local_declaration(
                    root,
                    workflow_target,
                    title=args.title,
                    status=args.status,
                    expires_at=args.expires_at,
                )
                context = (
                    apply_local_declaration(root, preview) if args.apply else None
                )
                result = {
                    "applied": args.apply,
                    "path": str(preview.path),
                    "before_digest": preview.before_digest,
                    "after_digest": preview.after_digest,
                    "target_digest": preview.target_digest,
                    "removes_external_target": preview.removes_external_target,
                    "context": (
                        context.model_dump(mode="json")
                        if context is not None
                        else json.loads(preview.content or "null")
                    ),
                    "network_required": False,
                }
            elif args.scope_command == "clear":
                preview = preview_clear(root, target_digest=args.target_digest)
                if args.apply:
                    apply_clear(root, preview)
                result = {
                    "applied": args.apply,
                    "path": str(preview.path),
                    "before_digest": preview.before_digest,
                    "after_digest": None,
                    "target_digest": preview.target_digest,
                    "removes_external_target": preview.removes_external_target,
                }
            elif args.scope_command == "migrate":
                legacy = load_scope_snapshot(root)
                assert legacy is not None
                model_path = discover_model(root)
                service = ModelService(model_path)
                workflow_target = WorkflowTarget(
                    target_version="projectlore-workflow-target/1.0.0",
                    project_id=service.model.id,
                    model_entrypoint=model_path.relative_to(root).as_posix(),
                    provider_id="local",
                    scope_id=legacy.frame_id,
                    container_id=None,
                )
                preview = preview_legacy_local_migration(root, workflow_target)
                migrated = (
                    apply_legacy_local_migration(root, preview)
                    if args.apply
                    else None
                )
                result = {
                    "applied": args.apply,
                    "path": str(preview.path),
                    "before_digest": preview.before_digest,
                    "after_digest": preview.after_digest,
                    "target_digest": preview.target_digest,
                    "context": (
                        migrated.model_dump(mode="json")
                        if migrated is not None
                        else json.loads(preview.content or "null")
                    ),
                }
            else:
                scope_target = load_scope_target(root, required=False)
                status_target = load_workflow_target(root)
                scope_error = None
                try:
                    status_scope_snapshot = load_scope_snapshot(root)
                except ValueError as error:
                    status_scope_snapshot = None
                    scope_error = str(error)
                result = {
                    "context": None,
                    "target": (
                        status_target.model_dump(mode="json")
                        if status_target is not None
                        else (
                            scope_target.model_dump(mode="json")
                            if scope_target is not None
                            else None
                        )
                    ),
                    "scope": (
                        status_scope_snapshot.model_dump(mode="json")
                        if status_scope_snapshot is not None
                        else None
                    ),
                    "workflow_observation": (
                        status_scope_snapshot.model_dump(mode="json")
                        if status_scope_snapshot is not None
                        else None
                    ),
                    "scope_error": scope_error,
                    "workflow_error": scope_error,
                }
                try:
                    result["context"] = load_workflow_context(root).model_dump(
                        mode="json"
                    )
                except ValueError as error:
                    if result["scope_error"] is None:
                        result["scope_error"] = str(error)
                        result["workflow_error"] = str(error)
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
            result = policy_check(
                service,
                request,
                registry=load_policy_registry(project_root_for_model(args.model)),
            )
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
                    args.output,
                    provider=args.provider,
                    scope_id=args.scope_id,
                    container_id=args.container_id,
                )
            )
        except (FileExistsError, FileNotFoundError, OSError, ValueError) as error:
            parser.error(str(error))
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
