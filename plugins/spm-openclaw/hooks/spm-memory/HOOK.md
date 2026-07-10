---
name: spm-memory
description: "Capture OpenClaw inbound and outbound project-memory events in SPM"
metadata:
  {"openclaw":{"events":["message:received","message:sent"],"requires":{"env":["SPM_AGENT_TOKEN"]},"homepage":"https://getspm.com"}}
---

# SPM memory lifecycle

Submits successful inbound and outbound message events to the authenticated SPM
lifecycle adapter. SPM resolves the active authorized project, performs LLM-first
triage and refuses ambiguous durable writes.
