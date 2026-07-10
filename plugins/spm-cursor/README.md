# SPM for Cursor

This bundle configures the hosted SPM MCP endpoint and installs project-memory
guidance for Cursor IDE and Cursor Agent. Cursor can resolve the active project,
query temporal memory, compose explicit cross-project context, create verified
context packs and report durable outcomes through the same governed API.

The bundle does not pretend that Cursor IDE exposes lifecycle hooks it does not
provide. MCP behavior is native; automatic user/assistant turn capture is supplied
by the optional `scripts/agent-connectors/spm-cursor-agent.py` wrapper.
