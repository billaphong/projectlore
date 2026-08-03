# Agent onboarding

This runbook is for a coding agent—or a person directing one—starting with no
ProjectLore context. It covers installing the tool, enabling one target
repository, proving the integration, and handing the repository to another
agent. ProjectLore is an alpha: review every proposed write and keep the normal
Git review boundary.

## Understand the two scopes

ProjectLore has an executable installation and a separate project integration:

| Scope | Contains | Recommended use |
| --- | --- | --- |
| Python environment | `lore`, both ProjectLore MCP servers, and all three hooks | Install once in an environment available to the agent clients. |
| Target Git repository | Canonical model, MCP configuration, hooks, and managed agent instructions | Initialize separately in every project that should use ProjectLore. |

Installing the package does not modify a target repository. Initializing a
repository does not install the executable. Canonical project knowledge belongs
to the target repository; disposable runtime state remains under its
`.projectlore/` directory.

## Prerequisites

Before changing a target project, confirm:

- Python 3.11 or newer is available as `python`;
- the target is a Git repository and its existing worktree state is understood;
- Claude Code 2.1.220 or newer and/or Codex CLI 0.146.0 or newer is installed;
- the person responsible for the repository can review project MCP and hook
  configuration; and
- the ProjectLore `0.1.0a3` wheel or exact source checkout is available.

The supported alpha matrix is CPython 3.11 and 3.13 on Windows, Ubuntu, and
macOS. Other Python 3.11+ versions are expected to work but are not release
gates. ProjectLore does not need Fraimed, CodeGraph, credentials, or network
access for its standalone core.

## 1. Obtain and install the alpha

`0.1.0a3` is not published to a package index. Do not run
`pip install projectlore==0.1.0a3`. Use one of these reviewed paths.

### Option A: install the verified wheel

Download the `projectlore-0.1.0a3` artifact only from a successful workflow for
the reviewed source commit. Compare its published SHA-256 receipt before
installation. Until that workflow exists, build from the exact checkout using
Option B; do not reuse hashes from an earlier alpha.

Verify the downloaded wheel before installing it. PowerShell example:

```powershell
Get-FileHash .\projectlore-0.1.0a3-py3-none-any.whl -Algorithm SHA256
python -m venv C:\Tools\projectlore-0.1.0a3
C:\Tools\projectlore-0.1.0a3\Scripts\python.exe -m pip install `
  .\projectlore-0.1.0a3-py3-none-any.whl
```

POSIX shell example:

```shell
sha256sum ./projectlore-0.1.0a3-py3-none-any.whl
python -m venv "$HOME/.local/share/projectlore/0.1.0a3"
"$HOME/.local/share/projectlore/0.1.0a3/bin/python" -m pip install \
  ./projectlore-0.1.0a3-py3-none-any.whl
