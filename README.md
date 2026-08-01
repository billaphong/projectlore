# ProjectLore

Give every agent the same understanding of your project.

ProjectLore creates and serves a shared, machine-readable project knowledge
model: the concepts, relationships, terminology, rules, provenance, and
implementation anchors that coding agents need to work consistently within a
software project. It attaches to the development workflow through MCP, agent
hooks, local checks, and CI without becoming a work tracker or code graph.

ProjectLore is licensed under the [Apache License 2.0](LICENSE).

## Quick start

ProjectLore requires Python 3.11 or newer. `0.1.0a2` is currently an
unpublished release candidate. Install the wheel downloaded from the successful
CI run (or built locally from this exact checkout), then initialize a new Git
repository:

```shell
python -m pip install ./projectlore-0.1.0a2-py3-none-any.whl
lore init --name "My Project"
# Review the complete preview, then:
lore init --name "My Project" --apply
lore validate projectlore.yaml
lore context projectlore.yaml "review project knowledge changes"
```

Review and approve the generated project MCP and hook files in Claude Code and
Codex before running `lore doctor projectlore.yaml`. ProjectLore never bypasses
client-owned trust. See the complete [getting-started guide](docs/getting-started.md)
for configuration review, expected degradation, troubleshooting, and removal.
The package-index command
`python -m pip install projectlore==0.1.0a2` becomes valid only after the owner
separately authorizes and completes publication.

ProjectLore works without Fraimed or any hosted workflow service. Deterministic
rules default to standalone evaluation. Optional local workflow context can be
previewed and set with `lore scope local ... --apply`; an explicit
`lore scope target --provider fraimed SCOPE_ID CONTAINER_ID`
instead enables the Fraimed adapter. Generated SessionStart hooks refresh only
that configured external target. Configured checked-out source can be evaluated with
`lore source-gate projectlore.yaml --all-configured`; its local or CI evidence
never claims repository certification.

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
lore integrate
lore doctor examples/homebrew.forecast-trust.project.yaml
# After reviewing and approving each client's project MCP and hooks:
lore trust claude_code --client-version 2.1.220 --confirm-reviewed
lore trust codex_cli --client-version 0.146.0 --confirm-reviewed
pytest
```

Canonical project models are human-authored YAML in Git. The executable
structural contract is `src/projectlore/models.py`; the portable structural
contract is the generated JSON Schema; whole-model identity, reference, and
provenance checks live in the semantic validator.

Repository discovery checks `.projectlore/model.yaml` and then
`projectlore.yaml`, rejecting ambiguous entrypoints. A model may declare an
`includes` list of repository-relative YAML files. Loading is UTF-8-only,
root-confined, symlink-free, SafeLoader-based, and bounded by file size, total
size, file count, node count, and nesting depth. Diagnostics retain stable codes,
model paths, source files, and line/column locations where YAML supplies them.

The Homebrew walking skeleton includes project-local MCP and `PreToolUse`
configuration for Claude Code and Codex. Both clients require their normal
explicit project and hook trust review before those integrations run. The
blocking hook interprets only bounded `*.projectlore-policy.json` inputs,
confines paths to the repository root, invokes built-in checkers with fixed
arguments, and performs no network access.

`lore integrate` previews managed ProjectLore blocks for `AGENTS.md` and
`CLAUDE.md`; it writes only with `--apply`, preserves content outside its
delimited block, and rejects drift between preview and application. The
versioned client capability matrix is in `docs/client-capabilities.json`.
`lore doctor` checks installed client minimums, both project MCP and hook
configurations, MCP startup, cross-process contract identity, and real hook
block behavior. Client-owned project and hook trust remains explicitly
unverified until reviewed in each client. `lore trust` then writes a local,
Git-ignored receipt under `.projectlore/trust/`, bound to the exact client
version and configuration digests. Any configuration or version drift
invalidates that receipt.

Interactive lifecycle adapters normalize supported `SessionStart`,
`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and `Stop` inputs into the
bounded `projectlore-agent-event/0.1.0` contract. Only a deterministic,
applicable pre-action violation blocks. Post-action findings are advisory and
never claim to reverse completed side effects. Session receipts attest only
that context was requested and resolved—not that an agent understood it.

