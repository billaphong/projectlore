# ProjectLore

Give every agent the same understanding of your project.

ProjectLore creates and serves a shared, machine-readable project knowledge
model: the concepts, relationships, terminology, rules, provenance, and
implementation anchors that coding agents need to work consistently within a
software project. It attaches to the development workflow through MCP, agent
hooks, local checks, and CI without becoming a work tracker or code graph.

## Vocabulary

- **Project knowledge model:** the complete model for a project.
- **Domain model:** a focused model for one business or technical domain.
- **Domain map:** a view of the concepts and relationships in a domain model.

## Principles

- Git-native, human-reviewable knowledge models
- Strict Pydantic contracts with a committed generated JSON Schema
- Deterministic whole-model validation with stable diagnostic codes
- First-class MCP access for Claude Code and Codex CLI
- Links between domain concepts, project decisions, and source code
- Explicit provenance instead of unattributed generated knowledge
- Read-only agent access by default
- Honest enforcement states that do not overstate hooks or CI

## Repository layout

```text
schemas/                  Generated portable JSON Schema
examples/                 Small example project models
src/projectlore/          Python package and `lore` CLI
tests/                    Automated tests
docs/                     Architecture and design documentation
```

## Development

ProjectLore requires Python 3.11 or newer.

```shell
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev]"
lore status examples/homebrew.project.yaml
lore validate examples/homebrew.project.yaml
lore schema schemas/projectlore.schema.json --check
lore model-status examples/homebrew.forecast-trust.project.yaml
lore context-for-task examples/homebrew.forecast-trust.project.yaml \
  "prevent current-day calibration look-ahead"
pytest
```

Canonical project models are human-authored YAML in Git. The executable
structural contract is `src/projectlore/models.py`; the portable structural
contract is the generated JSON Schema; whole-model identity, reference, and
provenance checks live in the semantic validator.

The Homebrew walking skeleton includes project-local MCP and `PreToolUse`
configuration for Claude Code and Codex. Both clients require their normal
explicit project and hook trust review before those integrations run. The
blocking hook interprets only bounded `*.projectlore-policy.json` inputs,
confines paths to the repository root, invokes built-in checkers with fixed
arguments, and performs no network access.

See [the pilot proof](docs/pilots/homebrew-forecast-trust.md) for its frozen
corpus, thresholds, and explicit limits.
