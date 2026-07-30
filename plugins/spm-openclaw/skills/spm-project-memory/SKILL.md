---
name: spm-project-memory
description: Use SPM for durable temporal memory, governed sharing, project resolution and context composition.
---

# SPM project memory

Use the SPM MCP tools naturally for durable project state, temporal reasoning,
explicit cross-project composition, context boundaries, verification, preflight and
post-action evidence. Inbound and successful outbound messages are triaged by the
installed lifecycle hook. Never mix projects implicitly and never store secrets.

Use `spm_agent_session_start` to resume project memory when the lifecycle hook has
not already done so, and `spm_agent_turn_ingest` only for explicit wrapper-driven
capture. Use `spm_agent_session_context_inject`,
`spm_agent_session_context_revoke`, `spm_cross_project_context_pack` and
`spm_multi_project_context_pack` only when the user explicitly asks for another
authorized project or a shared context pack. Use `spm_memory_capture_policy_get`,
`spm_memory_capture_evidence`, `spm_memory_context_compose`,
`spm_agent_session_receipt_delivery_report` and
`spm_agent_session_receipt_status` to inspect capture policy, compose governed
task context and inspect receipt state.

Surface pending project attention at session start. Treat delivery, surfacing,
acknowledgement and resolution as different states; never infer the latter two from display.

When the lifecycle returns a project-association `user_prompt`, ask it naturally
and map the user's ordinary-language answer to its structured reply options. For
`bootstrap_required`, ask whether to create a new project, show existing projects
or continue without persistent memory in SPM. Confirm, replace or skip a match through
`spm_agent_session_association_decide`. After the user explicitly chooses creation,
call `spm_project_bootstrap_execute` with the current lifecycle `session_id`,
that instruction, a safe authorized-resource inventory and source-grounded
evidence from a bounded inspection. Creation and task association are atomic:
never omit `session_id` or report success unless the returned session has the
new project active. Repeat the idempotent operation to resume the same bootstrap. If it returns
`evidence_required`, inspect only the requested authorized resources, submit them
to the same bootstrap and execute again. Never crawl unrelated resources or use
machine-local paths as portable project identity. Continue after `created` or
`already_completed`; use the private URL only for `review_required` or explicit
review-first requests. That optional path uses
`spm_project_bootstrap_preview`, submits requested bounded evidence through
`spm_project_bootstrap_evidence_submit` and completes through
`spm_project_bootstrap_confirm`. Never create project memory without an explicit
user instruction. If SPM unavailable status is returned, say `SPM unavailable`
plainly and continue without claiming persistence.

When authorized work must continue in another agent or device, create a
short-lived one-time handoff with `spm_agent_session_continuation_create`. The
receiving agent accepts it with `spm_agent_session_continuation_accept`; cancel
an unused handoff with `spm_agent_session_continuation_revoke`. Only project and
injected-context references cross the handoff. SPM rechecks current
authorization and does not transfer memory bodies or credentials.

Before creating the handoff, call `spm_agent_workspace_manifest_record` with
body-free evidence about required material resources: Git identity, revision and
local-state hash; non-Git filesystem/document hashes; remote version references;
or `memory_only`. The receiving agent inspects its available workspace, includes
that manifest during acceptance and follows the returned alignment result. Never
clone, pull, reset, overwrite or reveal raw diffs automatically. Use
`spm_agent_workspace_manifest_list` to inspect authorized session or project
history.

Follow the dynamic session source-capture contract for an authorized file, specification, repository snapshot, tool result or endpoint response that materially informed work. Call `spm_agent_resource_handoff` for a missing source with its concrete reference, kind and a redacted body or accurate summary. Include `source_identity` when a governed repository/source scope and repository-relative logical path are available; revision and machine belong to that observation, not to logical identity. SPM checks source coverage at work closure, reuses identical evidence canonically without discarding observed locations and links a changed portable source as a version across agents or machines. Do not imply that SPM read host files, hidden tool output or endpoints automatically, and never hand off secrets or data outside the approved sharing boundary.
