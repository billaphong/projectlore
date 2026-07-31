# Getting started

ProjectLore `0.1.0a2` is an early local alpha for Python 3.11 or newer. Canonical
project knowledge remains in human-readable YAML committed to the repository.
The initializer only writes after an explicit preview and does not approve
client-owned trust prompts.

## Install and initialize

Create and activate a virtual environment using the normal command for your
platform. Version `0.1.0a2` is currently an unpublished release candidate:
download its wheel from the successful CI run or build it from the exact source
commit, then install that local artifact. Launch Claude Code or Codex from a
shell where the environment remains active so the generated
`projectlore-mcp`, `projectlore-hook`, and `projectlore-scope-hook` commands
are on `PATH`:

```shell
python -m pip install ./projectlore-0.1.0a2-py3-none-any.whl
```

Do not use `python -m pip install projectlore==0.1.0a2` until the owner has
separately authorized package-index publication.

From the root of a Git repository, preview every proposed file:

```shell
lore init --name "My Project"
```

The JSON output includes the complete proposed content and before/after digest
for each file. Nothing is written. Review it, then apply the same deterministic
proposal:

```shell
lore init --name "My Project" --apply
```

Initialization creates:

- `projectlore.yaml`, a minimal valid canonical project knowledge model;
- managed ProjectLore instruction blocks in `AGENTS.md` and `CLAUDE.md`;
- `.mcp.json` and `.claude/settings.json` entries for Claude Code;
- `.codex/config.toml` and `.codex/hooks.json` entries for Codex CLI.

Both client hook files include a `SessionStart` command that refreshes an
explicitly configured Fraimed workflow target. If no target exists, the hook is
a no-op.

Existing unrelated JSON, TOML, and instruction content is retained. An existing
different canonical model, malformed client file, unmanaged ProjectLore MCP
entry, incomplete managed block, or file change between preview and application
stops initialization with an actionable conflict.

## Validate the installation

```shell
lore validate projectlore.yaml
lore model-status projectlore.yaml
lore context projectlore.yaml "review project knowledge changes"
```

Review the generated client files before approving the repository in Claude
Code or Codex. ProjectLore cannot and does not bypass those trust prompts.
After approval:

```shell
lore doctor projectlore.yaml
```

`lore doctor` checks the installed client versions, model validity, local
configuration, the configured MCP process over stdio, the configured hook
entrypoint's deterministic block, and configuration-bound trust receipts.
Before receipts exist, it may report `operational: true` while keeping
`healthy` and `ready` false. Record a receipt only after personally reviewing
the client configuration:

```shell
lore trust claude_code --client-version 2.1.220 --confirm-reviewed
lore trust codex_cli --client-version 0.146.0 --confirm-reviewed
```

Receipts are local and Git-ignored. Any client version or configuration digest
change invalidates them. Run `lore doctor projectlore.yaml` again; a healthy,
ready result requires both exact receipts to verify.

## Optional workflow scope

ProjectLore queries, validation, and ordinary deterministic rules work without
Fraimed, credentials, or network access. Policy bindings default to
`scope_requirement: "none"`.

For standalone task context:

```shell
lore scope local task-123 --title "Review pricing change"
lore scope status
```

This built-in local provider requires no account or network. To opt into the
Fraimed adapter, set the non-secret Frame and Space identity:

```shell
lore scope target FRAME_ID SPACE_ID
```

The command writes only `.projectlore/scope-target.json`; it never stores a
Fraimed credential. Export `FRAIMED_API_TOKEN` in the agent process
environment, then refresh explicitly or start a configured client session:

```shell
lore scope refresh
lore scope status
```

Refresh uses HTTPS Fraimed MCP and replaces `.projectlore/scope.json`
atomically only after a valid response. A SessionStart network failure is
advisory so the agent can still inspect project knowledge. A policy-relevant
source action remains fail-closed if its binding explicitly declares
`scope_requirement: "workflow"` and the snapshot is absent or stale.

## Gate configured checked-out source

When `.projectlore/source-policy-bindings.json` maps supported Python source to
facts, evaluate the actual checkout before commit:

```shell
lore source-gate projectlore.yaml --all-configured
lore source-gate projectlore.yaml --changed-file pricing.py
```

Use `--root PATH` when the checkout root is not the current directory.

For a CI job, select the narrower evidence label and retain the output:

```shell
lore source-gate projectlore.yaml --all-configured \
  --assurance-scope ci_job_result \
  --output .projectlore/evidence/source-gate.json
```

Exit codes are 0 for pass, 1 for fail, and 2 for indeterminate. Evidence always
sets `repository_certified` to false: a local command or individual CI job does
not prove protected-branch configuration. The scope receipt says
`provided_snapshot` because the gate evaluates the atomically refreshed local
snapshot rather than claiming a live Fraimed query for every check.

## Expected degradation

Model status, search, concept, relationship, validation, task-context, and
timeless policy tools start without a workflow provider. An applicable binding
with `scope_requirement: "workflow"` returns `indeterminate` with
`dependency_unavailable` when context is absent. It never reports success from
missing context that the rule explicitly requires.

Local hooks are bypassable and do not constitute repository protection.
External checker execution fails closed unless a supported operating-system
network sandbox is configured. See [compatibility](compatibility.md) for the
complete platform limits.

## Troubleshooting

- Run `lore validate projectlore.yaml --json` for source-located diagnostics.
- Run `lore doctor projectlore.yaml` after approving both client configurations.
- If MCP startup fails, run `projectlore-mcp` with
  `PROJECTLORE_MODEL=projectlore.yaml` and inspect the startup error.
- If initialization reports a conflict, edit or remove only the named
  ProjectLore entry and preview again. Do not replace unrelated client content.
- If a malformed model is saved while MCP is running, reads continue against
  the disclosed last-known-good snapshot while `model_validate` reports the
  candidate diagnostics.

## Remove ProjectLore

Uninstall the package from the environment:

```shell
python -m pip uninstall projectlore
```

Then remove only the generated `projectlore` MCP entry, the generated
`PreToolUse` hook entry whose command is `projectlore-hook`, the generated
`SessionStart` entry whose command is `projectlore-scope-hook`, and text between the
`PROJECTLORE_MANAGED_START` and `PROJECTLORE_MANAGED_END` markers. Delete
`projectlore.yaml` only if its Git history is no longer required. Local
`.projectlore/trust/` receipts and other disposable `.projectlore/` state may be
removed after review.
