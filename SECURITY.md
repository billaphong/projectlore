# Security policy

## Supported versions

Only the latest `0.1.x` alpha is eligible for security fixes. Alpha compatibility
may change according to `docs/versioning-and-migrations.md`.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include credentials,
private project models, or exploit details in public artifacts. Use GitHub's
private vulnerability reporting for this repository. If that facility is
unavailable, contact the repository owner privately through their GitHub profile.

Include affected version, platform, reproduction steps, impact, and whether the
report involves canonical-model parsing, path confinement, hook enforcement,
checker execution, MCP transport, or credential exposure. You should receive an
acknowledgement within seven days; remediation timing depends on severity and
reproducibility.

## Security boundary

- Project YAML and external context are untrusted data.
- MCP reads never silently mutate canonical knowledge.
- Local hooks are bypassable and are not repository protection.
- Checker labels in model content cannot grant executable authority.
- Secrets belong in environment variables or client-owned credential stores.
- Generated state belongs under `.projectlore/` and is disposable.

ProjectLore makes no claim that an agent read, understood, or followed returned
context. See the architecture and release policy for the complete trust model.
