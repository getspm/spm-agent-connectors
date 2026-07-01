#!/usr/bin/env python3
"""Install or render the SPM remote MCP connector for Codex."""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_ENDPOINT = "https://getspm.com/v1/mcp"
DEFAULT_TOKEN_ENV_VAR = "SPM_CODEX_MCP_TOKEN"
BEGIN_MARKER = "# BEGIN SPM CODEX MCP"
END_MARKER = "# END SPM CODEX MCP"


def build_codex_mcp_config(
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    token_env_var: str = DEFAULT_TOKEN_ENV_VAR,
    server_name: str = "spm",
    required: bool = False,
    startup_timeout_sec: int = 30,
    tool_timeout_sec: int = 120,
) -> str:
    required_line = "\nrequired = true" if required else ""
    return (
        f"{BEGIN_MARKER}\n"
        f"[mcp_servers.{server_name}]\n"
        f'url = "{endpoint.rstrip()}"\n'
        f'bearer_token_env_var = "{token_env_var.strip()}"\n'
        f"startup_timeout_sec = {startup_timeout_sec}\n"
        f"tool_timeout_sec = {tool_timeout_sec}"
        f"{required_line}\n"
        f"{END_MARKER}\n"
    )


def build_agent_guidance() -> str:
    return """# SPM-aware Codex guidance

Use SPM when work involves durable requirements, architecture, testing, security,
privacy, authorization, billing, deployment, temporal tension, context packs,
agent handoff, governed sharing or post-action evidence.

Before consequential changes, query SPM temporal state or request a context pack.
Run SPM preflight for risky work. After completion, report changed files, tests,
decisions and evidence back to SPM. Do not store secrets or raw sensitive data.
Prefer summaries, hashes, source references and redacted evidence.
"""


def upsert_marked_block(existing: str, block: str) -> str:
    if BEGIN_MARKER in existing and END_MARKER in existing:
        start = existing.index(BEGIN_MARKER)
        end = existing.index(END_MARKER, start) + len(END_MARKER)
        remainder = existing[end:]
        if remainder.startswith("\n"):
            remainder = remainder[1:]
        prefix = existing[:start].rstrip()
        return "\n\n".join(part for part in (prefix, block.rstrip(), remainder.rstrip()) if part) + "\n"
    prefix = existing.rstrip()
    return "\n\n".join(part for part in (prefix, block.rstrip()) if part) + "\n"


def write_config(path: Path, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(upsert_marked_block(existing, block), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the SPM remote MCP connector for Codex.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="SPM remote MCP endpoint.")
    parser.add_argument("--token-env-var", default=DEFAULT_TOKEN_ENV_VAR, help="Environment variable that stores the SPM project token.")
    parser.add_argument("--server-name", default="spm", help="Codex MCP server name.")
    parser.add_argument("--startup-timeout-sec", type=int, default=30)
    parser.add_argument("--tool-timeout-sec", type=int, default=120)
    parser.add_argument("--required", action="store_true", help="Make Codex fail loudly when SPM MCP cannot initialize.")
    parser.add_argument("--write-project", action="store_true", help="Write .codex/config.toml in the selected project root.")
    parser.add_argument("--write-user", action="store_true", help="Write ~/.codex/config.toml.")
    parser.add_argument("--config-path", type=Path, help="Write an explicit Codex config path.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root used with --write-project.")
    parser.add_argument("--print-guidance", action="store_true", help="Print AGENTS.md guidance after the config.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    block = build_codex_mcp_config(
        endpoint=args.endpoint,
        token_env_var=args.token_env_var,
        server_name=args.server_name,
        required=args.required,
        startup_timeout_sec=args.startup_timeout_sec,
        tool_timeout_sec=args.tool_timeout_sec,
    )
    targets: list[Path] = []
    if args.write_project:
        targets.append(args.project_root / ".codex" / "config.toml")
    if args.write_user:
        targets.append(Path.home() / ".codex" / "config.toml")
    if args.config_path:
        targets.append(args.config_path.expanduser())

    if targets:
        for target in targets:
            write_config(target, block)
            print(f"wrote {target}")
    else:
        print(block.rstrip())

    print(f"token_env_var={args.token_env_var}")
    print("token_value=not_printed")
    if args.print_guidance:
        print()
        print(build_agent_guidance().rstrip())


if __name__ == "__main__":
    main()
