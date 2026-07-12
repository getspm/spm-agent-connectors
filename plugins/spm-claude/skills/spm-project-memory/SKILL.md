---
name: spm-project-memory
description: Use SPM for durable requirements, temporal project state, governed context sharing, cross-project composition and consequential agent work.
---

# SPM project memory

Use SPM naturally when project work depends on durable requirements, decisions,
completed work, temporal validity, authority, context boundaries, source evidence,
agent handoff, testing, security, deployment or governed sharing.

The lifecycle hooks submit ordinary user and assistant turns to LLM-first memory
triage. Do not ask the user to repeat an SPM command for routine capture. Query the
active project first. List or compose another authorized project only when the user
explicitly requests cross-project context. Never claim that memory was persisted if
SPM reports ambiguity or a failed write.

Surface project attention returned at session start before continuing with the first
request. Display is not acknowledgement: update recipient state only after an explicit
user instruction to acknowledge, defer, resolve or dismiss an item.

If SPM returns `bootstrap_required`, prepare a source-grounded proposal with
`spm_project_bootstrap_preview` and present its confirmation URL. The user decides
whether to create project memory, link an existing project or continue without
durable memory. Never create a project silently or claim persistence before the
review is confirmed.

Do not store secrets, credentials, raw private tokens or unnecessary personal data.
Use context packs for handoff and preserve project id, source, temporal assessment,
policy boundary and verification hash.
