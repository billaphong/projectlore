# Workflow contract compatibility

This document freezes the workflow-related public contract at the Phase 1
baseline (`89158db3fa2a69f5597a745b05499033a46a503b`). It is an inventory and
migration policy, not authorization to change a payload in place.

## Version inventory

| Surface | Current identifier | Phase 1 classification | Compatibility decision |
| --- | --- | --- | --- |
| Canonical model | `schema_version` (`0.x` currently accepted) | Independent schema contract | Continue explicit model migrations; reads never rewrite canonical YAML. |
| MCP tools and envelopes | `projectlore-tools/0.4.0` | Current provider-neutral public tool contract | One normative ToolSpec is checked against all runtime MCP schemas; `context_for_task.limit` is consistently exposed. |
| MCP tools and envelopes | `projectlore-tools/0.2.0` | Frozen compatibility contract | The former caller-selected workflow identity is not accepted by 0.3. |
| `ScopeSnapshot` | Unversioned; `frame_*` fields | Legacy public payload | Freeze with a golden fixture. A provider-neutral replacement is breaking and must have an explicit version and migration path. |
| `ScopeReceipt` | `scope-receipt/0.1.0` | Public evidence payload | Continue reading the golden Fraimed-shaped receipt until a documented major-version removal. Additive readers may normalize it internally. |
| `ScopeTarget` | `scope-target/0.1.0` | Local persisted configuration | Migrate explicitly; the next format adds canonical model identity and a root-relative model entrypoint. Never guess when discovery is ambiguous. |
| `PolicyRequest` | Unversioned inside tool `0.2.0` | Tool-contract payload | The tool version governs compatibility. Provider/assurance changes require a tool-contract increment. |
| `PolicyResult` | Unversioned inside tool `0.2.0` | Tool-contract payload | Preserve legacy optional `scope_receipt`; new assurance/result semantics require a tool-contract increment. |
| Source-gate evidence | `projectlore-source-gate/0.1.0` | Persisted evidence | Any new required identity, assurance, or target-binding field requires a new evidence version. |
| Repository gate evidence | `projectlore-gate-evidence/0.1.0` | Frozen legacy evidence | Readable for compatibility but unbound, unauthenticated, and never assurance-promoting. |
| Repository gate evidence | `projectlore-gate-evidence/1.0.0` | Current self-consistent evidence | Binds normalized impact selection, plans, and bounded executions. Imported evidence is not authenticated local or hosted provenance and cannot promote assurance by itself. |
| Agent lifecycle event | `projectlore-agent-event/0.1.0` | Client integration contract | Provider-neutral lifecycle changes must retain an adapter or increment this contract. |
| Policy registry | Unversioned bounded JSON | Operator-authored configuration | A versioned registry envelope is required before changing binding meaning or required fields. |
| Canonical workflow target | `projectlore-workflow-target/1.0.0` | Provider-neutral persisted identity contract | Binds canonical project ID, root-relative model entrypoint, provider, scope, and optional container. It does not reinterpret `scope-target/0.1.0`. |
| Canonical workflow observation | `projectlore-workflow-observation/1.0.0` | Provider-neutral context contract | Repeats target identity, target digest, content digest, timestamps, and immutable declared/observed assurance. |
| Canonical workflow receipt | `projectlore-workflow-receipt/1.0.0` | Provider-neutral evidence contract | Binds target, observation, model digest, assurance, and evaluation freshness. Legacy receipt conversion is explicit. |
| Canonical policy plan | `projectlore-policy-plan/1.0.0` | Immutable evaluation contract | Freezes facts, binding snapshots, context requirements, model/registry/target identity, and complete-plan digest before provider resolution. |

Other receipts and observations are independently versioned as documented in
`versioning-and-migrations.md`; they are outside the workflow naming migration
unless their semantics change.

## Compatibility matrix

| Producer | Reader | Required Phase 1 behavior |
| --- | --- | --- |
| `ScopeSnapshot` legacy Fraimed payload | Current `ScopeSnapshot` | Load without loss and emit the same JSON values. |
| `scope-receipt/0.1.0` | Current `ScopeReceipt` | Load without loss, including `frame_id` and `fraimed_mcp`. |
| `scope-target/0.1.0` | Current `ScopeTarget` | Load without loss. A future migration must add canonical model ID and a root-relative model entrypoint. |
| Unknown `scope-target` version | Current `ScopeTarget` | Reject with a diagnostic naming `target_version`; never reinterpret it. |
| Unversioned policy request/result | Tool contract `0.2.0` | Load the frozen shapes. Their compatibility is coupled to the tool contract. |
| `projectlore-source-gate/0.1.0` | Current evidence reader | Load without loss. |

Legacy `frame_id`, `frame_title`, and `frame_status` fields and Fraimed receipt
values remain readable until a chosen major version explicitly removes them.
Writing a future canonical payload does not imply that legacy names remain the
canonical internal representation.

The provider-neutral `1.0.0` contracts are additive new contract families, not
new meanings assigned to `scope-target/0.1.0`, `scope-receipt/0.1.0`, or the
unversioned legacy snapshot. `projectlore.workflow_compat` is the only supported
normalization boundary between those families.
Legacy local snapshots migrate only through `lore scope migrate` followed by
the exact `--apply` operation. The migration is idempotent and refuses corrupt,
oversized, linked, mismatched, or external-provider state.

## Target identity and repository movement

The `scope-target/0.1.x` successor must bind both a canonical ProjectLore model
ID and a model entrypoint stored relative to the repository root. Loading must
resolve that entrypoint beneath the discovered root, verify the loaded model ID,
and reject path escape, identity mismatch, multiple candidate roots, or multiple
candidate model files. Moving or cloning the repository must remain valid when
the relative layout and canonical model ID are unchanged.

Golden payloads live in `tests/fixtures/contracts`. Tests prove lossless reads
for supported legacy data and a deterministic diagnostic for an unsupported
target version. Before any later phase changes one of these surfaces, its row
must name the new identifier and migration behavior.
