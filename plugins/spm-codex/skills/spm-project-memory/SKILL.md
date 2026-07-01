---
name: spm-project-memory
description: Use SPM as durable project memory when Codex work involves requirements, architecture, testing, security, deployment, billing, privacy, context packs, temporal tension, agent handoff, governed sharing or post-action evidence.
---

# SPM Project Memory for Codex

Use the `spm` MCP server as the durable project-memory authority for consequential Codex work. The hosted connector is project-scoped and exposes SPM memory and hardening tools without billing, checkout or destructive admin operations.

## Operating Loop

1. Before consequential work, call `spm_temporal_state` or `spm_temporal_context_pack` to understand current project memory for the active topic, context area and task.
2. If the task touches architecture, tests, security, auth, data, deployment, billing, customer-facing copy, external sharing or policy, call `spm_agent_preflight` before editing or executing.
3. When the user provides durable project information, record a concise temporal event with `spm_temporal_event_create` only if the token has write scope and the information should survive the chat.
4. For handoff or injection into another agent, call `spm_temporal_context_pack` or `spm_context_boundary_pack`, then verify the returned pack with `spm_temporal_context_pack_verify` before relying on it.
5. After meaningful work, call `spm_agent_action_report` with changed files, tests, decisions, pack hashes and evidence references.

## What To Preserve

- Requirements, constraints, architecture decisions and acceptance criteria.
- Temporal layers: original intent, working state, current truth and history.
- Context areas or audience boundaries such as backend, partner, support, legal, operator or customer.
- Source, actor role, authority, confidence, hashes and evidence references.
- Tests run, approvals, policy checks and deviations.

## What Not To Store

Do not store secrets or raw sensitive data in SPM.

- Secrets, raw credentials, private tokens or full personal data.
- Private pricing, customer-sensitive details or unnecessary message bodies.
- Incidental chatter that has no durable project value.

Prefer summaries, hashes, source references and redacted evidence. If SPM reports temporal tension, authority conflict, expired context or approval requirements, surface that to the user instead of silently choosing one memory.

## Hosted MCP Tools

The hosted `agent-core` connector currently exposes these core tools:

- `spm_temporal_state`
- `spm_temporal_event_create`
- `spm_temporal_context_pack`
- `spm_temporal_context_pack_verify`
- `spm_temporal_graph_query`
- `spm_context_boundaries_list`
- `spm_context_boundary_get`
- `spm_context_boundary_pack`
- `spm_agent_preflight`
- `spm_agent_policy_pack`
- `spm_agent_action_report`

If the MCP server is unavailable, say so explicitly and continue without claiming that SPM has recorded or verified the work.
