# Security Policy

This repository contains only SPM connector assets. It must not contain SPM core
source code, production secrets, customer data, billing internals or private
infrastructure configuration.

## Token Handling

- Never commit bearer tokens, API keys or `.env` files with real values.
- Use `SPM_CODEX_MCP_TOKEN` or equivalent client-side secret storage.
- Use tokens explicitly scoped to one project, a selected project set or an
  authorized organization user.
- Revoke tokens from SPM when an agent, laptop or workspace should lose access.

## Agent Boundary

The SPM MCP connector is designed for project-memory work. It intentionally does
not expose billing, checkout, invoice payment, customer portal creation,
destructive tenant administration or raw secret-return tools.

If an agent receives an authorization, quota, scope or policy error, it should
surface that error to the user instead of retrying destructively.

## Reporting Issues

Report security concerns privately through the contact channel listed at:

```text
https://getspm.com/security
```

Do not disclose vulnerabilities publicly before coordinated review.
