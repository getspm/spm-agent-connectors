---
name: spm-project-memory
description: Use SPM for durable requirements, temporal project state, governed context sharing, cross-project composition and consequential agent work.
---

# SPM project memory

Use SPM naturally when project work depends on durable requirements, decisions,
completed work, temporal validity, authority, context boundaries, source evidence,
agent handoff, testing, security, deployment or governed sharing.

The native lifecycle hooks submit ordinary user and assistant turns to
`spm_agent_turn_ingest` after `spm_agent_session_start` resumes the SPM session.
Do not ask the user to repeat an SPM command for routine capture. Query the active
project first. List or compose another authorized project only when the user
explicitly requests cross-project context. Use `spm_agent_session_context_inject`,
`spm_agent_session_context_revoke`, `spm_cross_project_context_pack` or
`spm_multi_project_context_pack` only for explicit cross-project or shared-context
work. Never claim that memory was persisted if SPM reports ambiguity, SPM
unavailable state or a failed write. If SPM unavailable status is returned,
say so plainly and continue without claiming persistence.

Surface project attention returned at session start before continuing with the first
request. Display is not acknowledgement: update recipient state only after an explicit
user instruction to acknowledge, defer, resolve or dismiss an item.

When SPM returns a project-association `user_prompt`, ask it naturally in the
user's language and interpret the answer semantically. A likely match can be
confirmed, replaced or skipped; an ambiguous match can list candidates. For
`bootstrap_required`, ask whether to create a new project, show existing projects
or continue without persistent memory in SPM. Confirm, replace or skip a match only through
`spm_agent_session_association_decide`. Call `spm_project_bootstrap_preview` only
after the user chooses a new project. If the user then explicitly confirms create,
link or skip in the agent conversation and the connector has write permission, call
`spm_project_bootstrap_confirm`; otherwise use the private URL solely for
authenticated confirmation. Never replace the question with a status note or bare
URL, create a project silently or claim persistence before confirmation.

Use `spm_agent_session_receipt_delivery_report` to record body-free connector
evidence that the receipt instruction was supplied or completion was observed.
Use `spm_agent_session_receipt_status` when the host drops or hides lifecycle
status text. Use `spm_memory_capture_policy_get` to inspect that policy and
`spm_memory_capture_evidence` for a body-free audit of capture state and
`spm_memory_context_compose` for governed task context before consequential
work in a confirmed project.

Do not store secrets, credentials, raw private tokens or unnecessary personal data.
Use context packs for handoff and preserve project id, source, temporal assessment,
policy boundary and verification hash.

Follow the dynamic session source-capture contract when an authorized file, specification, repository snapshot, tool result or endpoint response materially informs work. Use `spm_agent_resource_handoff` for a missing source with its stable reference, kind and a redacted body or accurate summary. SPM checks coverage at work closure, reuses byte-identical evidence canonically and versions a changed stable source. It does not gain implicit access to local files, hidden tool output or endpoints. Never hand off secrets or data outside the approved sharing boundary.
