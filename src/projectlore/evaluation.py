"""One-shot evaluator for a pre-registered ProjectLore pilot corpus."""

from __future__ import annotations

import json
import os
import shutil
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from projectlore.fraimed import FraimedScopeAuthority, ScopeAuthority
from projectlore.policy import PolicyRequest, policy_check
from projectlore.service import ModelService


async def evaluate_once(
    corpus_path: Path,
    frame_id: str,
    space_id: str,
    output_path: Path,
    scope_authority: ScopeAuthority | None = None,
) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(
            f"Refusing to replace retained evaluation evidence: {output_path}"
        )
    corpus = yaml.safe_load(corpus_path.read_text(encoding="utf-8"))
    project_root = corpus_path.resolve().parents[2]
    model_path = project_root / corpus["model"]
    authority = scope_authority or FraimedScopeAuthority(
        os.environ.get(
            "PROJECTLORE_FRAIMED_MCP_URL",
            "https://www.fraimed.ai/api/mcp",
        ),
        os.environ.get("FRAIMED_API_TOKEN", ""),
    )
    scope = await authority.current_scope(frame_id, space_id)

    service = ModelService(model_path)
    retrieval_success = 0
    provenance_correct = 0
    latencies: list[float] = []
    context_sizes: list[int] = []
    question_results: list[dict[str, Any]] = []
    for question in corpus["questions"]:
        started = time.perf_counter_ns()
        context = service.context_for_task(question["prompt"])
        latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        context_sizes.append(len(json.dumps(context, separators=(",", ":")).encode()))
        rule_ids = {rule["id"] for rule in context["rules"]}
        source_ids = {source["id"] for source in context["sources"]}
        rules_ok = set(question["expected_rule_ids"]) <= rule_ids
        sources_ok = set(question["expected_source_ids"]) <= source_ids
        retrieval_success += int(rules_ok)
        provenance_correct += int(sources_ok)
        question_results.append(
            {"id": question["id"], "rules_ok": rules_ok, "sources_ok": sources_ok}
        )

    caught = 0
    false_positives = 0
    policy_results: list[dict[str, Any]] = []
    for case in corpus["policy_cases"]:
        started = time.perf_counter_ns()
        result = policy_check(
            service,
            PolicyRequest(facts=case["facts"], scope=scope),
            scope_obtained_via="fraimed_mcp",
        )
        latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        finding = result["findings"][0]
        expected_failure = case["expected"] == "violation"
        outcome_ok = finding["outcome"] == case["expected_outcome"]
        if expected_failure and finding["decision"] == "fail" and outcome_ok:
            caught += 1
        if not expected_failure and finding["decision"] != "pass":
            false_positives += 1
        policy_results.append(
            {
                "id": case["id"],
                "decision": finding["decision"],
                "outcome": finding["outcome"],
                "outcome_ok": outcome_ok,
            }
        )

    question_total = len(corpus["questions"])
    violation_total = sum(
        case["expected"] == "violation" for case in corpus["policy_cases"]
    )
    compliant_total = sum(
        case["expected"] == "compliant" for case in corpus["policy_cases"]
    )
    correction_rule_ids = corpus.get(
        "correction_rule_ids",
        [rule.id for rule in service.model.rules],
    )
    rediscovered = _measure_correction_rediscovery(
        model_path, correction_rule_ids
    )
    model_lines = len(model_path.read_text(encoding="utf-8").splitlines())
    thresholds = _thresholds(
        corpus,
        question_total=question_total,
        violation_total=violation_total,
        compliant_total=compliant_total,
        correction_total=len(correction_rule_ids),
    )
    result = {
        "evaluation_id": f"{corpus['corpus_id']}-after",
        "run_at": datetime.now(UTC).isoformat(),
        "corpus": corpus_path.as_posix(),
        "model": Path(corpus["model"]).as_posix(),
        "scope_authority_ref": scope.authority_ref,
        "measurements": {
            "retrieval_success": {
                "successful": retrieval_success,
                "total": question_total,
            },
            "provenance_correctness": {
                "correct": provenance_correct,
                "total": question_total,
            },
            "policy_catch_rate": {
                "caught": caught,
                "violations": violation_total,
            },
            "policy_false_positive_rate": {
                "false_positives": false_positives,
                "compliant_cases": compliant_total,
            },
            "correction_rediscovery": {
                "rediscovered": rediscovered,
                "total": len(correction_rule_ids),
            },
            "latency_ms": {
                "p50": statistics.median(latencies),
                "p95": _percentile(latencies, 0.95),
            },
            "context_size_bytes": {
                "p50": statistics.median(context_sizes),
                "p95": _percentile(context_sizes, 0.95),
            },
            "maintenance": {"model_lines": model_lines},
        },
        "thresholds": thresholds,
        "question_results": question_results,
        "policy_results": policy_results,
    }
    result["passed"] = _passed(result["measurements"], thresholds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _measure_correction_rediscovery(
    model_path: Path, rule_ids: list[str]
) -> int:
    rediscovered = 0
    with tempfile.TemporaryDirectory(prefix="projectlore-eval-") as directory:
        for index, rule_id in enumerate(rule_ids):
            copy_path = Path(directory) / f"model-{index}.yaml"
            shutil.copyfile(model_path, copy_path)
            document = yaml.safe_load(copy_path.read_text(encoding="utf-8"))
            token = f"correction_token_{index}"
            rule = next(item for item in document["rules"] if item["id"] == rule_id)
            rule["rationale"] = f"{rule.get('rationale', '')} {token}".strip()
            copy_path.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
            context = ModelService(copy_path).context_for_task(token)
            if rule_id in {
                rule["id"] for rule in context["rules"]
            }:
                rediscovered += 1
    return rediscovered


def _percentile(values: list[float] | list[int], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * quantile + 0.999) - 1))
    return float(ordered[index])


