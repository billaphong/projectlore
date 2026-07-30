from __future__ import annotations

import json
from pathlib import Path

import yaml

from projectlore.validation import validate_path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"
CORPUS = ROOT / "evaluations" / "homebrew-forecast-trust" / "corpus.yaml"
BASELINE = ROOT / "evaluations" / "homebrew-forecast-trust" / "baseline.json"


def test_pilot_model_has_exactly_three_valid_invariants() -> None:
    model, report = validate_path(MODEL)

    assert report.valid
    assert model is not None
    assert [rule.id for rule in model.rules] == [
        "lore:homebrew/rule/calibration-predates-forecast",
        "lore:homebrew/rule/forecast-issued-by-snapshot",
        "lore:homebrew/rule/demand-covers-safety-lookahead",
    ]
    assert all(rule.source_refs for rule in model.rules)


def test_pilot_corpus_is_frozen_and_balanced() -> None:
    corpus = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))

    assert corpus["corpus_id"] == "homebrew-forecast-trust-v1"
    assert len(corpus["questions"]) == 6
    assert len({question["id"] for question in corpus["questions"]}) == 6
    cases = corpus["policy_cases"]
    assert len(cases) == 6
    assert len({case["id"] for case in cases}) == 6
    assert sum(case["expected"] == "violation" for case in cases) == 3
    assert sum(case["expected"] == "compliant" for case in cases) == 3


def test_foundation_baseline_covers_comparative_measures() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    measurements = baseline["measurements"]

    assert {
        "retrieval_success",
        "provenance_correctness",
        "policy_catch_rate",
        "policy_false_positive_rate",
        "correction_rediscovery",
        "latency_ms",
        "context_size_bytes",
    } <= measurements.keys()
    assert measurements["retrieval_success"]["total"] == 6
    assert measurements["policy_catch_rate"]["violations"] == 3
    assert measurements["policy_false_positive_rate"]["compliant_cases"] == 3
