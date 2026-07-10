#!/usr/bin/env python3
"""Vendor-neutral agent lifecycle bridge for SPM.

Agent runtimes can invoke this command from session/prompt/completion hooks. The
bridge keeps only an opaque SPM session id locally; SPM performs LLM-first
triage, creates canonical provenance and refuses writes while project identity
is ambiguous.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://getspm.com/v1"
MAX_CONTENT_CHARS = 100_000


class LifecycleBridgeError(RuntimeError):
    pass


def _api_url() -> str:
    return os.environ.get("SPM_API_URL", DEFAULT_API_URL).rstrip("/")


def _token() -> str:
    token = (
        os.environ.get("SPM_AGENT_TOKEN")
        or os.environ.get("SPM_CODEX_MCP_TOKEN")
        or ""
    ).strip()
    if not token:
        raise LifecycleBridgeError(
            "SPM_AGENT_TOKEN (or SPM_CODEX_MCP_TOKEN) is required"
        )
    return token


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{_api_url()}/{path.lstrip('/')}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "spm-agent-lifecycle/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise LifecycleBridgeError(f"SPM API returned HTTP {exc.code}: {detail}") from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise LifecycleBridgeError(f"SPM API request failed: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleBridgeError("SPM API returned an invalid lifecycle response")
    return value


def _state_dir() -> Path:
    configured = os.environ.get("SPM_AGENT_STATE_DIR")
    path = Path(configured).expanduser() if configured else Path.home() / ".spm" / "agent-sessions"
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def _session_key(client_kind: str, external_session_id: str) -> str:
    return hashlib.sha256(f"{client_kind}:{external_session_id}".encode("utf-8")).hexdigest()


def _state_path(client_kind: str, external_session_id: str) -> Path:
    return _state_dir() / f"{_session_key(client_kind, external_session_id)}.json"


def _read_state(client_kind: str, external_session_id: str) -> dict[str, Any]:
    path = _state_path(client_kind, external_session_id)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(client_kind: str, external_session_id: str, session: dict[str, Any]) -> None:
    path = _state_path(client_kind, external_session_id)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "spm_session_id": session["id"],
                "source_namespace": session.get("source_namespace"),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)


def start_session(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "client_kind": args.client_kind,
        "external_session_id": args.external_session_id,
        "workspace_hint": args.workspace_hint,
        "prompt": args.prompt,
        "project_ref": args.project_ref,
        "include_projects": not args.no_project_catalog,
        "metadata": {"source": "spm-agent-lifecycle-bridge"},
    }
    session = _request(
        "POST",
        "/agent-memory-sessions",
        {key: value for key, value in payload.items() if value is not None},
    )
    _write_state(args.client_kind, args.external_session_id, session)
    return session


def _session_id(args: argparse.Namespace) -> str:
    state = _read_state(args.client_kind, args.external_session_id)
    session_id = str(state.get("spm_session_id") or "").strip()
    if session_id:
        return session_id
    return str(start_session(args)["id"])


def ingest_turn(args: argparse.Namespace) -> dict[str, Any]:
    content = args.content
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    if content is None:
        content = sys.stdin.read()
    content = content.strip()
    if not content:
        raise LifecycleBridgeError("Turn content is required")
    if len(content) > MAX_CONTENT_CHARS:
        raise LifecycleBridgeError(
            f"Turn content exceeds the {MAX_CONTENT_CHARS} character bridge limit"
        )
    session_id = _session_id(args)
    payload = {
        "external_turn_id": args.external_turn_id,
        "role": args.role,
        "content": content,
        "title": args.title,
        "workspace_hint": args.workspace_hint,
        "project_ref": args.project_ref,
        "actor_ref": args.actor_ref,
        "actor_role": args.actor_role,
        "authority_role": args.authority_role,
        "relevance_target": args.relevance_target,
        "user_intent": args.user_intent,
        "metadata": {"source": "spm-agent-lifecycle-bridge"},
    }
    return _request(
        "POST",
        f"/agent-memory-sessions/{urllib.parse.quote(session_id)}/turns",
        {key: value for key, value in payload.items() if value is not None},
    )


def set_project(args: argparse.Namespace) -> dict[str, Any]:
    session_id = _session_id(args)
    session = _request(
        "POST",
        f"/agent-memory-sessions/{urllib.parse.quote(session_id)}/project",
        {"project_ref": args.project_ref, "reason": args.reason},
    )
    _write_state(args.client_kind, args.external_session_id, session)
    return session


def get_session(args: argparse.Namespace) -> dict[str, Any]:
    session_id = _session_id(args)
    return _request("GET", f"/agent-memory-sessions/{urllib.parse.quote(session_id)}")


def _base_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--client-kind", required=True, help="Agent/runtime name, for example cursor or claude")
    parser.add_argument("--external-session-id", required=True, help="Stable task/thread id from the agent runtime")
    parser.add_argument("--workspace-hint", default=os.getcwd())
    parser.add_argument("--project-ref")
    parser.add_argument("--prompt")
    parser.add_argument("--no-project-catalog", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge agent lifecycle events into SPM")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start", help="Start or resume an SPM agent session")
    _base_arguments(start)
    start.set_defaults(handler=start_session)

    show = subparsers.add_parser("show", help="Show the current SPM session and project catalog")
    _base_arguments(show)
    show.set_defaults(handler=get_session)

    project = subparsers.add_parser("set-project", help="Explicitly change the active project")
    _base_arguments(project)
    project.add_argument("--reason", required=True)
    project.set_defaults(handler=set_project)

    turn = subparsers.add_parser("turn", help="Submit one user or assistant turn to SPM triage")
    _base_arguments(turn)
    turn.add_argument("--external-turn-id", required=True)
    turn.add_argument("--role", required=True, choices=("user", "assistant", "combined"))
    turn.add_argument("--content")
    turn.add_argument("--content-file")
    turn.add_argument("--title")
    turn.add_argument("--actor-ref")
    turn.add_argument("--actor-role")
    turn.add_argument("--authority-role")
    turn.add_argument("--relevance-target")
    turn.add_argument("--user-intent")
    turn.set_defaults(handler=ingest_turn)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = args.handler(args)
    except LifecycleBridgeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "result": result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
