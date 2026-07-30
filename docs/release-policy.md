# Release and packaging policy

## Alpha artifact

`0.1.0a2` is a prepared release candidate, not an authorized package-index
publication. Build from a clean, annotated commit using Python 3.11 or newer:

```shell
python -m build
python scripts/verify_distribution.py dist
python scripts/offline_smoke.py dist examples/contracts/portable.valid.yaml \
  schemas/projectlore.schema.json
```

The wheel contains only the typed `projectlore` package and distribution
metadata. The source distribution allow-list contains the package, build
metadata, public policies/docs, generated schema, and the synthetic portable
example. Homebrew, Sienna, Fraimed evidence, client-local configuration, hooks,
trust receipts, caches, and `.projectlore/` state are excluded.

Builds are validated on Windows, Linux, and macOS with Python 3.11 and 3.13. The
offline smoke step first prepares a wheelhouse, then creates a new environment
and installs exclusively with `--no-index`.

## Publication gate

Building, testing, committing, and attaching an artifact to CI do not authorize
publication. Publishing to PyPI, creating a GitHub Release, signing a tag, or
promoting an alpha requires a separate explicit owner instruction after:

1. all CI matrix jobs pass for the exact commit;
2. distribution inspection passes;
3. the owner selects and records a distribution license;
4. package name and version availability are checked immediately before upload;
5. hashes and generated schema are recorded.

The owner selected Apache-2.0 and authorized publication of `0.1.0a1` on
2026-07-30. The subsequent product-readiness audit held that version off package
indexes. `0.1.0a2` and later versions still require their own explicit release
authorization.

## Reproducibility

Archive byte identity is not claimed because standard Python metadata may include
build timestamps. Reproducibility means the same clean source commit yields the
same allow-listed file set, version, generated schema, and passing smoke behavior.
