"""Portable JSON Schema for the implemented acquisition kernel."""

from __future__ import annotations

import json

from projectlore.acquisition.models import (
    CandidateFile,
    Diagnostic,
    Generation,
    KnowledgeCandidate,
    KnowledgePacket,
    KnowledgeProposal,
    KnowledgeReceipt,
    KnowledgeReview,
    KnowledgeRoot,
    KnowledgeSignal,
    Provenance,
)

PUBLIC_MODELS = (
    CandidateFile,
    Diagnostic,
    Generation,
    KnowledgeCandidate,
    KnowledgePacket,
    KnowledgeProposal,
    KnowledgeReceipt,
    KnowledgeReview,
    KnowledgeRoot,
    KnowledgeSignal,
    Provenance,
)


def render_acquisition_schema() -> str:
    definitions: dict[str, object] = {}
    for model in PUBLIC_MODELS:
        schema = model.model_json_schema(
            ref_template="#/$defs/{model}", mode="validation"
        )
        definitions.update(schema.pop("$defs", {}))
        definitions[model.__name__] = schema
    document = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://projectlore.ai/schema/acquisition-kernel-0.6.1.json",
        "$defs": definitions,
        "x-projectlore-public-contracts": [model.__name__ for model in PUBLIC_MODELS],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
