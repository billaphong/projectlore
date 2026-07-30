# Contributing to ProjectLore

ProjectLore is in alpha. Discuss schema, MCP-contract, trust-boundary, or
packaging changes before investing in a large patch.

## Development

Use Python 3.11 or newer:

```shell
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m mypy src/projectlore
python -m projectlore.cli schema schemas/projectlore.schema.json --check
```

Every behavior change requires tests. Schema changes require regenerated schema,
valid checked-in examples, migration notes, and a versioning decision. Do not
weaken validation or enforcement claims to obtain a pass.

## Pull requests

- Keep changes bounded and explain user-visible behavior and trust impact.
- Preserve Git-tracked YAML as canonical authority.
- Never commit secrets, private model content, `.projectlore/`, indexes, caches,
  or virtual environments.
- Include exact verification commands and results.
- Do not publish packages or create releases from a pull request.

By contributing, you affirm that you have the right to submit the contribution.
The repository owner must select and publish the project license before accepting
external redistribution terms.
