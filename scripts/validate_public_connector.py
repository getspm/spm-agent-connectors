#!/usr/bin/env python3
"""Validate that this repository remains a connector-only public package."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "LICENSE",
    ROOT / "server.json",
    ROOT / "directory-listing.json",
    ROOT / ".agents" / "plugins" / "marketplace.json",
    ROOT / "plugins" / "spm-codex" / ".codex-plugin" / "plugin.json",
    ROOT / "plugins" / "spm-codex" / ".mcp.json",
    ROOT / "plugins" / "spm-codex" / "scripts" / "auth_spm_codex.py",
    ROOT / "plugins" / "spm-codex" / "scripts" / "doctor_spm_codex.py",
    ROOT / "plugins" / "spm-codex" / "scripts" / "smoke_spm_remote_mcp.py",
    ROOT / "plugins" / "spm-claude" / ".claude-plugin" / "plugin.json",
    ROOT / "plugins" / "spm-cursor" / ".cursor-plugin" / "plugin.json",
    ROOT / "plugins" / "spm-openclaw" / "hooks" / "spm-memory" / "handler.js",
    ROOT / "scripts" / "agent-connectors" / "authorize_spm_agent.py",
    ROOT / "scripts" / "agent-connectors" / "spm-agent-lifecycle.py",
    ROOT / "docs" / "security-boundary.md",
    ROOT / "docs" / "publishing.md",
    ROOT / "docs" / "directory-listing-pack.md",
]

BANNED_TOP_LEVEL = {
    "backend",
    "frontend",
    "deploy",
    "sdk",
    "ops",
    "alembic",
}

SECRET_PATTERNS = [
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"rk_live_[A-Za-z0-9]+"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
]

BANNED_PUBLIC_PHRASES = [
    "xchat",
    "because the user asked",
    "as requested",
    "messy project",
    "internal roadmap",
]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_dir() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path == Path(__file__).resolve():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".pyc"}:
            continue
        files.append(path)
    return files


def main() -> int:
    for path in REQUIRED_FILES:
        if not path.exists():
            fail(f"missing required file: {path.relative_to(ROOT)}")
        if path.stat().st_size == 0:
            fail(f"empty required file: {path.relative_to(ROOT)}")

    top_level = {path.name for path in ROOT.iterdir()}
    forbidden = sorted(BANNED_TOP_LEVEL & top_level)
    if forbidden:
        fail(f"core directories must not be public connector repo content: {forbidden}")

    marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
    plugin = json.loads((ROOT / "plugins" / "spm-codex" / ".codex-plugin" / "plugin.json").read_text())
    mcp = json.loads((ROOT / "plugins" / "spm-codex" / ".mcp.json").read_text())
    listing = json.loads((ROOT / "directory-listing.json").read_text())
    server = json.loads((ROOT / "server.json").read_text())

    assert marketplace["plugins"][0]["source"]["path"] == "./plugins/spm-codex"
    assert plugin["name"] == "spm-codex"
    assert plugin["mcpServers"] == "./.mcp.json"
    assert mcp["mcpServers"]["spm"]["url"] == "https://getspm.com/v1/mcp"
    assert mcp["mcpServers"]["spm"]["bearer_token_env_var"] == "SPM_CODEX_MCP_TOKEN"
    assert listing["remote_mcp_endpoint"] == "https://getspm.com/v1/mcp"
    assert listing["static_server_card"] == "https://getspm.com/.well-known/mcp/server-card.json"
    assert listing["repository"] == "https://github.com/getspm/spm-agent-connectors"
    assert listing["authentication"]["required"] is True
    assert listing["authentication"]["scheme"] == "bearer"
    assert listing["authentication"]["token_scope"] == "project, project_set or organization"
    assert "checkout" in listing["excluded_connector_surfaces"]
    assert len(listing["capabilities"]) >= 8
    assert server["name"] == "com.getspm/spm"
    assert server["title"] == "SPM - Structured Project Memory"
    assert server["websiteUrl"] == "https://getspm.com"
    assert server["repository"]["url"] == "https://github.com/getspm/spm-agent-connectors"
    assert server["repository"]["source"] == "github"
    assert server["version"] == "0.2.0"
    assert "packages" not in server
    assert server["remotes"][0]["type"] == "streamable-http"
    assert server["remotes"][0]["url"] == "https://getspm.com/v1/mcp"
    authorization_header = server["remotes"][0]["headers"][0]
    assert authorization_header["name"] == "Authorization"
    assert authorization_header["isRequired"] is True
    assert authorization_header["isSecret"] is True
    publisher_meta = server["_meta"]["io.modelcontextprotocol.registry/publisher-provided"]
    assert publisher_meta["agentIntegrationGuide"] == "https://getspm.com/agents"
    assert "billing" in publisher_meta["excludedConnectorSurfaces"]
    assert "smart_project_memory" in publisher_meta["capabilities"]
    assert "explicit_multi_project_composition" in publisher_meta["capabilities"]
    assert "agent_lifecycle_triage" in publisher_meta["capabilities"]

    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        for phrase in BANNED_PUBLIC_PHRASES:
            if phrase in lower:
                fail(f"banned public phrase in {path.relative_to(ROOT)}: {phrase}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"secret-like value in {path.relative_to(ROOT)}")

    print("public connector repo ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
