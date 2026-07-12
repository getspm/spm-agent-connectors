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

When the lifecycle reports `bootstrap_required`, call
`spm_project_bootstrap_preview` with source-grounded conversation context and give
the user its confirmation URL. Creation, linking or skipping is a human decision;
do not claim that project memory exists before confirmation.