Executable checker authority is local runtime policy, not canonical model
content. `CheckerRegistry` accepts only operator-constructed
`TrustedChecker` entries. Model-provided labels cannot add arguments or change
the executable, environment, working directory, timeout, output bound,
dependency pins, or deny-network policy. The runner resolves and confines
paths, verifies digests, starts no shell, sanitizes the environment, bounds
captured output, and terminates the process group on timeout. External
execution fails closed unless a trusted operating-system network sandbox is
supplied. The first concrete backend uses bubblewrap with an unshared network
namespace and a read-only project bind; its executable is digest-pinned.
Network exceptions are not supported in this release. All model,
workflow-provider, documentation, and code context remains explicitly untrusted data;
common inline credentials are redacted and prompt-like text is never executed.

Repository assurance remains evidence-scoped. Changed files resolve to rules
through implementation anchors; any unmapped change conservatively selects all
rules. Local adapters delegate to existing Semgrep, architecture-test, or
project-test commands through the trusted checker registry rather than
reimplementing their semantics. Local and pre-commit results are explicitly
`local_advisory`: hooks can be bypassed and never certify a repository or
protected branch. Hosted CI configuration is not generated or modified without
repository-specific authorization.

CodeGraph integration is optional and read-only. `AdapterRegistry` accepts a
bounded lookup client, and `CodeGraphAdapter` resolves Concept and Rule
implementation anchors into provenance-bearing observations. Absent, stale,
rebuilding, ambiguous, and broken results remain explicit and localized; a
required unavailable lookup is indeterminate. The adapter retains stable
references and observation digests, never a mirrored code graph.

Long-lived MCP processes use validated request-driven refresh. Valid Git edits
activate atomically on the next request; malformed edits are disclosed while
queries continue against the last valid immutable snapshot. Pilot latency and
corpus measurements did not justify SQLite, a background watcher, embeddings,
or graph storage; see
[the scale decision](docs/scale-and-refresh-decision.md).

`lore integration check MODEL [--evidence EVIDENCE.json]` reports the highest
contiguously proven assurance state and every missing requirement. The only
states are `available`, `hook_active`, `local_gate_passed`, `ci_gate_passed`,
and `protected_gate_enforced`. The command works offline and reports
`available` without an evidence file. Optional protected-gate verification is
read-only and requires separately authorized hosted credentials; ProjectLore
does not acquire or infer those credentials. Protected enforcement requires a
fresh accessible observation naming the repository, branch, required hosted
check, non-bypass policy, configuration revision/time, and the verifier's
`repository:read` and `rules:read` permission scopes. Missing, stale, or
insufficient hosted evidence remains indeterminate and never promotes the
reported state.

Imported gate JSON is an untrusted claim. Version 1 evidence is checked for
internal integrity, exact plan/execution binding, and current-model impact
semantics, but its self-hash cannot authenticate where it ran. Imported
evidence alone therefore cannot promote a local or hosted gate state;
authenticated provenance remains a separately reported requirement.

See [the pilot proof](docs/pilots/homebrew-forecast-trust.md) for its frozen
corpus, thresholds, and explicit limits.

The contrasting
[Sienna campaign-authority pilot](docs/pilots/sienna-campaign-authority.md)
reuses the same model, MCP, policy-result, and scope-receipt contracts for a
deterministic C# simulation domain without changing the Sienna repository.

The retained pilots do not currently justify a dedicated product UI. See the
[dedicated UI decision](docs/ui-decision.md) for the evidence, alternatives,
and measurable re-evaluation triggers.
