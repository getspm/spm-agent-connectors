# SPM Directory Listing Pack

Use this pack for MCP directories, hosted connector catalogs and agent tooling
marketplaces. The tone should stay direct, technical and commercially clear:
SPM is a project-memory layer for serious agent work, not a generic chatbot
memory plugin.

## Primary Positioning

SPM turns project knowledge into verified context that agents can query, inject,
share and trust.

## One-Line Description

Structured project memory for AI agents, delivered through a project-scoped
remote MCP connector.

## Short Description

SPM gives agents smart, temporal and verifiable project context through MCP,
with scoped context packs, source traceability, access control and post-action
evidence.

## Long Description

SPM is project memory infrastructure for AI agents and technical teams. It
structures project knowledge into temporal memory, context graphs and
hash-verifiable context packs that can be injected into Codex, Cursor, Claude,
custom runtimes and other MCP-capable agents.

Agents can retrieve the right project context for a task, verify what they
received, run policy-aware preflight checks before consequential actions and
report completed work back to project memory with tests, decisions and evidence.
Teams can scope context for different agents, collaborators, partners or support
flows without exposing billing, checkout, destructive administration or raw
secrets through the connector.

## Capability Order

Use this order when a directory allows bullets or feature fields:

1. Smart project memory that structures, summarizes, tags and relates project knowledge.
2. Temporal memory across original intent, working state, current truth and history.
3. Queryable context graphs, source traceability and item-level recall.
4. Scoped context packs for different agents, teams, partners or support flows.
5. MCP, CLI and API injection into agent workflows.
6. Access control, permissions, expirations, revocation and audit logs.
7. Provenance, hashes and verification for the context an agent receives.
8. Policy and hardening checks before consequential agent actions.

## Suggested Categories

- Developer Tools
- Coding Agents
- AI & Machine Learning
- RAG Systems
- Project Management
- Security

## Suggested Tags

- mcp
- agents
- project-memory
- agent-memory
- context-packs
- temporal-memory
- context-graph
- provenance
- verification
- access-control
- agent-governance
- developer-tools

## Public URLs

- Website: https://getspm.com
- Agent integration guide: https://getspm.com/agents
- Remote MCP endpoint: https://getspm.com/v1/mcp
- Official MCP Registry descriptor: server.json
- Official MCP Registry name: com.getspm/spm
- Static MCP server card: https://getspm.com/.well-known/mcp/server-card.json
- MCP setup: https://getspm.com/mcp
- Public docs: https://getspm.com/docs
- Security: https://getspm.com/security
- Demo video: https://getspm.com/sales/spm-current-scoped-trusted-agent-memory.mp4
- Public connector repository: https://github.com/getspm/spm-agent-connectors
- Public connector release: https://github.com/getspm/spm-agent-connectors/releases/tag/v0.1.1

## Smithery Fields

Name:

```text
SPM
```

Display name:

```text
SPM - Structured Project Memory
```

Server URL:

```text
https://getspm.com/v1/mcp
```

Homepage:

```text
https://getspm.com
```

Description:

```text
SPM turns project knowledge into verified context that agents can query, inject, share and trust. The connector exposes smart project memory, temporal state, context packs, graph query, preflight checks and post-action evidence through a project-scoped remote MCP endpoint.
```

Authentication note:

```text
SPM uses project-scoped bearer tokens created or approved inside the SPM workspace. Billing, checkout, invoice payment, customer portal and destructive administration tools are not exposed through the agent connector.
```

If Smithery cannot scan authenticated tools, use the static server card:

```text
https://getspm.com/.well-known/mcp/server-card.json
```

If a config schema is requested:

```json
{
  "type": "object",
  "required": ["spm_api_token"],
  "properties": {
    "spm_api_token": {
      "type": "string",
      "title": "SPM project token",
      "description": "A project-scoped SPM token created from the MCP setup console or browser-approved device flow.",
      "format": "password"
    }
  }
}
```

## Glama Fields

Submission type:

```text
Hosted MCP connector
```

Connector URL:

```text
https://getspm.com/v1/mcp
```

Repository:

```text
https://github.com/getspm/spm-agent-connectors
```

Description:

```text
SPM is structured project memory for AI agents. It provides smart temporal memory, queryable context graphs, scoped context packs, provenance, hash verification, access control and agent hardening checks through an authenticated remote MCP endpoint.
```

Reviewer note:

```text
The endpoint is public for discovery and authenticated for use. Public metadata and the static server card describe the tool surface; real tool calls require a project-scoped SPM token.
```

## Security Boundary

The public connector is intentionally narrower than the full SPM platform. It
does not expose billing, checkout, invoice payment, customer portal creation,
tenant deletion, destructive administration, raw secrets or cross-project access.

Agents receive project-memory tools only after authentication with a
project-scoped token. Returned context is summary and hash oriented; raw event
bodies are not exposed by the hosted connector.

## Quality Proof

Before updating a live listing, run:

```bash
python3 scripts/validate_public_connector.py
python3 plugins/spm-codex/scripts/doctor_spm_codex.py --metadata-only
```

For a full authenticated smoke, run:

```bash
SPM_CODEX_MCP_TOKEN="<project-scoped-token>" python3 plugins/spm-codex/scripts/smoke_spm_remote_mcp.py
```

The full smoke validates remote MCP initialization, tool discovery, temporal
event creation, temporal state recall, context pack generation, context pack
verification, context graph query, preflight and post-action reporting.