def _thresholds(
    corpus: dict[str, Any],
    *,
    question_total: int,
    violation_total: int,
    compliant_total: int,
    correction_total: int,
) -> dict[str, int]:
    configured = corpus.get("thresholds", {})
    return {
        "retrieval_success_min": configured.get(
            "retrieval_success_min", question_total
        ),
        "provenance_correctness_min": configured.get(
            "provenance_correctness_min", question_total
        ),
        "policy_catch_rate_min": configured.get(
            "policy_catch_rate_min", violation_total
        ),
        "policy_false_positives_max": configured.get(
            "policy_false_positives_max", 0
        ),
        "correction_rediscovery_min": configured.get(
            "correction_rediscovery_min", correction_total
        ),
        "latency_p95_ms_max": configured.get("latency_p95_ms_max", 100),
        "context_size_p95_bytes_max": configured.get(
            "context_size_p95_bytes_max", 16_384
        ),
        "model_lines_max": configured.get("model_lines_max", 2**31 - 1),
        "compliant_case_count": compliant_total,
    }


def _passed(
    measurements: dict[str, Any], thresholds: dict[str, int]
) -> bool:
    return bool(
        measurements["retrieval_success"]["successful"]
        >= thresholds["retrieval_success_min"]
        and measurements["provenance_correctness"]["correct"]
        >= thresholds["provenance_correctness_min"]
        and measurements["policy_catch_rate"]["caught"]
        >= thresholds["policy_catch_rate_min"]
        and measurements["policy_false_positive_rate"]["false_positives"]
        <= thresholds["policy_false_positives_max"]
        and measurements["correction_rediscovery"]["rediscovered"]
        >= thresholds["correction_rediscovery_min"]
        and measurements["latency_ms"]["p95"]
        <= thresholds["latency_p95_ms_max"]
        and measurements["context_size_bytes"]["p95"]
        <= thresholds["context_size_p95_bytes_max"]
        and measurements["maintenance"]["model_lines"]
        <= thresholds["model_lines_max"]
    )
