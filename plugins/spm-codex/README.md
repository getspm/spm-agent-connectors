# SPM for Codex

This plugin connects Codex to Structured Project Memory through SPM remote MCP.

## Install

1. Authorize Codex with a browser-approved device flow:

```bash
python3 plugins/spm-codex/scripts/auth_spm_codex.py --project-id <project-id> --write-env ~/.spm/codex.env
source ~/.spm/codex.env
```

The script opens SPM, asks a logged-in project admin to approve the code and returns a project-scoped token once. The token is written with file mode `0600` when `--write-env` is used.

Manual fallback: generate or reveal a project-scoped SPM agent token from the private SPM console and export it before starting Codex:

```bash
export SPM_CODEX_MCP_TOKEN="<project-scoped-token>"
```

2. Install this plugin from the Codex plugin marketplace entry in this repository, or add the MCP server manually:

```toml
[mcp_servers.spm]
url = "https://getspm.com/v1/mcp"
bearer_token_env_var = "SPM_CODEX_MCP_TOKEN"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

3. Open a new Codex session and check `/mcp`.

## Verify

Run:

```bash
python3 plugins/spm-codex/scripts/doctor_spm_codex.py
```

The doctor checks the public MCP metadata, confirms the token is present without printing it, initializes the hosted MCP endpoint and verifies that the required project-memory tools are exposed.

## Security Boundary

The hosted connector is project-scoped. It does not expose SPM billing, checkout, invoice payment, customer portal creation or destructive admin tools to Codex. Use read-write tokens only for trusted agent sessions that may record temporal events or post-action evidence.