```

Add that environment's executable directory to the shell `PATH`, or always
launch Claude Code and Codex from a shell where the environment is activated.
The generated alpha configuration invokes six console commands by name.
An environment dedicated to ProjectLore is preferable to an unrelated
application's virtual environment.

### Option B: build from the exact source commit

Use this when the verified wheel is unavailable:

```shell
git clone https://github.com/billaphong/projectlore.git
cd projectlore
git checkout 7354658a7e1424f18fdc5228e942371a781dc8af
python -m venv .venv
# Windows: .venv\Scripts\activate
# POSIX:   . .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m mypy src/projectlore
python -m build
python scripts/verify_distribution.py dist
```

Install the resulting wheel into the environment that the target project's
agent clients will use. An editable development environment is appropriate for
contributing to ProjectLore, but a built wheel is the better target-project
test because it exposes missing package files.

Verify either installation:

```shell
lore --version
lore --help
```

Also confirm that `projectlore-mcp`, `projectlore-acquisition-mcp`,
`projectlore-hook`, `projectlore-scope-hook`, and
`projectlore-acquisition-hook` resolve from the same shell. Do not launch either
MCP command as an interactive probe: stdio servers wait for MCP input. The
complete startup check occurs after initialization.

If an editable install has `lore` but is missing a newer entry point, refresh
its generated console scripts before diagnosing the package or initializer:

```shell
python -m pip install -e .
```

Then repeat the six-command resolution check. A target repository is not ready
until every command referenced by its generated MCP and hook configuration is
available to the client process.

## 2. Inspect the target repository

Change to the target repository root. Do not initialize from a parent directory
or a nested package directory.

```shell
git status --short --branch
```

Read the repository's existing `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`,
`.mcp.json`, `.claude/settings.json`, `.codex/config.toml`, and
`.codex/hooks.json` when present. Preserve unrelated content. If another MCP
server already uses the name `projectlore`, stop and resolve ownership rather
than overwriting it.

## 3. Preview and initialize

Preview from the target root:

```shell
lore init --name "My Project"
```

The preview is non-mutating and includes complete proposed contents and
before/after digests. Review every path. Initialization normally proposes:

- `projectlore.yaml` as the canonical project knowledge model;
- managed blocks in `AGENTS.md` and `CLAUDE.md`;
- Claude project MCP and hook configuration in `.mcp.json` and
  `.claude/settings.json`; and
- Codex project MCP and hook configuration in `.codex/config.toml` and
  `.codex/hooks.json`.

Apply only the reviewed proposal:

```shell
lore init --name "My Project" --apply
git diff -- projectlore.yaml AGENTS.md CLAUDE.md .mcp.json .claude .codex
```

Initialization fails rather than replacing unmanaged ProjectLore entries,
malformed configuration, a different existing canonical model, incomplete
managed markers, or files changed after preview.

## 4. Replace starter meaning with accepted project knowledge

The generated model is deliberately minimal. Before presenting ProjectLore as
useful, inspect the target repository's architecture, terminology, policies,
and authoritative documents and then review changes to `projectlore.yaml` like
code. At minimum:

1. Define focused domains with authoritative provenance.
2. Add important concepts and preferred terminology.
3. Add relationships that help agents navigate meaning.
4. Add only accepted Rules; do not convert guesses into policy.
5. Link concepts or Rules to implementation anchors when stable references
   exist.
6. Distinguish asserted knowledge from suggestions or inference.

Inspect `schemas/projectlore.schema.json` and
`examples/contracts/portable.valid.yaml` when authoring model structure. Every
asserted concept and relationship must retain provenance. ProjectLore YAML is
canonical; generated indexes and code-graph observations are disposable views.

Validate after each coherent edit:

```shell
lore validate projectlore.yaml
lore model-status projectlore.yaml
lore context projectlore.yaml "the first real task for this project"
```

Do not commit a model merely because it is structurally valid. A maintainer
must also confirm that its meaning and authority are correct.

## 5. Review and trust each client

ProjectLore cannot approve Claude Code or Codex trust prompts. Review the exact
project files first, then open each client from the target repository in a shell
where the ProjectLore commands are on `PATH`.

Codex ignores project `.codex/config.toml`, `.codex/hooks.json`, and local rules
until the Git repository is trusted. Run Codex from the repository root, review
and accept its trust prompt, then use `codex mcp list` to confirm both
`projectlore` and `projectlore-acquisition`. A missing server in an untrusted or
non-Git scratch directory is expected and is not an MCP startup failure.

Confirm that:

- the MCP command is `projectlore-mcp`;
- `PROJECTLORE_MODEL` names the intended repository-relative model;
- the hooks invoke only the three documented ProjectLore hook commands with the
  documented timeouts;
- unrelated client settings were preserved; and
- the client identifies the configuration as project-scoped.

After approving the repository in each installed client, record the exact
reviewed client version:

```shell
claude --version
codex --version
lore trust claude_code --client-version 2.1.220 --confirm-reviewed
lore trust codex_cli --client-version 0.146.0 --confirm-reviewed
```

Use the versions actually printed on the machine, not the example versions.
Only issue a receipt for a client that is installed and personally reviewed.
Receipts are local, Git-ignored, and bound to the client version and exact
configuration digests. Configuration or version drift invalidates them.

## 6. Prove the installed integration

Run:

```shell
lore doctor projectlore.yaml
lore integration check projectlore.yaml
```

`lore doctor` validates the model, parses both clients' project configuration,
starts the installed MCP server over stdio, checks process contract identity,
executes the installed hook probe, and verifies trust receipts. `operational`
can be true before trust is recorded; `healthy` and `ready` remain false until
the required reviewed receipts match.

Then start a new Claude Code or Codex session from the repository root. Ask the
agent to:

1. call `model_status`;
2. call `context_for_task` for a real task;
3. resolve one project term with `model_resolve_term`;
4. retrieve one concept and its provenance; and
5. run `policy_check` with a harmless applicable request if the model has a
   deterministic policy binding.

The agent should identify the same model and model digest in both clients.
Missing information must be reported as missing, not as an empty successful
result. MCP reads must not modify `projectlore.yaml` or included model files.

## 7. Decide what to commit

Normally commit and review:

- `projectlore.yaml` or `.projectlore/model.yaml` and any declared includes;
- managed `AGENTS.md` and `CLAUDE.md` blocks;
- project MCP and hook configuration;
- `.projectlore/policy-bindings.json` when deterministic policy is enabled; and
- `.projectlore/source-policy-bindings.json` when checked-out source facts are
  enabled.

Do not commit:

- `.projectlore/trust/` receipts;
- local workflow declarations or external scope snapshots;
- evidence, caches, indexes, databases, embeddings, or generated graphs;
- tokens, `.env` files, or provider credentials; or
- a virtual environment.

Run `git status --short` and inspect the complete diff before committing. If the
target repository's ignore rules differ, add narrow ignore entries without
hiding the two reviewable policy-binding files.

## 8. Use ProjectLore during normal work

At the beginning of a task, agents should use the project-scoped MCP tools for
meaning and policy and continue using CodeGraph or source tools for code
structure. A practical loop is:

1. Read the applicable agent instructions.
2. Request `context_for_task` with the actual task and relevant paths.
3. Resolve ambiguous terms before editing.
4. Check related concepts, Rules, provenance, and implementation anchors.
5. Run `policy_check` before a policy-sensitive action.
6. Validate canonical model edits and review their Git diff.

The initial read-only MCP surface is `model_status`, `model_search`,
`model_get_concept`, `model_resolve_term`, `model_get_relationships`,
`model_validate`, `context_for_task`, and `policy_check`.

Standalone operation is the default. Optional local task context can be
declared with a preview/apply pair:

```shell
lore scope local task-123 --title "Review pricing change"
lore scope local task-123 --title "Review pricing change" --apply
lore scope status
```

Use an external Fraimed target only when the project explicitly chooses that
adapter. Do not treat Fraimed as required ProjectLore infrastructure.

## 9. Upgrade, repair, or remove

Before upgrading, read `CHANGELOG.md`, `docs/versioning-and-migrations.md`, and
the new release's compatibility notes. Install the new artifact, rerun
`lore init` as a preview to inspect managed configuration changes, re-review
both clients, issue new trust receipts, and rerun `lore doctor`. Never silently
rewrite canonical model semantics during an upgrade.

For repair:

```shell
lore validate projectlore.yaml --json
lore doctor projectlore.yaml
```

If MCP startup fails, verify that the client process can resolve
`projectlore-mcp` and that `PROJECTLORE_MODEL` points to exactly one valid model.
If a client configuration conflicts, edit only the named ProjectLore-owned
entry and preview again; do not replace unrelated content.

For removal, preview before applying:

```shell
lore remove
lore remove --apply
python -m pip uninstall projectlore
```

Removal preserves canonical model YAML and client-owned content. Delete the
model only through the repository's normal review process.

## Completion checklist

Onboarding is complete only when all applicable items are true:

- [ ] The installed `lore --version` is the intended reviewed version.
- [ ] The executable environment is available to both agent clients.
- [ ] Initialization was previewed before it was applied.
- [ ] The canonical model contains reviewed project-specific meaning and
      provenance, not only starter content.
- [ ] `lore validate`, `lore model-status`, and a real task-context query pass.
- [ ] Claude Code and/or Codex project MCP and hooks were explicitly reviewed.
- [ ] Trust receipts match the exact installed client versions and configs.
- [ ] `lore doctor` reports the expected operational, healthy, and ready state.
- [ ] A real client session successfully calls the ProjectLore MCP tools.
- [ ] Canonical and integration files are reviewed for commit; local state and
      secrets remain untracked.
- [ ] Another agent can start from the repository instructions and retrieve the
      same project meaning without a private prompt or Fraimed dependency.

When handing off, report the ProjectLore version, model path and digest, enabled
clients, doctor result, optional provider choice, files committed, and any
indeterminate or deliberately unsupported enforcement state.
