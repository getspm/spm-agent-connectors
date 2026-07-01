# Publishing Checklist

Use this repository when submitting SPM to MCP directories and agent-tooling
catalogs.

## Public Listing Text

SPM turns project knowledge into scoped, temporal, verifiable and injectable
context for AI agents.

## Endpoint

```text
https://getspm.com/v1/mcp
```

## Authentication

- Bearer token.
- Token generated or approved in SPM.
- Project-scoped.
- Trial or paid plan required.

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
- Setup: https://getspm.com/mcp
- Docs: https://getspm.com/docs
- Security: https://getspm.com/security
- Demo: https://getspm.com/sales/spm-current-scoped-trusted-agent-memory.mp4
