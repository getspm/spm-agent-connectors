# SPM for Cursor

This bundle configures the hosted SPM MCP endpoint and installs project-memory
guidance for Cursor IDE and Cursor Agent. Cursor can resolve the active project,
query temporal memory, compose explicit cross-project context, create verified
context packs and report durable outcomes through the same governed API.

The bundle does not pretend that Cursor IDE exposes lifecycle hooks it does not
provide. MCP behavior is native; automatic user/assistant turn capture is supplied
by the optional `ops/agent-connectors/spm-cursor-agent.py` wrapper.

Authorize the connector without copying a project UUID first:

```bash
python3 ops/agent-connectors/authorize_spm_agent.py \
  --client-name "Cursor" \
  --write-env ~/.spm/cursor.env
source ~/.spm/cursor.env
```

The browser approval chooses one, selected or all authorized local projects and
an independent external-project boundary. Cursor defaults to the active project
and composes another project only after an explicit user request.

Runtime parity with other SPM adapters is preserved through the hosted MCP tools:
`spm_agent_session_association_decide` for conversational project decisions,
`spm_agent_session_context_inject` and `spm_agent_session_context_revoke` for
explicit cross-project context, `spm_agent_session_receipt_status` for capture
status, `spm_agent_session_receipt_delivery_report` for body-free receipt delivery
evidence, and `spm_agent_turn_ingest` for wrapper-driven lifecycle capture. If SPM
is unavailable, Cursor should continue the user task without claiming persistent
memory.

When a file, specification, repository snapshot, tool result or endpoint response
materially informs work, Cursor or its wrapper follows the dynamic session
source-capture contract and can call `spm_agent_resource_handoff` with a concrete
source reference and an authorized redacted body or summary. Portable sources also
include `source_identity`: the governed repository/source scope and repository-
relative logical path, while revision and machine remain observation metadata. SPM
checks source coverage at work closure, canonically reuses identical evidence
without losing observed locations and links changed portable sources across agents
or machines. The connector does not claim access to arbitrary local files, hidden
tool output or endpoints. The handoff follows the same capture policy, journal,
temporal triage and governed sharing controls as a normal agent turn.
