# SPM Agent Connectors

Public connector package for SPM - Structured Project Memory.

SPM turns project knowledge into durable, shareable, governed and internally
smart project memory for AI agents. This repository contains only the public
connector surface: the authenticated remote MCP configuration, installable
bundles for Codex, Claude Code, Cursor and OpenClaw, browser authorization
helpers, lifecycle adapters, examples and security guidance.

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
com.getspm/spm
```

The endpoint is public for discovery, but authenticated for use. A client needs:

- an SPM account;
- an organization and at least one project;
- a trial or paid plan;
- an SPM token authorized for one project, a selected project set or the
  projects the user may access in an organization.

## What Agents Can Do

Connector profiles expose the agent-facing SPM surface:

- use durable project memory across chats, runs and tools;
- resolve the active project without confusing it with other authorized
  projects;
- list authorized projects and compose cross-project context only when the
  user explicitly requests it;
- work with smart memory packs that preserve requirements, current decisions,
  completed work, source-backed context and temporal signals;
- query temporal project memory;
- request scoped context packs;
- verify context pack provenance and hashes;
- query context graphs and boundaries;
- run policy-aware preflight checks;
- report completed actions, tests, evidence and decisions;
- submit agent lifecycle turns to LLM-first memory triage with source
  provenance, when the client supports lifecycle hooks.
- choose selective, complete redacted, summaries-only or metadata-only source
  capture independently from the memory that triage promotes for future use;
- inspect and verify an append-ordered capture journal without exposing retained
  conversation bodies to agent tools.
- propose a source-grounded project-memory bootstrap when no authorized project
  matches, then wait for the user to create, link or skip it in SPM.

## Typical Use Cases

- Coding agents receive the project memory they should actually use before
  changing code: requirements, current decisions, tests, constraints and
  completed work.
- Delivery teams turn scattered project knowledge into scoped packs for
  engineers, clients, partners or support without exposing the whole project.
- Partners or external collaborators receive bounded memory with source,
  expiry, revocation, provenance and audit evidence.
- Agent workflows preserve memory after the task by reporting decisions, tests
  and evidence back to SPM.

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

Authorize Codex for all projects the signed-in organization user may access:

```bash
python3 plugins/spm-codex/scripts/auth_spm_codex.py \
  --project-id <authorization-project-id> \
  --access-mode organization \
  --write-env ~/.spm/codex.env
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
hosted MCP endpoint, verifies the project-resolution, multi-project,
agent-session and memory tool surface, creates a small project-scoped smoke
memory event, reads temporal state, creates and verifies a context pack, queries
the context graph, runs agent preflight and reports post-action evidence. It
never prints the token and the hosted connector strips raw event bodies from
returned context.

For a non-mutating token check, use:

```bash
python3 plugins/spm-codex/scripts/smoke_spm_remote_mcp.py --read-only
```

## Claude Code, Cursor And OpenClaw

The repository includes native client bundles:

- `plugins/spm-claude`
- `plugins/spm-cursor`
- `plugins/spm-openclaw`

Clients that only support MCP can use the same remote endpoint and bearer
token. The generic authorization helper is
`scripts/agent-connectors/authorize_spm_agent.py`. See also:

- `examples/codex/config.toml`
- `examples/claude-desktop/claude_desktop_config.json`
- `examples/cursor/mcp.json`
- `examples/windsurf/mcp_config.json`

## Security

Do not commit tokens. Prefer environment variables or each agent client's
secret storage. Tokens must be explicitly scoped and revocable from SPM.
Organization visibility does not permit silent project mixing: each task keeps
one active project, while cross-project packs require an explicit user request.

See `SECURITY.md` and `docs/security-boundary.md`.

## Links

- Website: https://getspm.com
- Agent integration guide: https://getspm.com/agents
- MCP setup: https://getspm.com/mcp
- Docs: https://getspm.com/docs
- Security: https://getspm.com/security
- Demo: https://getspm.com/sales/spm-current-scoped-trusted-agent-memory.mp4
- Directory listing pack: docs/directory-listing-pack.md
