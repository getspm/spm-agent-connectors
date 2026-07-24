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
`spm_agent_session_association_decide`. Call `spm_project_bootstrap_preview` only
after the user chooses a new project. Include a safe authorized-resource
inventory and source-grounded evidence from a bounded inspection. Follow a
specific `evidence_assessment.agent_instruction` with
`spm_project_bootstrap_evidence_submit`; never crawl unrelated resources or use
machine-local paths as portable project identity. If the user then explicitly confirms create,
link or skip in the agent conversation and the connector has write permission, call
`spm_project_bootstrap_confirm`; otherwise use the private URL solely for
authenticated confirmation. Do not replace the conversation with a bare URL,
claim that project memory exists before confirmation or claim persistence during
SPM unavailable states.

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

Follow the dynamic session source-capture contract for an authorized file, specification, repository snapshot, tool result or endpoint response that materially informed work. Call `spm_agent_resource_handoff` for a missing source with a source reference, source kind and a redacted body or accurate summary. SPM checks source coverage at work closure, reuses identical evidence canonically and links a changed stable source as a version. Do not imply that SPM read host files, hidden tool output or endpoints automatically, and never hand off secrets or data outside the approved sharing boundary.
