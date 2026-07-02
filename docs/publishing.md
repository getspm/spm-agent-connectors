# Publishing Checklist

Use this repository when submitting SPM to MCP directories and agent-tooling
catalogs.

## Public Listing Text

Use `docs/directory-listing-pack.md` as the canonical public copy source. It is
written for external MCP directory reviewers, integration partners and agent
builders.

Short listing text:

```text
SPM turns project knowledge into verified context that agents can query, inject, share and trust.
```

## Endpoint

Human setup and inspection guide:

```text
https://getspm.com/agents
```

```text
https://getspm.com/v1/mcp
```

## Authentication

- Bearer token.
- Token generated or approved in SPM.
- Project-scoped.
- Trial or paid plan required.

## Directory Strategy

Use the remote connector path first:

- Submit `https://getspm.com/v1/mcp` as the public HTTPS MCP endpoint.
- Use `https://getspm.com/agents` as the human inspection and setup URL.
- Use `https://github.com/getspm/spm-agent-connectors` as the public connector repository.
- Do not provide a private SPM project token to public scanners unless a
  temporary review token has been explicitly approved, scoped and scheduled for
  revocation.
- If a directory cannot scan authenticated tools, point it to the static server
  card at `https://getspm.com/.well-known/mcp/server-card.json`.

## Verification Gate

Before submitting or updating a directory listing, run:

```bash
python3 scripts/validate_public_connector.py
python3 plugins/spm-codex/scripts/doctor_spm_codex.py --metadata-only
python3 plugins/spm-codex/scripts/smoke_spm_remote_mcp.py
```

The first command verifies that this public repository remains connector-only.
The second checks public MCP discovery metadata without credentials. The third
requires a project-scoped `SPM_CODEX_MCP_TOKEN` and exercises real agent-facing
MCP calls: temporal state, context pack, verification, graph query, preflight
and post-action report.

## Suggested Tags

- mcp
- agents
- memory
- context
- project-memory
- temporal-memory
- governance
- verification
- provenance
- developer-tools

## Links

- Website: https://getspm.com
- Agent integration guide: https://getspm.com/agents
- Setup: https://getspm.com/mcp
- Docs: https://getspm.com/docs
- Security: https://getspm.com/security
- Demo: https://getspm.com/sales/spm-current-scoped-trusted-agent-memory.mp4
- Public connector repository: https://github.com/getspm/spm-agent-connectors
- Public connector release: https://github.com/getspm/spm-agent-connectors/releases/tag/v0.1.0
