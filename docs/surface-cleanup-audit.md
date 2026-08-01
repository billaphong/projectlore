# Public-surface cleanup audit

The repository sweep identified three functions without current production
callers: `invoke_authoritative_check`, `diagnostics_payload`, and
`clear_workflow_target`. Repository-call absence is not sufficient evidence
that an alpha package consumer does not import them, and the package does not
yet publish a formal export manifest. They therefore remain available in this
release.

`build_workflow_provider` was previously test-only. It is now part of the
production composition path through `resolve_workflow_observation`, which is
used by MCP policy evaluation, retained pilot evaluation, and external scope
refresh. This establishes one authority without removing compatibility types.

The CLI remains a large dispatcher. Splitting it before golden stdout, stderr,
exit-code, and payload fixtures exist for every command family would create
more compatibility risk than demonstrated maintenance benefit. Handler
extraction is deferred until those fixtures exist and must be behavior-only;
it may not change schemas or payloads in the same change.
