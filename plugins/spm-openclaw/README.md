# SPM for OpenClaw

This OpenClaw bundle contributes the hosted SPM MCP server, project-memory skill and
message lifecycle hook. The hook is fail-open for the conversation and fail-closed
for memory: transport or project ambiguity cannot write into an arbitrary project.

Set `SPM_AGENT_TOKEN`, install this directory with OpenClaw's plugin installer and
restart the Gateway. The token may authorize one project, a selected set including
external mounts, or all projects available to the organization user.
