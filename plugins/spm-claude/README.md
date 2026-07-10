# SPM for Claude Code

This plugin connects Claude Code to the hosted SPM MCP endpoint and captures the
session lifecycle automatically through authenticated HTTP hooks.

The same SPM token governs MCP reads/writes and lifecycle capture. It can be scoped
to one project, a selected project set plus external mounts, or all projects the
authorized organization user may access. Project ambiguity never causes an
arbitrary durable write.

Authorize with the browser device flow, export the returned token as
`SPM_AGENT_TOKEN`, then install this directory as a Claude Code plugin. The plugin
contains no credential and never stores a raw transcript in SPM.
