# ProjectLore knowledge-acquisition contract 0.6.1

This is the promoted standalone technical contract. Release acceptance remains
unbound until its required evidence is complete. No earlier proposed package is
normatively imported. Git-tracked ProjectLore YAML is the sole canonical
project knowledge; acquisition objects are immutable evidence until an explicit
digest-bound `accept` review is applied through the shared canonical transaction.
Reads and hooks never promote or mutate canonical knowledge.

Normative artifacts are the complete `schemas.json`, digest and migration
registries, semantic validator, MCP registry/fixtures, hook and fault contracts,
platform renderer, removal contract, package proof, decision ledger, and 27-row
mapping in this directory. Unknown fields and unsupported versions fail closed.

All JSON identity uses RFC 8785 JCS UTF-8 and the per-object domain/exclusion
registry. Set-like arrays are unique and ascending by UTF-8 or JCS bytes;
sequence arrays are explicitly named. Paths are NFC, root-relative, `/`-only,
1..1024 UTF-8 bytes, symlink-free and physically confined. Timestamps receive
real proleptic-Gregorian parsing and require UTC `Z`.

Implementation note: the promoted contract excludes both `root_digest` and
`generation_id` from root identity. The reviewed proposal excluded only
`root_digest`, which formed an uncomputable cycle because generation identity
also binds `root_digest`. Root identity therefore binds the ordered member set;
generation identity binds that root plus sequence and state.

Candidate wheel/dependency/corpus/client hashes are candidate evidence rather
than fictional pre-build constants. The proposal begins `unbound`; acceptance
is forbidden until the package-proof readiness machine reaches `verified` with
both real clients successful. Indeterminate is non-pass.
