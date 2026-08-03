"""Executable bounded model of the acquisition canonical/workflow transaction."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class MachineState:
    canonical_root: str = "old"
    workflow_root: str = "old"
    claim: str = "none"
    canonical_lock: str | None = None
    workflow_lock: str | None = None
    programs: tuple[tuple[str, int], ...] = (
        ("writer-1", 0),
        ("writer-2", 0),
        ("recoverer-1", 0),
        ("recoverer-2", 0),
    )

    @property
    def observation(self) -> str:
        if self.canonical_root == self.workflow_root:
            return self.canonical_root
        return "neither"

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.canonical_root,
            self.workflow_root,
            self.claim,
            self.canonical_lock,
            self.workflow_lock,
            self.programs,
        )


WRITER_STEPS = (
    "lock.canonical",
    "lock.workflow",
    "claim",
    "canonical_root.replace",
    "workflow_root.replace",
    "lock.workflow.release",
    "lock.canonical.release",
)
RECOVERER_STEPS = (
    "lock.canonical",
    "lock.workflow",
    "recover",
    "lock.workflow.release",
    "lock.canonical.release",
)


def advance(state: MachineState, worker: str) -> MachineState | None:
    programs = dict(state.programs)
    pc = programs[worker]
    steps = WRITER_STEPS if worker.startswith("writer") else RECOVERER_STEPS
    if pc >= len(steps):
        return None
    step = steps[pc]
    updated = state
    if step == "lock.canonical":
        if state.canonical_lock not in (None, worker):
            return None
        updated = replace(state, canonical_lock=worker)
    elif step == "lock.workflow":
        if state.canonical_lock != worker or state.workflow_lock not in (None, worker):
            return None
        updated = replace(state, workflow_lock=worker)
    elif step == "claim":
        updated = replace(state, claim="old")
    elif step == "canonical_root.replace":
        updated = replace(state, canonical_root="new", claim="new")
    elif step == "workflow_root.replace":
        updated = replace(state, workflow_root="new", claim="none")
    elif step == "recover":
        if state.claim == "new":
            updated = replace(state, workflow_root="new", claim="none")
        elif state.claim == "old":
            updated = replace(state, claim="none")
    elif step == "lock.workflow.release":
        if state.workflow_lock != worker:
            return None
        updated = replace(state, workflow_lock=None)
    elif step == "lock.canonical.release":
        if state.canonical_lock != worker:
            return None
        updated = replace(state, canonical_lock=None)
    programs[worker] = pc + 1
    return replace(updated, programs=tuple(sorted(programs.items())))


def terminate(state: MachineState, worker: str) -> MachineState:
    programs = dict(state.programs)
    steps = WRITER_STEPS if worker.startswith("writer") else RECOVERER_STEPS
    programs[worker] = len(steps)
    return replace(
        state,
        canonical_lock=None if state.canonical_lock == worker else state.canonical_lock,
        workflow_lock=None if state.workflow_lock == worker else state.workflow_lock,
        programs=tuple(sorted(programs.items())),
    )


def explore(
    max_states: int = 100_000,
) -> tuple[set[tuple[object, ...]], set[tuple[object, ...]]]:
    initial = MachineState(programs=tuple(sorted(MachineState().programs)))
    states = {initial.key}
    transitions: set[tuple[object, ...]] = set()
    pending = [initial]
    while pending:
        state = pending.pop()
        for worker, _ in state.programs:
            target = advance(state, worker)
            if target is None:
                continue
            transitions.add((state.key, worker, target.key))
            if target.key not in states:
                if len(states) >= max_states:
                    raise ValueError("fault exploration exceeded state bound")
                states.add(target.key)
                pending.append(target)
    return states, transitions
