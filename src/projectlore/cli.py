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
from projectlore.acquisition.compaction import (
    apply_compaction,
    compaction_preview,
)
from projectlore.acquisition.models import (
    ProposalClassification,
    ReviewDisposition,
)
from projectlore.acquisition.onboarding import (
    onboarding_preview,
    start_onboarding,
)
from projectlore.acquisition.passive import (
    capture_scan,
    knowledge_status,
    next_packet,
)
from projectlore.acquisition.proposal import submit_proposal
from projectlore.acquisition.recovery import (
    apply_repair,
    recovery_status,
    repair_preview,
)
from projectlore.acquisition.review import apply_review, review_proposal
from projectlore.acquisition.schema import render_acquisition_schema
from projectlore.assurance_report import (
    assess_assurance,
    load_integration_evidence,
)
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
from projectlore.removal import (
    acquisition_removal_preview,
    apply_acquisition_removal,
    apply_removal,
    removal_previews,
)
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

    acquisition_schema = subparsers.add_parser(
        "acquisition-schema",
        help="Generate or check the portable acquisition JSON Schema.",
    )
    acquisition_schema.add_argument("output", type=Path)
    acquisition_schema.add_argument("--check", action="store_true")

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

    onboard = subparsers.add_parser(
        "onboard",
        help="Create immediate repository evidence for a knowledge baseline.",
    )
    onboard_subparsers = onboard.add_subparsers(dest="onboard_command", required=True)
    onboard_start = onboard_subparsers.add_parser(
        "start", help="Preview or create the initial evidence packet."
    )
    onboard_start.add_argument("--apply", action="store_true")
    onboard_start.add_argument("--root", type=Path, default=Path.cwd())
    onboard_status = onboard_subparsers.add_parser(
        "status", help="Inspect onboarding and acquisition state."
    )
    onboard_status.add_argument("--root", type=Path, default=Path.cwd())

    knowledge = subparsers.add_parser(
        "knowledge", help="Propose, review, and apply project knowledge."
    )
    knowledge_subparsers = knowledge.add_subparsers(
        dest="knowledge_command", required=True
    )
    knowledge_propose = knowledge_subparsers.add_parser(
        "propose", help="Submit a complete candidate without applying it."
    )
    knowledge_propose.add_argument("candidate", type=Path)
    knowledge_propose.add_argument("--packet-id", required=True)
    knowledge_propose.add_argument(
        "--classification",
        choices=tuple(item.value for item in ProposalClassification),
        default=ProposalClassification.ASSERTED.value,
    )
    knowledge_propose.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_review = knowledge_subparsers.add_parser(
        "review", help="Record an explicit digest-bound proposal decision."
    )
    knowledge_review.add_argument("proposal_id")
    knowledge_review.add_argument(
        "--disposition",
        required=True,
        choices=tuple(item.value for item in ReviewDisposition),
    )
    knowledge_review.add_argument("--actor", required=True)
    knowledge_review.add_argument("--revision-note")
    knowledge_review.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_apply = knowledge_subparsers.add_parser(
        "apply", help="Apply an accepted review to canonical YAML."
    )
    knowledge_apply.add_argument("review_id")
    knowledge_apply.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_status_parser = knowledge_subparsers.add_parser(
        "status", help="Inspect passive acquisition state without writing."
    )
    knowledge_status_parser.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_scan = knowledge_subparsers.add_parser(
        "scan", help="Capture one bounded metadata-only repository signal."
    )
    knowledge_scan.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_packet = knowledge_subparsers.add_parser(
        "packet", help="Lease pending passive evidence for agent inspection."
    )
    packet_subparsers = knowledge_packet.add_subparsers(
        dest="packet_command", required=True
    )
    packet_next = packet_subparsers.add_parser(
        "next", help="Return the outstanding packet or lease pending signals."
    )
    packet_next.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_recover = knowledge_subparsers.add_parser(
        "recover", help="Inspect active workflow recovery state without writing."
    )
    knowledge_recover.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_repair = knowledge_subparsers.add_parser(
        "repair", help="Preview or explicitly apply workflow-root repair."
    )
    knowledge_repair.add_argument("--apply", action="store_true")
    knowledge_repair.add_argument("--preview-digest")
    knowledge_repair.add_argument("--root", type=Path, default=Path.cwd())
    knowledge_compact = knowledge_subparsers.add_parser(
        "compact", help="Preview or apply deletion of unreachable workflow files."
    )
    knowledge_compact.add_argument("--apply", action="store_true")
    knowledge_compact.add_argument("--preview-digest")
    knowledge_compact.add_argument("--root", type=Path, default=Path.cwd())

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
    remove.add_argument("--preview-digest")

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

    if args.command == "acquisition-schema":
        rendered = render_acquisition_schema()
        if args.check:
            if (
                args.output.is_file()
                and args.output.read_text(encoding="utf-8") == rendered
            ):
                print(f"Acquisition schema is current: {args.output}")
                return 0
            print(f"Acquisition schema drift detected: {args.output}")
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote acquisition schema: {args.output}")
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

    if args.command == "onboard":
        try:
            root = args.root.resolve(strict=True)
            if args.onboard_command == "status":
                onboard_result = knowledge_status(root)
            else:
                onboard_result = onboarding_preview(root)
                if args.apply:
                    signal, packet = start_onboarding(root)
                    onboard_result.update(
                        {
                            "applied": True,
                            "signal": signal.model_dump(mode="json"),
                            "packet": packet.model_dump(mode="json"),
                        }
                    )
        except (OSError, RuntimeError, ValueError) as error:
            parser.error(str(error))
        print(json.dumps(onboard_result, indent=2))
        return 0

    if args.command == "knowledge":
        try:
            root = args.root.resolve(strict=True)
            if args.knowledge_command == "propose":
                proposal = submit_proposal(
                    root,
                    args.candidate,
                    args.packet_id,
                    classification=ProposalClassification(args.classification),
                )
                result = proposal.model_dump(mode="json")
            elif args.knowledge_command == "review":
                review = review_proposal(
                    root,
                    args.proposal_id,
                    ReviewDisposition(args.disposition),
                    args.actor,
                    revision_note=args.revision_note,
                )
                result = review.model_dump(mode="json", exclude_none=True)
            elif args.knowledge_command == "apply":
                path = apply_review(root, args.review_id)
                result = {
                    "contract_version": "projectlore-knowledge-apply/0.6.1",
                    "applied": True,
                    "review_id": args.review_id,
                    "path": str(path),
                }
            elif args.knowledge_command == "scan":
                signal = capture_scan(root)
                result = signal.model_dump(mode="json", exclude_none=True)
            elif args.knowledge_command == "packet":
                leased_packet = next_packet(root)
                result = {
                    "contract_version": "projectlore-packet-next/0.6.1",
                    "packet": (
                        None
                        if leased_packet is None
                        else leased_packet.model_dump(mode="json")
                    ),
                    "missing": leased_packet is None,
                }
            elif args.knowledge_command == "recover":
                result = recovery_status(root)
            elif args.knowledge_command == "repair":
                if args.apply:
                    if args.preview_digest is None:
                        raise ValueError("--preview-digest is required with --apply")
                    result = apply_repair(root, args.preview_digest)
                else:
                    result = repair_preview(root)
            elif args.knowledge_command == "compact":
                if args.apply:
                    if args.preview_digest is None:
                        raise ValueError("--preview-digest is required with --apply")
                    result = apply_compaction(root, args.preview_digest)
                else:
                    result = compaction_preview(root)
            else:
                result = knowledge_status(root)
        except (OSError, RuntimeError, ValueError) as error:
            parser.error(str(error))
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
        if args.preview_digest is not None:
            if not args.apply:
                raise ValueError("--preview-digest requires --apply")
            result = apply_acquisition_removal(Path.cwd(), args.preview_digest)
            print(json.dumps(result, indent=2))
            return 0
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
        knowledge = Path.cwd() / ".projectlore" / "knowledge"
        acquisition_present = knowledge.is_dir() and any(
            path.is_file() and "locks" not in path.relative_to(knowledge).parts
            for path in knowledge.rglob("*")
        )
        if acquisition_present:
            transaction = acquisition_removal_preview(Path.cwd())
            result["preview_digest"] = transaction["preview_digest"]
        if args.apply:
            if acquisition_present:
                raise ValueError(
                    "Acquisition removal requires --preview-digest from the preview."
                )
            apply_removal(previews)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "integration":
        try:
            service = ModelService(args.model)
            if args.evidence is not None:
                evidence, evidence_diagnostics = load_integration_evidence(
                    args.evidence
                )
            else:
                evidence, evidence_diagnostics = None, ()
        except (FileNotFoundError, OSError, ValueError, InvalidModelError) as error:
            parser.error(str(error))
        assurance_report = assess_assurance(
            service.project.digest,
            evidence,
            project=service.project,
            ingestion_diagnostics=evidence_diagnostics,
        )
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
                    (root / ".projectlore" / "scope.json").unlink(missing_ok=True)
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
                path, snapshot = asyncio.run(refresh_scope_from_environment(root))
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
                context = apply_local_declaration(root, preview) if args.apply else None
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
                    apply_legacy_local_migration(root, preview) if args.apply else None
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
