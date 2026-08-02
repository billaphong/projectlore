"""Constructor-supplied deterministic controller for test compositions only."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FaultPlan:
    ordinal: int
    selector: str
    phase: str
    outcome: str


@dataclass
class FaultController:
    plan: FaultPlan
    visited: set[tuple[int, str]] = field(default_factory=set)

    def checkpoint(
        self, *, ordinal: int, selector: str, phase: str, state_digest: str
    ) -> str:
        del state_digest
        key = (ordinal, phase)
        if key in self.visited:
            raise ValueError("fault checkpoint invoked more than once")
        self.visited.add(key)
        if (
            ordinal == self.plan.ordinal
            and selector == self.plan.selector
            and phase == self.plan.phase
        ):
            return self.plan.outcome
        return "continue"
