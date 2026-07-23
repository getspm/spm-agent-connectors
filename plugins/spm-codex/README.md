# SPM for Codex

This plugin connects Codex to Structured Project Memory through the hosted SPM remote MCP endpoint.

SPM gives Codex persistent project memory, temporal state, context packs, context
boundaries, project resolution, explicit cross-project packs, trust status,
preflight and post-action reports. Lifecycle hooks submit user and assistant
turns under the effective SPM capture policy, then LLM-first triage derives
persistent memory. The user does not need to ask Codex to store it explicitly.

## Install

1. Authorize Codex with a browser-approved device flow:

```bash
python3 plugins/spm-codex/scripts/auth_spm_codex.py --write-env ~/.spm/codex.env
source ~/.spm/codex.env
```

The script opens SPM before it needs a project UUID. The signed-in user chooses
one project, a selected project set or every authorized organization project,
and independently chooses whether governed external project mounts are hidden,
selected or all available. Every Codex task still maintains one active project;
availability never causes automatic cross-project recall. The token is returned
once and written with file mode `0600` when `--write-env` is used.

For an intentionally isolated installation, pass `--access-mode project
--project-id <project-id> --external-access-mode none`. Access can later be
narrowed or expanded from the private SPM console. Codex can also call
`spm_connector_access_request` conversationally, but the requested boundary is
not applied until a human approves it in SPM.

Manual fallback: generate or reveal a project-scoped SPM agent token from the private SPM console and export it before starting Codex:

```bash
export SPM_CODEX_MCP_TOKEN="<project-scoped-token>"
```

The receipt mode is selected during browser authorization with
`--memory-receipt-mode compact` (or `audit`). It is stored in the connector
authorization and returned by the MCP/API session metadata; no string matching
is used to decide whether a receipt is shown.

The global lifecycle hook never reuses the token in `~/.spm/config.toml` by
default because that CLI token may be limited to an unrelated project. A
deliberately project-local installation may opt in with
`SPM_CODEX_ALLOW_CLI_TOKEN=1`; otherwise a missing Codex token disables memory
capture for that turn without blocking Codex.

Organization mode is appropriate when the same authorized user works across
several projects. Visibility does not imply mixing: each task keeps one active
project, and cross-project context packs require an explicit user request.
`spm_multi_project_context_pack` can compose several explicitly named projects
while retaining one verifiable pack and provenance boundary per source.

2. Install this plugin from the Codex plugin marketplace entry in this repository, or add the MCP server manually:

```toml
[mcp_servers.spm]
url = "https://getspm.com/v1/mcp"
bearer_token_env_var = "SPM_CODEX_MCP_TOKEN"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

3. Open a new Codex session and check `/mcp`.

4. Open `/hooks`, review the plugin lifecycle hooks and trust them. Codex hashes
hook definitions, so a changed hook must be reviewed again before automatic
capture resumes.

## Automatic Lifecycle

- `SessionStart` starts or resumes an SPM agent-memory session and resolves the
  current workspace against authorized projects.
- `UserPromptSubmit` applies the effective selective, complete redacted,
  summaries-only or metadata-only capture policy before LLM-first triage. When
  a capture receipt exists, it gives Codex canonical, verified receipt facts
  and a same-turn instruction to append that *input* receipt at the end of its
  response. Codex renders the labels in the language it uses for the
  substantive response; the hook does not impose a translated sentence. It
  never asks Codex to invent a hash for a response that has not yet been
  emitted.
- `Stop` sends the exact final assistant turn and its achieved state to the
  same project session. It then asks SPM to evaluate the captured prompt and
  captured final response as one completed work unit. This uses the existing
  journal entries as the canonical source and does not create a second RAW
  transcript. The completed-turn receipt remains available through SPM's
  structured API/MCP status rather than appearing as an extra host-UI
  notification after the answer.
- The connector can return one capture receipt after each iteration. `compact`
  is the default and shows the project, input state, memory state, temporal
  layer and a short hash. Codex renders compact receipt labels in the same
  language as its substantive response and uses product language such as `input saved`,
  `project memory updated`, `memory saved without automatic promotion`,
  `smart memory classification not completed` or `source saved as evidence`.
  Internal triage/review states and diagnostic codes stay in structured operator
  fields. `discreet` only surfaces attention-worthy states, and `audit` shows the
  project, journal/event identifiers and decision hashes. The input receipt and
  the completed-turn status receipt are provenance evidence, not claims that
  the stored content is semantically true.
- Ambiguous project identity produces a confirmation request and no memory
  write. The hook never chooses an arbitrary project and never blocks Codex.
- SPM generates `codex://session/.../turn/...` provenance automatically. Full
  source retention is optional, redacted and encrypted in a separate journal;
  session tables never contain raw transcripts.
- `spm_memory_capture_evidence` gives an audited, body-free account of the
  effective capture policy, journal verification and triage outcomes for the
  active project.
- `spm_memory_context_compose` builds governed task context from canonical
  project memory, with source refs, temporal signals, authority and explicitly
  injected session context.

## Transport Trace (Opt-In)

For connector diagnosis, set this before starting a new Codex task:

```bash
export SPM_CODEX_CAPTURE_TRACE=full
```

The hook writes an owner-only local JSONL trace at
`$PLUGIN_DATA/capture-trace.jsonl`. It records the exact text received from
Codex, transmitted to SPM, and returned to Codex as `additionalContext`.
`metadata` records only hashes and lengths; `off` is the default. The trace is
never sent to SPM and `full` can contain sensitive local content, so turn it
off and delete the file after diagnosis.

## Verify

Run:

```bash
python3 plugins/spm-codex/scripts/doctor_spm_codex.py
```

The doctor checks the public MCP metadata, confirms the token is present without printing it, initializes the hosted MCP endpoint and verifies that the required project-memory tools are exposed.

To verify the public metadata and safety boundary without a token:

```bash
python3 plugins/spm-codex/scripts/doctor_spm_codex.py --metadata-only
```

## Security Boundary

The hosted connector supports one-project, selected-project-set and organization
authorization. An organization token can resolve any authorized project without
being reinstalled, while every conversation still keeps one active project and
cross-project composition remains explicit. The connector returns event bodies
as summaries by default, does not return secrets, and does not expose SPM
billing, checkout, invoice payment, customer portal creation or destructive
admin tools to Codex. Use read-write tokens only for trusted agent sessions that
may record temporal events or post-action evidence.
