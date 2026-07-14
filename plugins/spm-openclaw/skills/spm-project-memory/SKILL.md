---
name: spm-project-memory
description: Use SPM for durable temporal memory, governed sharing, project resolution and context composition.
---

# SPM project memory

Use the SPM MCP tools naturally for durable project state, temporal reasoning,
explicit cross-project composition, context boundaries, verification, preflight and
post-action evidence. Inbound and successful outbound messages are triaged by the
installed lifecycle hook. Never mix projects implicitly and never store secrets.

Surface pending project attention at session start. Treat delivery, surfacing,
acknowledgement and resolution as different states; never infer the latter two from display.

When the lifecycle returns a project-association `user_prompt`, ask it naturally
and map the user's ordinary-language answer to its structured reply options. For
`bootstrap_required`, ask whether to prepare a new project, show existing projects
or continue without durable memory. Call `spm_project_bootstrap_preview` only after
the user chooses a new project; use its URL solely for authenticated confirmation.
Do not replace the conversation with a bare URL or claim that project memory exists
before confirmation.
