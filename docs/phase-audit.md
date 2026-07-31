# Full-phase product audit

Audit date: 2026-07-30
Candidate baseline: `0.1.0a2` at `89158db`
Status: corrected candidate; package-index publication remains unauthorized

This audit maps the accepted v2 plan to the current product and executable
evidence. It combines a primary implementation pass with a read-only independent
verification pass.

| Phase | Current evidence | Audit result |
| --- | --- | --- |
| 0 — Product boundary | `AGENTS.md`, architecture, accepted v2 plan, Fraimed project structure | Pass after correcting the plan's stale “pending acceptance” label |
| 1 — Homebrew walking skeleton | Homebrew model, corpus, MCP/policy/hook tests, pilot proof | Pass |
| 2 — Contracts and compiler | Strict models, bounded loader, semantic validator, generated schema, hostile fixtures | Pass |
| 3 — Query, policy, MCP, clients | Eight MCP tools, CLI parity, capability matrix, managed integration, doctor | Pass after replacing marker-only doctor checks with parsed configuration and installed-entrypoint probes |
| 4 — Security and interactive enforcement | Normalized events, trusted checker registry, sandbox/fail-closed behavior, injection and timeout tests | Pass within documented platform limits |
| 5 — Repository assurance | Changed-file impact, delegated checkers, evidence states, protected-gate verifier | Pass; local and ordinary CI remain honestly bypassable |
| 6 — Adapters and second pilot | Optional CodeGraph adapter, Homebrew and Sienna pilots | Pass |
| 7 — Refresh and measured scale | Request-driven atomic refresh, last-valid snapshot, recorded scale/UI decisions | Pass by accepted evidence-based deferral: measurements did not justify SQLite, embeddings, graph storage, a watcher, or a dedicated UI |
| 8 — Public alpha preparation | Cross-platform matrix, package allow-list, offline wheel smoke, policies/docs/SDK | Candidate pass; publication is deliberately not part of this result |

## Corrected findings

1. Documentation advertised a package-index install for an unpublished version.
   It now directs candidate testers to the verified local wheel and states the
   separate publication condition.
2. Publication workflows allowed tags other than `v0.1.0a1` to bypass artifact
   hashes. They now reject any tag without a committed release manifest and bind
   the tag to its exact commit, version, filenames, embedded metadata, and
   SHA-256 hashes.
3. `lore doctor` used marker strings and internal probes. It now parses the
   generated JSON/TOML structures, launches the installed MCP entrypoint over
   stdio, launches the installed hook entrypoint, and reserves healthy/ready for
   verified client trust.
4. README-linked pilot, scale, and UI documents were missing from the source
   distribution. They are now included and enforced by the distribution
   allow-list.
5. The plan-of-record status contradicted the owner's accepted v2 decision. Its
   status now records acceptance.

## Remaining external release control

The repository's workflow now fails closed on unrecognized or mismatched
artifacts. GitHub environment reviewer and administrator-bypass settings are
hosted repository controls, not source-controlled ProjectLore behavior. At audit
time, the `pypi` environment had no protection rules and allowed administrator
bypass, and a protected `testpypi` environment did not exist. Publication must
remain blocked until the owner selects reviewers and configures those hosted
controls, or explicitly accepts that residual release-operator risk.

No `0.1.0a2` tag, GitHub Release, TestPyPI upload, or PyPI upload was created by
this audit.
