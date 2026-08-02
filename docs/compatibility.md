# Client and platform compatibility

## Python and operating systems

ProjectLore requires Python 3.11 or newer. The alpha gate covers CPython 3.11
and 3.13 on current GitHub-hosted Windows, Ubuntu, and macOS runners. Other
Python 3.11+ versions are expected to work but are not release-gated until added
to the matrix.

## Agent clients

The executable capability matrix is `docs/client-capabilities.json`.

| Client | Minimum verified version | Instructions | MCP | Hooks |
| --- | ---: | --- | --- | --- |
| Claude Code | 2.1.220 | `CLAUDE.md` | project `.mcp.json`, stdio | reviewed project `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop` |
| Codex CLI | 0.146.0 | root-to-current `AGENTS.md` chain | trusted project `.codex/config.toml`, stdio | reviewed project `.codex/hooks.json` for the shared events |

These minimums are the exact versions exercised locally for the alpha, not a
claim that earlier versions cannot work. `lore doctor` reports installed-version,
configuration, startup, process-identity, hook, and local trust-receipt state.

Codex loads project `.codex/` layers only for trusted Git repositories. Verify
from the repository root with `codex mcp list`; both `projectlore` and
`projectlore-acquisition` must appear. An untrusted or non-repository fixture is
not a valid project-MCP compatibility probe.

Codex officially supports project-scoped MCP configuration in trusted
`.codex/config.toml`, stdio servers, server instructions, and explicit hook
review. Codex rebuilds its `AGENTS.md` instruction chain at session start.
See the official
[Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp.md),
[Codex hooks documentation](https://learn.chatgpt.com/docs/hooks.md), and
[AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md).

Claude Code exposes `claude mcp` and project MCP configuration and supports
Windows through WSL or Git for Windows. See Anthropic's
[CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage),
[setup guide](https://docs.anthropic.com/en/docs/claude-code/getting-started),
and [MCP overview](https://docs.anthropic.com/en/docs/mcp).

## Known degradation

- MCP and instructions remain useful when hooks are unavailable or untrusted,
  but no blocking enforcement is claimed.
- Local hooks are always bypassable. Repository protection requires separately
  verified hosted evidence.
- Missing or stale Fraimed scope makes applicable policy indeterminate.
- Missing, stale, or rebuilding CodeGraph leaves anchor observations partial or
  indeterminate when required; core model queries continue.
- External checkers remain indeterminate without a verified deny-network
  operating-system sandbox.
- Client-owned trust is invalidated by version or configuration digest drift.
- Native Windows does not provide the current bubblewrap network sandbox;
  external checker execution therefore fails closed.

No client-specific model semantics exist: both clients consume the same MCP
contract, model digest, policy outcomes, and receipts.
