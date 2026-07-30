# Changelog

ProjectLore follows Keep a Changelog and Semantic Versioning. Dates use UTC.

## [Unreleased]

- No unreleased changes.

## [0.1.0a2] - 2026-07-30

### Added

- Preview-first `lore init` for a minimal canonical model, managed agent
  instructions, and cross-platform Claude Code and Codex CLI MCP/hook entries.
- Installed-wheel fresh-repository acceptance covering real MCP stdio transport,
  hook allow/block behavior, valid refresh, and malformed-edit last-known-good
  recovery.
- A public installation, trust-review, troubleshooting, and removal guide.

### Changed

- Read-only MCP tools now start without Fraimed credentials. Scope-dependent
  policy checks explicitly degrade to `dependency_unavailable`.

## [0.1.0a1] - 2026-07-30

### Added

- Git-native project knowledge model with strict validation and generated JSON
  Schema.
- Read-only query, context, policy, status, and validation tools over MCP and
  CLI.
- Claude Code and Codex CLI integration, capability inspection, and
  review-bound trust receipts.
- Trusted checker execution, repository assurance reporting, optional
  CodeGraph anchor resolution, and validated last-valid model refresh.
- Proven Homebrew and Sienna pilot corpora.

### Security

- Canonical content is non-executable and read-only to MCP.
- Executable checkers require an operator-owned digest-pinned registry.
- External execution requires a deny-network operating-system sandbox.

[Unreleased]: https://github.com/billaphong/projectlore/compare/v0.1.0a2...HEAD
[0.1.0a2]: https://github.com/billaphong/projectlore/compare/v0.1.0a1...v0.1.0a2
[0.1.0a1]: https://github.com/billaphong/projectlore/releases/tag/v0.1.0a1
