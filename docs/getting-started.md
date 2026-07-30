# Getting started

ProjectLore `0.1.0a2` is an early local alpha for Python 3.11 or newer. Canonical
project knowledge remains in human-readable YAML committed to the repository.
The initializer only writes after an explicit preview and does not approve
client-owned trust prompts.

## Install and initialize

Create and activate a virtual environment using the normal command for your
platform, then install ProjectLore. Launch Claude Code or Codex from a shell
where that environment remains active so the generated `projectlore-mcp` and
`projectlore-hook` commands are on `PATH`:

```shell
python -m pip install projectlore==0.1.0a2
```

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
configuration, MCP process identity, a deterministic hook block, and
configuration-bound trust receipts. Record a receipt only after personally
reviewing the client configuration:

```shell
lore trust claude_code --client-version 2.1.220 --confirm-reviewed
lore trust codex_cli --client-version 0.146.0 --confirm-reviewed
```

Receipts are local and Git-ignored. Any client version or configuration digest
change invalidates them.

## Expected degradation

Model status, search, concept, relationship, validation, and task-context tools
start without a Fraimed credential. `policy_check` requires fresh Fraimed scope;
without a configured token it returns `indeterminate` with
`dependency_unavailable`. It never reports success from missing workflow scope.

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
`PreToolUse` hook entry whose command is `projectlore-hook`, and text between the
`PROJECTLORE_MANAGED_START` and `PROJECTLORE_MANAGED_END` markers. Delete
`projectlore.yaml` only if its Git history is no longer required. Local
`.projectlore/trust/` receipts and other disposable `.projectlore/` state may be
removed after review.
