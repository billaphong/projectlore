# Release-candidate checklist

This repository is implementation-ready when the source gate, committed schema,
distribution inspection, fresh offline installation, removal tests, and pinned
security scans pass. Hosted release-candidate status remains owner-gated.

## Local evidence

- Full pytest, Ruff, strict mypy, schema drift, and diff hygiene
- Wheel/sdist build from a clean local commit
- Distribution allow-list inspection and fresh no-index installation
- Dependency, license, and static-security JSON reports using
  `docs/security/tool-manifest.json`
- Artifact SHA-256 and source commit recorded in the release manifest
- Generated integration removal preserves client-owned content

## Owner-gated evidence

- GitHub Actions matrix succeeds on Windows, Linux, and macOS with Python 3.11
  and 3.13
- Candidate commit and artifact hashes are confirmed from the hosted build
- Any non-low security finding is explicitly resolved or accepted by the owner
- Tag, GitHub Release, TestPyPI, or PyPI publication receives separate approval

No local result in this file claims hosted CI or publication.
