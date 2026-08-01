# Relationship traversal benchmark

The 2026-07-31 sweep measured `QueryService.get_relationships` on a deterministic
1,200-concept directed ring, depth 5, limit 500, for 20 warm in-process runs on
Windows with Python 3.13.

Reproduce from the repository root with:

```shell
.venv/Scripts/python.exe scripts/benchmark_query_traversal.py
```

The script deterministically generates both corpora, implements the frozen
global scan as its reference, runs each path 20 times, prints raw medians and
ratios, and exits nonzero unless the large-corpus improvement is at least 30%
and the small-corpus median regression is at most 5%.

| implementation | median | minimum | maximum |
| --- | ---: | ---: | ---: |
| repeated global sort and scan | 1.662 ms | 1.620 ms | 2.897 ms |
| immutable incoming/outgoing/both index | 0.051 ms | 0.049 ms | 0.347 ms |

The indexed traversal improved the median by approximately 97%, exceeding the
30% adoption threshold. The index is rebuilt with each immutable
`QueryService` snapshot; canonical model files remain authoritative. Existing
query tests retain ordering, direction, depth, cycle, limit, truncation,
missing/empty, and provenance behavior. Token caching was not introduced.
