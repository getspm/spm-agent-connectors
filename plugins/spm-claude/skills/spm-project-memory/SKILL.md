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

When SPM returns a project-association `user_prompt`, ask it naturally in the
user's language and interpret the answer semantically. A likely match can be
confirmed, replaced or skipped; an ambiguous match can list candidates. For
`bootstrap_required`, ask whether to prepare a new project, show existing projects
or continue without durable memory. Call `spm_project_bootstrap_preview` only after
the user chooses a new project. Its private URL is used solely for authenticated
confirmation. Never replace the question with a status note or bare URL, create a
project silently or claim persistence before confirmation.

Do not store secrets, credentials, raw private tokens or unnecessary personal data.
Use context packs for handoff and preserve project id, source, temporal assessment,
policy boundary and verification hash.
