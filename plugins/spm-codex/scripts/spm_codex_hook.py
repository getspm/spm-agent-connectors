#!/usr/bin/env python3
"""Codex lifecycle bridge for SPM.

The hook is deliberately fail-open for Codex and fail-closed for memory: an
ambiguous project or unavailable SPM service never writes to an arbitrary
project and never blocks the user's task.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_MCP_URL = "https://getspm.com/v1/mcp"
TOKEN_ENV = "SPM_CODEX_MCP_TOKEN"
CLI_TOKEN_OPT_IN_ENV = "SPM_CODEX_ALLOW_CLI_TOKEN"
MAX_TURN_CHARS = 100_000
MAX_TRANSCRIPT_BYTES = 4 * 1024 * 1024


class SpmHookError(RuntimeError):
    pass


def _rpc_call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    endpoint, token = _resolve_credentials()
    if not token:
        raise SpmHookError(
            f"{TOKEN_ENV} is not configured and no browser-approved token was found in "
            "~/.spm/codex.env"
        )
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": hashlib.sha256(
                f"{tool}:{json.dumps(arguments, sort_keys=True)}".encode()
            ).hexdigest()[:16],
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-SPM-MCP-Profile": "agent-core",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=70) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SpmHookError(f"SPM MCP request failed: {exc}") from exc
    if payload.get("error"):
        raise SpmHookError(f"SPM MCP error: {payload['error'].get('message')}")
    result = payload.get("result") or {}
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise SpmHookError("SPM MCP returned no structured content")
    return structured


def _resolve_credentials() -> tuple[str, str]:
    explicit_endpoint = os.environ.get("SPM_CODEX_MCP_URL", "").strip()
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        token = _token_from_codex_env(Path.home() / ".spm" / "codex.env")

    config = _spm_config(Path.home() / ".spm" / "config.toml")
    if not token and _truthy(os.environ.get(CLI_TOKEN_OPT_IN_ENV)):
        token = str(config.get("token") or "").strip()
    endpoint = explicit_endpoint or _mcp_endpoint(str(config.get("api_url") or ""))
    return endpoint or DEFAULT_MCP_URL, token


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _token_from_codex_env(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        try:
            parts = shlex.split(line, comments=True, posix=True)
        except ValueError:
            continue
        if parts and parts[0] == "export":
            parts = parts[1:]
        for part in parts:
            prefix = f"{TOKEN_ENV}="
            if part.startswith(prefix):
                return part[len(prefix) :].strip()
    return ""


def _spm_config(path: Path) -> dict[str, Any]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _mcp_endpoint(api_url: str) -> str:
    cleaned = api_url.strip().rstrip("/")
    if not cleaned:
        return ""
    if cleaned.endswith("/v1/mcp"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/mcp"
    return f"{cleaned}/v1/mcp"


def _plugin_data_dir() -> Path:
    configured = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    path = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".codex" / "spm-codex"
    )
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def _session_key(event: dict[str, Any]) -> str:
    session_id = str(event.get("session_id") or "unknown-session")
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _state_path(event: dict[str, Any]) -> Path:
    return _plugin_data_dir() / f"session-{_session_key(event)}.json"


def _read_state(event: dict[str, Any]) -> dict[str, Any]:
    path = _state_path(event)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(event: dict[str, Any], state: dict[str, Any]) -> None:
    path = _state_path(event)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)


def _log(event: dict[str, Any], *, status: str, detail: str) -> None:
    entry = {
        "event": str(event.get("hook_event_name") or "unknown"),
        "session_hash": _session_key(event)[:16],
        "turn_hash": hashlib.sha256(
            str(event.get("turn_id") or "").encode()
        ).hexdigest()[:16],
        "status": status,
        "detail": detail[:1000],
    }
    path = _plugin_data_dir() / "lifecycle.log"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _start_or_resume(
    event: dict[str, Any], state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    existing_id = state.get("spm_session_id")
    if existing_id:
        try:
            session = _rpc_call(
                "spm_agent_session_get",
                {"session_id": existing_id, "include_projects": True},
            )
            active = session.get("active_project") or {}
            session["attention_briefing"] = _rpc_call(
                "spm_attention_briefing",
                {
                    "project_id": active.get("id"),
                    "mode": "relevant",
                    "limit": 8,
                    "mark_surfaced": True,
                },
            )
            return session, state
        except SpmHookError:
            state = {}
    external_session_id = str(event.get("session_id") or "").strip()
    if not external_session_id:
        raise SpmHookError("Codex hook did not provide session_id")
    session = _rpc_call(
        "spm_agent_session_start",
        {
            "client_kind": "codex",
            "external_session_id": external_session_id,
            "workspace_hint": str(event.get("cwd") or "") or None,
            "include_projects": True,
            "include_attention_briefing": True,
            "attention_mode": "relevant",
            "attention_limit": 8,
            "metadata": {
                "surface": "codex_plugin_hook",
                "model": str(event.get("model") or "unknown"),
            },
        },
    )
    state = {
        "spm_session_id": session["id"],
        "source_namespace": session.get("source_namespace"),
    }
    _write_state(event, state)
    return session, state


def _project_context(session: dict[str, Any]) -> str:
    active = session.get("active_project") or {}
    projects = session.get("accessible_projects") or []
    association = session.get("project_association") or {}
    if active:
        context = (
            f"SPM agent memory is active for project '{active.get('name')}' "
            f"({active.get('id')}). Keep ordinary recall and writes in this project. "
            "List or compose another authorized project only when the user explicitly asks."
        )
        attention = _attention_context(session.get("attention_briefing"))
        return f"{context}\n\n{attention}" if attention else context
    if association.get("user_prompt") or association.get("status") in {
        "proposed",
        "requires_selection",
        "external_context_only",
    }:
        return _association_conversation_context(association)
    if association.get("status") == "skipped":
        return (
            "The user chose to continue this Codex task without durable SPM project memory. "
            "Do not claim persistence. The user may explicitly select a project later."
        )
    if session.get("bootstrap"):
        return _association_conversation_context(association)
    names = ", ".join(str(project.get("name")) for project in projects[:12]) or "none"
    return (
        "SPM cannot safely select one project for this task yet. "
        f"Authorized projects: {names}. Ask the user once to choose a project, list the full catalog, "
        "or continue without durable memory. Persist the answer with "
        "spm_agent_session_association_decide before claiming that memory was stored."
    )


def _association_conversation_context(association: dict[str, Any]) -> str:
    prompt = str(
        association.get("user_prompt") or association.get("message") or ""
    ).strip()
    mappings = []
    for option in association.get("reply_options") or []:
        label = str(option.get("label") or option.get("intent") or "option")
        tool = str(option.get("tool") or "").strip()
        mappings.append(f"{label} -> {tool}" if tool else label)
    return (
        "SPM needs one project-memory decision. In the next user-facing response, ask this "
        "question directly and naturally in the user's language; do not turn it into a status "
        "note and do not show a bare confirmation URL:\n"
        f"{prompt}\n"
        "Interpret the answer semantically rather than by string matching. Intent mappings: "
        f"{'; '.join(mappings) or 'select or skip the association'}. If the user chooses a new "
        "project, call spm_project_bootstrap_preview with source-grounded context only then, and "
        "use its private URL solely for authenticated confirmation. Continue the requested work "
        "when safe, but never claim durable persistence before confirmation."
    )


def _association_prompt_signature(session: dict[str, Any]) -> str:
    association = session.get("project_association") or {}
    proposed = association.get("proposed_project") or {}
    value = {
        "status": association.get("status") or session.get("resolution_status"),
        "project_id": proposed.get("id"),
        "resolution_hash": association.get("resolution_hash"),
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _mark_association_prompted(
    event: dict[str, Any],
    state: dict[str, Any],
    session: dict[str, Any],
) -> None:
    state["association_prompt_signature"] = _association_prompt_signature(session)
    _write_state(event, state)


def _association_prompt_is_new(state: dict[str, Any], session: dict[str, Any]) -> bool:
    return state.get("association_prompt_signature") != _association_prompt_signature(
        session
    )


def _attention_context(briefing: Any) -> str:
    if not isinstance(briefing, dict) or not briefing.get("pending_count"):
        return ""
    lines = [
        "Project attention is pending. At the beginning of your response, surface this compact "
        "briefing to the user before continuing with their request. Do not claim an item was read, "
        "acknowledged or resolved unless the user explicitly says so.",
        str(briefing.get("headline") or "Pending project communication."),
    ]
    for entry in list(briefing.get("items") or [])[:3]:
        item = entry.get("item") if isinstance(entry, dict) else {}
        why_now = entry.get("why_now") if isinstance(entry, dict) else None
        if not isinstance(item, dict) or not item.get("title"):
            continue
        suffix = f" — {why_now}" if why_now else ""
        lines.append(f"- {item['title']}{suffix}")
    if len(list(briefing.get("items") or [])) > 3:
        lines.append(
            "- Additional pending communications are available through spm_attention_briefing."
        )
    lines.append(
        "Use spm_attention_state_update only after an explicit user instruction to acknowledge, "
        "defer, resolve or dismiss a receipt."
    )
    return "\n".join(lines)


def _hook_output(event_name: str, context: str, *, warning: str | None = None) -> None:
    payload: dict[str, Any] = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        },
    }
    if warning:
        payload["systemMessage"] = warning
    print(json.dumps(payload))


def _direct_turn_text(event: dict[str, Any], role: str) -> str | None:
    keys = (
        ("prompt", "user_prompt", "message", "content")
        if role == "user"
        else ("last_assistant_message", "assistant_message", "response", "content")
    )
    for key in keys:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_TURN_CHARS]
    return None


def _transcript_turn(event: dict[str, Any], role: str) -> str | None:
    transcript = event.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return None
    path = Path(transcript)
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - MAX_TRANSCRIPT_BYTES))
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(raw.splitlines()):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = _message_text(item, role)
        if text:
            return text[:MAX_TURN_CHARS]
    return None


def _message_text(item: dict[str, Any], role: str) -> str | None:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
    if payload.get("type") == "response_item" and isinstance(
        payload.get("payload"), dict
    ):
        payload = payload["payload"]
    if payload.get("role") != role:
        return None
    content = payload.get("content")
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    texts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        text = part.get("text") or part.get("input_text") or part.get("output_text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    return "\n".join(texts) or None


def _ingest(
    event: dict[str, Any], state: dict[str, Any], *, role: str
) -> dict[str, Any] | None:
    content = _direct_turn_text(event, role) or _transcript_turn(event, role)
    if not content:
        return None
    external_turn_id = str(event.get("turn_id") or "").strip()
    if not external_turn_id:
        external_turn_id = hashlib.sha256(f"{role}:{content}".encode()).hexdigest()
    return _rpc_call(
        "spm_agent_turn_ingest",
        {
            "session_id": state["spm_session_id"],
            "external_turn_id": external_turn_id,
            "role": role,
            "content": content,
            "workspace_hint": str(event.get("cwd") or "") or None,
            "actor_ref": "codex-user" if role == "user" else "codex-agent",
            "actor_role": "user" if role == "user" else "agent",
            "authority_mode": "advisory",
            "relevance_target": "Maintain durable memory for the active Codex project task.",
            "metadata": {
                "surface": "codex_plugin_hook",
                "model": str(event.get("model") or "unknown"),
            },
        },
    )


def handle(event: dict[str, Any]) -> None:
    event_name = str(event.get("hook_event_name") or "")
    state = _read_state(event)
    session, state = _start_or_resume(event, state)
    if event_name == "SessionStart":
        _log(event, status="ready", detail=session.get("resolution_status", "unknown"))
        _mark_association_prompted(event, state, session)
        _hook_output(event_name, _project_context(session))
        return
    if event_name == "UserPromptSubmit":
        result = _ingest(event, state, role="user")
        if result and result.get("status") in {
            "requires_project_confirmation",
            "bootstrap_required",
            "not_linked",
        }:
            current_session = result.get("session") or session
            context = _project_context(current_session)
            if _association_prompt_is_new(state, current_session):
                _mark_association_prompted(event, state, current_session)
                _log(event, status="requires_project_confirmation", detail=context)
                _hook_output(event_name, context)
            else:
                _log(
                    event,
                    status=result.get("status"),
                    detail="association prompt already surfaced",
                )
        else:
            _log(
                event,
                status=(result or {}).get("status", "no_content"),
                detail="user turn",
            )
        return
    if event_name == "Stop":
        result = _ingest(event, state, role="assistant")
        _log(
            event,
            status=(result or {}).get("status", "no_content"),
            detail="assistant turn",
        )
        return
    _log(event, status="ignored", detail=event_name)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise SpmHookError("Hook input must be a JSON object")
        handle(event)
        return 0
    except Exception as exc:  # noqa: BLE001 - lifecycle hooks must not block Codex
        event = locals().get("event") if isinstance(locals().get("event"), dict) else {}
        _log(event, status="error", detail=str(exc))
        event_name = str(event.get("hook_event_name") or "")
        if event_name in {"SessionStart", "UserPromptSubmit"}:
            _hook_output(
                event_name,
                "SPM lifecycle capture is unavailable for this turn. Do not claim that project memory was persisted.",
                warning="SPM did not persist this turn; Codex work can continue.",
            )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
