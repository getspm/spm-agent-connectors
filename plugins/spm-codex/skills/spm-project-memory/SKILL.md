---
name: spm-project-memory
description: Use SPM as durable project memory when Codex work involves requirements, architecture, testing, security, deployment, billing, privacy, context packs, temporal tension, agent handoff, governed sharing or post-action evidence.
---

# SPM Project Memory for Codex

Use the `spm` MCP server as the durable project-memory authority for consequential Codex work. The hosted connector defaults to the active project boundary, supports explicit project resolution and cross-project context packs when the user asks for them, and exposes SPM memory and hardening tools without billing, checkout or destructive admin operations.

## Operating Loop

1. At task start, use `spm_agent_session_start` or the bundled lifecycle hook to establish one active project and inspect the authorized project catalog. If SPM returns `bootstrap_required`, call `spm_project_bootstrap_preview` with source-grounded context from the task and present its confirmation URL. The user chooses create, link or skip; never create project memory silently. For ordinary ambiguity among existing projects, ask the user instead of writing memory.
2. Call `spm_temporal_state` or `spm_temporal_context_pack` to understand current project memory for the active topic, context area and task.
3. Surface `attention_briefing` returned at session start before continuing with the user's first request. Display is not acknowledgement; call `spm_attention_state_update` only after an explicit user instruction.
4. If the task touches architecture, tests, security, auth, data, deployment, billing, customer-facing copy, external sharing or policy, call `spm_agent_preflight` before editing or executing.
5. Let the lifecycle hook submit user and assistant turns to `spm_agent_turn_ingest`. SPM applies the effective session/project/org capture policy before LLM-first triage decides what to store, update, relate, temporalize, promote or discard. Use `spm_memory_capture_policy_get` to inspect that policy and `spm_temporal_event_create` only for deliberate operator-authored events.
6. For handoff or injection into another agent, call `spm_temporal_context_pack` or `spm_context_boundary_pack`, then verify the returned pack with `spm_temporal_context_pack_verify` before relying on it.
7. For one external project, call `spm_cross_project_context_pack`; for several explicit sources, call `spm_multi_project_context_pack`. Do not pull memory from another project merely because it is available. Multi-project composition must preserve each source pack and hash instead of flattening memories.
8. After meaningful work, call `spm_agent_action_report` with changed files, tests, decisions, pack hashes and evidence references.

## Project Boundary Rules

- Default to the active project. Do not guess a different project from repository names, filenames or loose string matches.
- Use SPM's project resolver for ambiguous natural-language references, and surface unresolved ambiguity instead of silently mixing memories.
- Cross-project context is opt-in per task. The user can ask for another project, a comparison, a handoff or an injected context pack; otherwise keep recall project-local.
- If a token is project-scoped, respect that scope and do not imply organization-wide access.
- If a token is organization-scoped, the connector still defaults to active-project-only behavior and uses cross-project tools only when explicitly requested.

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

- `spm_agent_action_report`
- `spm_agent_session_get`
- `spm_agent_session_set_project`
- `spm_agent_session_start`
- `spm_attention_briefing`
- `spm_attention_inbox`
- `spm_attention_sent`
- `spm_attention_create`
- `spm_attention_state_update`
- `spm_attention_revoke`
- `spm_agent_turn_ingest`
- `spm_memory_capture_policy_get`
- `spm_memory_capture_policy_set`
- `spm_memory_capture_journal_list`
- `spm_memory_capture_journal_verify`
- `spm_agent_policy_pack`
- `spm_agent_preflight`
- `spm_context_boundaries_list`
- `spm_context_boundary_get`
- `spm_context_boundary_pack`
- `spm_cross_project_context_pack`
- `spm_multi_project_context_pack`
- `spm_project_resolve`
- `spm_project_bootstrap_preview`
- `spm_project_bootstrap_status`
- `spm_projects_list`
- `spm_temporal_context_pack`
- `spm_temporal_context_pack_verify`
- `spm_temporal_event_create`
- `spm_temporal_graph_query`
- `spm_temporal_state`
- `spm_trust_remediation_plan`
- `spm_trust_status`

If the MCP server is unavailable, say so explicitly and continue without claiming that SPM has recorded or verified the work.
