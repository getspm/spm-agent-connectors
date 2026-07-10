# SPM for Codex

This plugin connects Codex to Structured Project Memory through the hosted SPM remote MCP endpoint.

SPM gives Codex durable project memory, temporal state, context packs, context
boundaries, project resolution, explicit cross-project packs, trust status,
preflight and post-action reports. Lifecycle hooks submit user and assistant
turns to SPM's LLM-first triage, so durable memory does not depend on the user
asking Codex to store it explicitly.

## Install

1. Authorize Codex with a browser-approved device flow:

```bash
python3 plugins/spm-codex/scripts/auth_spm_codex.py --project-id <authorization-project-id> --access-mode organization --write-env ~/.spm/codex.env
source ~/.spm/codex.env
```

The script opens SPM and asks a logged-in owner or admin to approve the access boundary. Organization mode lets the connector list authorized projects while every Codex task still maintains one active project. Use `--access-mode project` when the connector should never leave the authorization project. The token is returned once and written with file mode `0600` when `--write-env` is used.

Manual fallback: generate or reveal a project-scoped SPM agent token from the private SPM console and export it before starting Codex:

```bash
export SPM_CODEX_MCP_TOKEN="<project-scoped-token>"
```

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
- `UserPromptSubmit` sends the user turn to LLM-first triage.
- `Stop` sends the final assistant turn and its achieved state to the same
  project session.
- Ambiguous project identity produces a confirmation request and no memory
  write. The hook never chooses an arbitrary project and never blocks Codex.
- SPM generates `codex://session/.../turn/...` provenance automatically. Raw
  transcripts are not stored in the session tables.

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

The hosted connector supports project-scoped tokens and organization-scoped
project resolution. In both cases it keeps an active project per conversation,
returns event bodies as summaries by default, does not return secrets, and does
not expose SPM billing, checkout, invoice payment, customer portal creation or
destructive admin tools to Codex. Use read-write tokens only for trusted agent
sessions that may record temporal events or post-action evidence.
