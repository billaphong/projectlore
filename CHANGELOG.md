# Changelog

ProjectLore follows Keep a Changelog and Semantic Versioning. Dates use UTC.

## [Unreleased]

### Added

- Fail-closed publication manifests binding an authorized release tag to its
  exact commit, version, filenames, and artifact hashes.
- Preview-first `lore init` for a minimal canonical model, managed agent
  instructions, and cross-platform Claude Code and Codex CLI MCP/hook entries.
- Installed-wheel fresh-repository acceptance covering real MCP stdio transport,
  hook allow/block behavior, valid refresh, and malformed-edit last-known-good
  recovery.
- Strict project-local declarative policy bindings for deterministic string,
  decimal, and timestamp checks without granting executable authority.
- Bounded Python AST source-fact bindings that evaluate configured ordinary
  Write, Edit, and apply-patch actions through the same policy gate.
- Explicit non-secret Fraimed scope targets with atomic HTTPS refresh and
  generated Claude Code and Codex CLI SessionStart hooks.
- A deterministic checked-out source gate with bounded local or CI evidence,
  provenance, honest scope receipts, and explicit non-certification.
- Provider-neutral optional workflow scope: timeless policy runs offline,
  workflow-dependent bindings opt in explicitly, and a built-in local provider
  requires no hosted account or network.
- A public installation, trust-review, troubleshooting, and removal guide.

### Fixed

- Corrected pre-publication installation guidance so the unpublished
  `0.1.0a2` candidate is installed from a verified local wheel rather than
  falsely appearing available from a package index.
- Read-only MCP tools now start without Fraimed credentials. Scope-dependent
  policy checks explicitly degrade to `dependency_unavailable`.
- Hardened `lore doctor` to parse generated native configuration, execute the
  installed MCP and hook entrypoints, and reserve healthy/ready status for
  reviewed client trust.

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

[Unreleased]: https://github.com/billaphong/projectlore/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/billaphong/projectlore/releases/tag/v0.1.0a1
