"""Deterministically expose the frozen phase-failure matrix."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from projectlore_fault_support.controller import FaultController, FaultPlan
from projectlore_fault_support.machine import MachineState, advance, terminate


def generate(contract: Path) -> list[dict[str, object]]:
    value = json.loads(contract.read_text(encoding="utf-8"))
    return list(value["phase_failure_matrix"])


def generate_traces(contract: Path) -> list[dict[str, object]]:
    traces = []
    for case in generate(contract):
        plan = FaultPlan(
            int(case["ordinal"]),
            str(case["selector"]),
            str(case["phase"]),
            str(case["outcome"]),
        )
        controller = FaultController(plan)
        machine = MachineState(programs=tuple(sorted(MachineState().programs)))
        before = _state_digest(machine)
        outcome = "continue"
        for ordinal in range(1, 13):
            if ordinal == plan.ordinal and plan.phase in {"before", "before_acquire"}:
                outcome = controller.checkpoint(
                    ordinal=ordinal,
                    selector=plan.selector,
                    phase=plan.phase,
                    state_digest=_state_digest(machine),
                )
                break
            if ordinal in {1, 2, 5, 7, 9, 11, 12}:
                target = advance(machine, "writer-1")
                if target is not None:
                    machine = target
            if ordinal == plan.ordinal and plan.phase in {"after", "after_acquire"}:
                outcome = controller.checkpoint(
                    ordinal=ordinal,
                    selector=plan.selector,
                    phase=plan.phase,
                    state_digest=_state_digest(machine),
                )
                break
        machine = terminate(machine, "writer-1")
        for _ in range(5):
            target = advance(machine, "recoverer-1")
            if target is not None:
                machine = target
        state = machine.observation
        after = _state_digest(machine)
        plan_value = {
            "ordinal": plan.ordinal,
            "selector": plan.selector,
            "phase": plan.phase,
            "outcome": plan.outcome,
        }
        plan_id = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(plan_value, sort_keys=True).encode()
            ).hexdigest()
        )
        trace_base = {
            "contract_version": "projectlore-fault-trace/0.6.1",
            "plan_id": plan_id,
            "events": [
                {
                    "sequence": 1,
                    "ordinal": case["ordinal"],
                    "selector": case["selector"],
                    "phase": case["phase"],
                    "outcome": outcome,
                    "state_before": before,
                    "state_after": after,
                }
            ],
            "observation": state,
            "proof": state in {"old", "new"},
        }
        trace_id = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(trace_base, sort_keys=True).encode()
            ).hexdigest()
        )
        traces.append({**trace_base, "trace_id": trace_id})
    return traces


def _state_digest(state: MachineState) -> str:
    return "sha256:" + hashlib.sha256(repr(state.key).encode()).hexdigest()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: projectlore-fault-generate FAULT_CONTRACT")
    print(
        json.dumps(generate(Path(sys.argv[1])), separators=(",", ":"), sort_keys=True)
    )
