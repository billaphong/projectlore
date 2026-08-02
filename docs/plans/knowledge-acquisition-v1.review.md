# Detached review attestation — knowledge acquisition plan 1.0.0

- Plan: `docs/plans/knowledge-acquisition-v1.md`
- Package ID: `projectlore-knowledge-acquisition`
- Version: `1.0.0`
- Plan SHA-256: `9cd6821a0578c4b24d6748966d94942c9ad4b3e08bbbd4cae9abbe39cf09fca0`
- Repository baseline: `7354658a7e1424f18fdc5228e942371a781dc8af`
- Included tracked-diff identity: Git object `47168b837b2b31b6172fb2c45fe764b511ea5acc`
- Included untracked onboarding guide SHA-256: `9ade467009b462bf98680de9672a8d5ea96932c55a1e3d3f16ef300a257ae4ce`
- Grader: independent sub-agent `/root/knowledge_plan_grader`
- Timestamp: `2026-08-01T16:28:48.3231493-05:00`
- Clean-context declaration: the grader was distinct from the author, received
  no desired score or defense, independently reconstructed the plan against
  pinned authority and current read-only source, and changed no file.

## Scorecard

| Dimension | Score |
| --- | ---: |
| Authority and requirement fidelity | 14/15 |
| Repository and architecture grounding | 19/20 |
| Requirement/risk coverage and traceability | 12/15 |
| Phase coherence and dependency order | 10/15 |
| Verification and acceptance evidence | 11/15 |
| Failure, rollback, migration, and operational safety | 6/10 |
| Executability, precision, and scope discipline | 6/10 |
| **Total** | **78/100** |

## Findings

### KA-REV-001 — High — multi-file activation is not atomic

Affected R06, K03, K07, K14 and Phase 3. `loader.py:151-166` recursively
loads independent index/fragment files, while `refresh.py:29-61` can read
between separate replacements. Writing a fragment, then index, then root/model
version permits a supported reader to observe a new index with the old root.
Correction required: choose one atomic activation boundary, such as immutable
unreferenced fragments and index followed by one atomic root replacement that
changes both index reference and model version. Deduction: 8.

### KA-REV-002 — High — MCP 0.4 preservation conflicts with global 0.5

Affected R14, K09 and Phase 5. `tool_spec.py:7` has one global 0.4 version;
`query.py:13-52` incorporates that version and the complete schema map into
every existing response. Adding tools to the same contract changes existing
envelopes/digests, contradicting shape-identical preservation. Correction
required: choose a separate acquisition contract/server or explicitly authorize
the envelope change. Deduction: 7.

### KA-REV-003 — Medium — excerpt privacy boundary is unprovable

Affected R13, R15, K02 and Phases 1, 2, 4. “Explicitly public text” is undefined,
and Git tracking or secret-pattern canaries cannot prove a file contains no
credential. Correction required: define exact excerpt eligibility and
fail-closed redaction, or default packets to path/hash metadata without source
content and narrow the proof claim. Deduction: 3.

### KA-REV-004 — Medium — baseline review transition is missing

Affected R01, R06, R11 and Phase 2. Phase 2 claims a `reviewed` state and reaches
apply without defining a review operation/receipt; the shared review workflow
does not appear until Phase 3. Correction required: define the digest-bound
review transition in Phase 1/2 and reuse it later. Deduction: 2.

### KA-REV-005 — High — artifact package is incomplete

Hard gate 10 failed because only the plan existed at review time. Correction
required: preserve this detached review and create a non-self-digested manifest
with raw-byte plan/review hashes and durable delivery. Deduction: 2.

Finding disposition at this review: all five Open. Finding counts: 0 Critical,
3 High, 2 Medium, 0 Low.

## Attempted counterexamples that did not become findings

The grader reproduced all plan/source/worktree/user-direction identities;
confirmed accepted fragments outside `.projectlore/` can be canonical;
confirmed nested explicit includes are supported; confirmed Stop-time Git scans
can detect Bash edits; found no proposed write-capable MCP operation; confirmed
removal preserves accepted knowledge; confirmed provider-free evidence; found
the local rejection-memory limitation disclosed; confirmed external client
drift is rechecked; and confirmed the plan grants no publication authority.

## Hard gates

| Gate | Result | Basis |
| --- | --- | --- |
| 1 | Pass | Authority, baseline, worktree, and plan identity reproduced. |
| 2 | Fail | Atomic activation and MCP versioning conflicts remain. |
| 3 | Pass | R01-R20 and K01-K18 reconcile numerically. |
| 4 | Fail | Phase 3 activation and Phase 2 review are incoherent. |
| 5 | Fail | MCP and absolute secret-capture proof claims cannot pass. |
| 6 | Fail | Multi-file visibility and excerpt handling are unresolved. |
| 7 | Fail | Implementer must invent three material mechanisms. |
| 8 | Pass | Distinct clean-context grader. |
| 9 | Pass | No premature human escalation. |
| 10 | Fail | Review and manifest were absent at review time. |

Verdict: **Not ready**. Exact plan score 78/100; 4 gates Pass, 6 Fail.
