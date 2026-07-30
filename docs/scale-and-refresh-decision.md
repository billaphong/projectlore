# Scale and refresh decision

Decision: add validated request-driven refresh; defer SQLite/FTS, a background
watcher, embeddings, and graph storage.

## Evidence

The retained Homebrew pilot measured 0.108 ms p95 query/policy latency and
3,254-byte p95 context. The retained Sienna pilot measured 0.159 ms and 5,957
bytes. Both are far below the pre-registered 100 ms and 16 KiB budgets. The
canonical models are also small: Sienna is 158 lines. There is no measured
performance, memory, or corpus-size case for a database projection.

The correction-rediscovery proof did reveal a lifecycle requirement. Canonical
Git edits must become visible to a long-lived MCP process, and a malformed edit
must not take the previously valid model away from agents. This is a refresh and
activation problem, not a search-index problem.

## Bounded implementation

`RefreshingModelService` validates canonical files at each MCP request boundary.
A valid candidate atomically becomes active. An invalid candidate leaves the
last valid immutable `ModelService` active and adds localized diagnostics plus a
`last_valid` refresh state to every response. `model_validate` reports the
candidate invalid while other reads continue against the disclosed last-valid
snapshot.

This polling design requires no background thread, filesystem-specific watcher,
cache invalidation protocol, generated state, or new dependency. Existing loader
file, byte, node, and depth bounds apply to every attempt. A process still fails
at startup when no valid initial model exists; last-valid behavior cannot invent
an initial authority.

## Reconsideration triggers

Reconsider SQLite/FTS only with retained evidence showing at least one of:

- representative warm-query p95 exceeds 100 ms;
- representative task context or corpus growth makes bounded in-memory scans a
  demonstrated bottleneck;
- repeated full validation consumes a measured material share of agent request
  latency;
- a supported use case requires durable disposable projections across process
  restarts.

Any future projection must remain under `.projectlore/`, pass the same repository
contract suite as in-memory operation, rebuild transactionally, and remain
disposable. Embeddings and graph databases require a separate decision.
