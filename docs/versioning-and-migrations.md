# Versioning and migrations

ProjectLore versions the Python distribution, canonical model schema, MCP tool
contract, integration manifest, observations, receipts, and client capability
matrix independently.

## Distribution

The package follows Semantic Versioning. Before `1.0.0`, a minor release may
contain a documented breaking API change; patch releases remain
backward-compatible bug and security fixes. Pre-release identifiers such as
`0.1.0a1` are not stable production commitments.

## Canonical models

`schema_version` governs accepted canonical structure. Readers reject unsupported
major versions. Additive fields normally increment the minor version; incompatible
meaning or required structure increments the major version. `model_version`
belongs to the project model and advances whenever accepted project meaning
changes.

Migrations are explicit, deterministic, reviewable transformations between known
schema versions. ProjectLore does not silently rewrite canonical files during a
read or validation. A migration must preserve provenance, emit diagnostics for
unrepresentable content, include before/after fixtures, and require an explicit
write command. No migration command ships in `0.1.0a1`.

## Tool and extension contracts

The MCP `contract_version` changes when tool names, arguments, result states, or
required envelope fields change. Extension observation and execution payloads
carry their own literal version. Consumers must reject unsupported major versions
and tolerate documented additive fields within a compatible version.

Every release records migrations and compatibility changes in `CHANGELOG.md`.
