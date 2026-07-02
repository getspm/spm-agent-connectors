# SPM Agent Connectors

Public connector package for SPM - Structured Project Memory.

SPM turns project knowledge into scoped, temporal, verifiable and injectable
context for AI agents. This repository contains only the public connector
surface: MCP configuration, Codex plugin metadata, setup scripts, examples and
security guidance.

The SPM application, backend, billing system, private console, memory engine and
infrastructure are not included in this repository.

## Hosted MCP Endpoint

Human setup and inspection guide:

```text
https://getspm.com/agents
```

```text
https://getspm.com/v1/mcp
```

Official MCP Registry descriptor:

```text
server.json
```

Registry name:

```text
io.github.getspm/spm
```

The endpoint is public for discovery, but authenticated for use. A client needs:

- an SPM account;
- an organization and project;
- a trial or paid plan;
- a project-scoped SPM token.

## What Agents Can Do

Connector profiles expose the agent-facing SPM surface:

- query temporal project memory;
- request scoped context packs;
- verify context pack provenance and hashes;
- query context graphs and boundaries;
- run policy-aware preflight checks;
- report completed actions, tests, evidence and decisions.

## What Agents Cannot Do

The hosted MCP connector does not expose:

- billing or checkout;
- invoice payment;
- customer portal creation;
- destructive tenant administration;
- raw secrets;
- global operator tools.

This boundary is intentional. Agents receive the memory tools they need without
being given commercial or destructive administrative powers.

## Codex

Install the Codex plugin from this repository marketplace:

```text
.agents/plugins/marketplace.json
```

Or configure Codex manually:

```toml
[mcp_servers.spm]
url = "https://getspm.com/v1/mcp"
bearer_token_env_var = "SPM_CODEX_MCP_TOKEN"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

Authorize a project-scoped token:

```bash
python3 plugins/spm-codex/scripts/auth_spm_codex.py --project-id <project-id> --write-env ~/.spm/codex.env
source ~/.spm/codex.env
```

Verify:

```bash
python3 plugins/spm-codex/scripts/doctor_spm_codex.py
```

Run the functional remote MCP smoke:

```bash
python3 plugins/spm-codex/scripts/smoke_spm_remote_mcp.py
```

The smoke uses the same `SPM_CODEX_MCP_TOKEN` as Codex. It initializes the
hosted MCP endpoint, verifies the exposed tool surface, creates a small
project-scoped smoke memory event, reads temporal state, creates and verifies a
context pack, queries the context graph, runs agent preflight and reports
post-action evidence. It never prints the token and the hosted connector strips
raw event bodies from returned context.

For a non-mutating token check, use:

```bash
python3 plugins/spm-codex/scripts/smoke_spm_remote_mcp.py --read-only
```

## Other MCP Clients

Use the same endpoint with a project-scoped bearer token. See:

- `examples/codex/config.toml`
- `examples/claude-desktop/claude_desktop_config.json`
- `examples/cursor/mcp.json`
- `examples/windsurf/mcp_config.json`

## Security

Do not commit tokens. Prefer environment variables or each agent client's
secret storage. Tokens should be project-scoped and revocable from SPM.

See `SECURITY.md` and `docs/security-boundary.md`.

## Links

- Website: https://getspm.com
- Agent integration guide: https://getspm.com/agents
- MCP setup: https://getspm.com/mcp
- Docs: https://getspm.com/docs
- Security: https://getspm.com/security
- Demo: https://getspm.com/sales/spm-current-scoped-trusted-agent-memory.mp4
- Directory listing pack: docs/directory-listing-pack.md
