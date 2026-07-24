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
RECEIPT_MODE_ENV = "SPM_CODEX_RECEIPT_MODE"
CAPTURE_TRACE_ENV = "SPM_CODEX_CAPTURE_TRACE"
RECEIPT_MODES = {"discreet", "compact", "audit"}
CAPTURE_TRACE_MODES = {"off", "metadata", "full"}
SMART_PROMOTION_PENDING_REVIEW = "smart_promotion_pending_review"
MAX_TURN_CHARS = 100_000
MAX_TRANSCRIPT_BYTES = 4 * 1024 * 1024
MAX_RESOLUTION_CONTEXT_TURNS = 12
MAX_RESOLUTION_CONTEXT_CHARS = 36_000


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
    return _codex_env_value(path, TOKEN_ENV)


def _codex_env_value(path: Path, variable: str) -> str:
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
            prefix = f"{variable}="
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


def _capture_trace_mode() -> str:
    value = (
        os.environ.get(CAPTURE_TRACE_ENV, "").strip()
        or _codex_env_value(Path.home() / ".spm" / "codex.env", CAPTURE_TRACE_ENV)
        or "off"
    ).lower()
    return value if value in CAPTURE_TRACE_MODES else "off"


def _trace_capture(
    event: dict[str, Any],
    *,
    direction: str,
    label: str,
    text: str | None,
    source: str | None = None,
) -> None:
    """Write an opt-in, local-only diagnostic record of hook transport.

    ``full`` is intentionally explicit because it keeps the exact text locally
    for comparison. It never adds a diagnostic copy to SPM and the trace file
    remains owner-readable only. ``metadata`` provides source/length/hash
    evidence without retaining the text.
    """

    mode = _capture_trace_mode()
    if mode == "off":
        return
    value = text or ""
    entry: dict[str, Any] = {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "event": str(event.get("hook_event_name") or "unknown"),
        "session_hash": _session_key(event)[:16],
        "turn_hash": hashlib.sha256(str(event.get("turn_id") or "").encode()).hexdigest()[:16],
        "direction": direction,
        "label": label,
        "source": source,
        "character_count": len(value),
        "content_hash": hashlib.sha256(value.encode("utf-8")).hexdigest(),
    }
    if mode == "full":
        entry["content"] = value
    path = _plugin_data_dir() / "capture-trace.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _start_or_resume(
    event: dict[str, Any], state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    existing_id = state.get("spm_session_id")
    if existing_id:
        try:
            session = _rpc_call(
                "spm_agent_session_get",
                {
                    "session_id": existing_id,
                    "include_projects": True,
                    # Project context is refreshed after the previous answer
                    # has been captured. Do not make a new user prompt wait
                    # for hierarchical composition before Codex receives its
                    # mandatory receipt instruction.
                    "include_prompt_context": False,
                },
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
            _remember_response_language(event, state, session)
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
            "include_prompt_context": False,
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
    _remember_response_language(event, state, session)
    _write_state(event, state)
    return session, state


def _session_response_language(session: dict[str, Any]) -> str:
    association = (
        session.get("project_association")
        if isinstance(session.get("project_association"), dict)
        else {}
    )
    return _language_code(association.get("response_language"))


def _remember_response_language(
    event: dict[str, Any], state: dict[str, Any], session: dict[str, Any]
) -> None:
    state["response_language"] = _session_response_language(session)
    _write_state(event, state)


def _cached_project_context(state: dict[str, Any], session: dict[str, Any]) -> str:
    """Return the last composed project context when it still targets this project.

    The journal capture path must complete within Codex's hook deadline. The
    Stop lifecycle refreshes this snapshot after the completed work bundle has
    been evaluated, so the next prompt still receives a rich, current project
    context without coupling its receipt to LLM composition latency.
    """

    active = session.get("active_project") if isinstance(session, dict) else None
    active_id = str(active.get("id") or "") if isinstance(active, dict) else ""
    cached = str(state.get("cached_project_context") or "").strip()
    if cached and active_id and state.get("cached_project_id") == active_id:
        attention = _attention_context(session.get("attention_briefing"))
        return _combine_context(cached, attention)
    return _project_context(session)


def _refresh_cached_project_context(
    event: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any] | None:
    """Refresh the next-turn context after answer capture, never before it."""

    session_id = str(state.get("spm_session_id") or "").strip()
    if not session_id:
        return None
    try:
        session = _rpc_call(
            "spm_agent_session_get",
            {
                "session_id": session_id,
                "include_projects": True,
                "include_prompt_context": True,
            },
        )
    except SpmHookError as exc:
        _log(event, status="project_context_refresh_unavailable", detail=str(exc))
        return None
    active = session.get("active_project") if isinstance(session, dict) else None
    context = _prompt_context(session) if isinstance(session, dict) else ""
    if isinstance(active, dict) and active.get("id") and context:
        state["cached_project_id"] = str(active["id"])
        state["cached_project_context"] = context
    else:
        state.pop("cached_project_id", None)
        state.pop("cached_project_context", None)
    _remember_response_language(event, state, session)
    return session


def _prompt_context(session: dict[str, Any]) -> str:
    prompt_context = session.get("prompt_context")
    if not isinstance(prompt_context, dict):
        return ""
    active = session.get("active_project") or {}
    status = str(prompt_context.get("status") or "")
    if status == "unavailable":
        warnings = ", ".join(str(item) for item in prompt_context.get("warnings") or [])
        return (
            f"SPM project memory is active for project '{active.get('name')}' "
            f"({active.get('id')}), but SPM could not provide project context for this prompt"
            f"{': ' + warnings if warnings else ''}. Do not infer missing project memory."
        )
    if status != "provided":
        return ""
    lines = [
        (
            f"SPM provided rich project context for '{prompt_context.get('project_name') or active.get('name')}' "
            f"({prompt_context.get('project_id') or active.get('id')}). Use this as the project-memory context "
            "for ordinary recall, decisions and constraints. Keep writes in this project unless the user "
            "explicitly asks to list, compose or inject another authorized project."
        ),
        f"Context hash: {prompt_context.get('context_hash')}.",
    ]
    summary = str(prompt_context.get("summary") or "").strip()
    if summary:
        lines.append(f"Project memory summary: {summary[:1800]}")
    sections = [item for item in list(prompt_context.get("sections") or []) if isinstance(item, dict)]
    if sections:
        lines.append("Selected memory:")
        for section in sections[:6]:
            title = str(section.get("title") or section.get("node_key") or "memory").strip()
            text = str(section.get("summary") or "").strip()
            source_hash = str(section.get("source_hash") or "").strip()
            node_hash = str(section.get("node_hash") or "").strip()
            evidence = ", ".join(item for item in (source_hash[:12], node_hash[:12]) if item)
            suffix = f" [{evidence}]" if evidence else ""
            lines.append(f"- {title}: {text[:700]}{suffix}")
    temporal = [str(item) for item in list(prompt_context.get("temporal_signals") or []) if item]
    if temporal:
        lines.append("Temporal signals: " + "; ".join(temporal[:5]))
    authority = [str(item) for item in list(prompt_context.get("authority_signals") or []) if item]
    if authority:
        lines.append("Authority signals: " + "; ".join(authority[:5]))
    injected_count = int(prompt_context.get("injected_context_count") or 0)
    if injected_count:
        lines.append(
            f"{injected_count} explicit injected context source"
            f"{'s' if injected_count != 1 else ''} available for this task."
        )
    missing = [str(item) for item in list(prompt_context.get("missing_information") or []) if item]
    if missing:
        lines.append("Missing or uncertain project memory: " + "; ".join(missing[:5]))
    lines.append(
        "Do not reveal hidden/raw source bodies. Use hashes and source summaries as provenance evidence."
    )
    return "\n".join(lines)


def _project_context(session: dict[str, Any]) -> str:
    active = session.get("active_project") or {}
    projects = session.get("accessible_projects") or []
    association = session.get("project_association") or {}
    if active:
        context = _prompt_context(session) or (
            f"SPM project memory is active for project '{active.get('name')}' "
            f"({active.get('id')}). Keep ordinary recall and writes in this project. "
            "List or compose another authorized project only when the user explicitly asks."
        )
        default_material_instruction = (
            "If an authorized file, document, tool result, repository snapshot or endpoint response "
            "materially informs the work and is not already represented in project memory, call "
            "spm_agent_resource_handoff before the final response with its source reference, kind and "
            "a redacted body or accurate summary. SPM cannot inspect arbitrary host files, hidden tool "
            "output or endpoints itself. Do not hand off secrets or data outside the approved sharing scope."
        )
        source_contract = session.get("source_capture_contract") or {}
        material_instruction = str(
            source_contract.get("agent_instruction") or default_material_instruction
        )
        known_sources = list(source_contract.get("known_sources") or [])
        if known_sources:
            source_labels = [
                str(item.get("title") or item.get("source_ref") or "material source")
                for item in known_sources[:8]
            ]
            material_instruction += " Known governed sources: " + "; ".join(source_labels) + "."
        user_question = str(source_contract.get("user_question") or "").strip()
        if user_question:
            material_instruction += " Ask the user only when needed: " + user_question
        attention = _attention_context(session.get("attention_briefing"))
        parts = [context, material_instruction]
        if attention:
            parts.append(attention)
        return "\n\n".join(parts)
    if association.get("user_prompt") or association.get("status") in {
        "proposed",
        "requires_selection",
        "external_context_only",
    }:
        return _association_conversation_context(association)
    if association.get("status") == "skipped":
        return (
            "The user chose to continue this Codex task without persistent SPM project memory. "
            "Do not claim persistence. The user may explicitly select a project later."
        )
    if session.get("bootstrap"):
        return _association_conversation_context(association)
    names = ", ".join(str(project.get("name")) for project in projects[:12]) or "none"
    return (
        "SPM cannot safely select one project for this task yet. "
        f"Authorized projects: {names}. Ask the user once to choose a project, list the full catalog, "
        "or continue without persistent memory in SPM. Persist the answer with "
        "spm_agent_session_association_decide before claiming that memory was stored."
    )


def _association_conversation_context(association: dict[str, Any]) -> str:
    proposed = association.get("proposed_project")
    candidate = (
        {
            "id": str(proposed.get("id") or ""),
            "name": str(proposed.get("name") or ""),
            "confidence": association.get("confidence"),
        }
        if isinstance(proposed, dict)
        else None
    )
    actions = []
    for option in association.get("reply_options") or []:
        if not isinstance(option, dict):
            continue
        intent = str(option.get("intent") or "").strip()
        if not intent:
            continue
        actions.append(
            {
                "intent": intent,
                "project_id": str(option.get("project_id") or "") or None,
                "tool": str(option.get("tool") or "") or None,
            }
        )
    decision = {
        "status": str(association.get("status") or "requires_selection"),
        "candidate": candidate,
        "available_actions": actions,
    }
    return (
        "SPM has an unresolved project-memory association. The JSON below is canonical machine "
        "state, not user-facing copy. Do not quote, translate, or reproduce any server wording. "
        "Determine whether the user is resolving this decision. If they are not, answer the immediate "
        "request when safe, then append one concise conversational question in the same language as "
        "the current user conversation and your substantive answer. Do not put that question at the "
        "top, do not turn it into a status note, and do not show a bare confirmation URL. Offer only "
        "the available actions. If there is a candidate, state it is only a possible match and include "
        "its calibrated confidence. Keep asking in later turns until the user confirms, rejects, selects, "
        "creates, or skips. A hook context being emitted is not a user-visible decision. Interpret the "
        "user's answer semantically, never with string matching. If the user chooses create, call "
        "spm_project_bootstrap_preview with a safe inventory and source-grounded evidence from a "
        "bounded inspection. Follow a specific evidence_assessment.agent_instruction by inspecting "
        "only authorized resources and calling spm_project_bootstrap_evidence_submit. Never crawl "
        "the workspace, expose secrets, or use absolute local paths as shared identity. Use the "
        "private URL only for authenticated confirmation. Never claim persistent project memory "
        "before confirmation.\n"
        f"SPM association facts: {json.dumps(decision, sort_keys=True, ensure_ascii=True)}"
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


def _association_requires_decision(session: dict[str, Any]) -> bool:
    if session.get("active_project"):
        return False
    association = session.get("project_association") or {}
    return bool(
        session.get("bootstrap")
        or association.get("user_prompt")
        or association.get("status")
        in {"proposed", "requires_selection", "external_context_only"}
        or session.get("resolution_status")
        in {"requires_project_confirmation", "bootstrap_required", "not_linked"}
    )


def _association_turn_key(event: dict[str, Any]) -> str:
    turn_id = str(event.get("turn_id") or "").strip()
    if turn_id:
        return turn_id
    value = {
        "session_id": event.get("session_id"),
        "prompt": _direct_turn_text(event, "user"),
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _mark_association_context_delivered(
    event: dict[str, Any],
    state: dict[str, Any],
    session: dict[str, Any],
) -> None:
    state["association_prompt_signature"] = _association_prompt_signature(session)
    state["association_prompt_turn_id"] = _association_turn_key(event)
    _write_state(event, state)


def _association_context_is_new_for_turn(
    event: dict[str, Any], state: dict[str, Any], session: dict[str, Any]
) -> bool:
    return (
        state.get("association_prompt_turn_id") != _association_turn_key(event)
        or state.get("association_prompt_signature")
        != _association_prompt_signature(session)
    )


def _clear_association_context_delivery(event: dict[str, Any], state: dict[str, Any]) -> None:
    if "association_prompt_turn_id" not in state:
        return
    state.pop("association_prompt_turn_id", None)
    _write_state(event, state)


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


def _association_notice(session: dict[str, Any]) -> str:
    """A concise visible companion to the model-only association instruction."""

    association = session.get("project_association") or {}
    prompt = str(association.get("user_prompt") or association.get("message") or "").strip()
    if prompt:
        return f"SPM project memory needs a decision: {prompt}"
    return "SPM project memory needs a project decision before it can persist this task."


def _hook_output(
    event_name: str,
    context: str,
    *,
    warning: str | None = None,
    event: dict[str, Any] | None = None,
) -> None:
    # The hook is the sole transport boundary that can show the exact context
    # handed back to Codex. This remains local-only and explicitly opt-in.
    _trace_capture(
        event or {"hook_event_name": event_name},
        direction="sent_to_codex",
        label="hookSpecificOutput.additionalContext",
        text=context,
        source="hook_output",
    )
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


def _receipt_mode(session: dict[str, Any]) -> str:
    configured = os.environ.get(RECEIPT_MODE_ENV, "").strip().lower()
    if configured in RECEIPT_MODES:
        return configured
    metadata = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
    server_mode = str(metadata.get("memory_receipt_mode") or "").strip().lower()
    server_mode_explicit = bool(metadata.get("memory_receipt_mode_explicit"))
    # Device tokens issued before compact receipts used an implicit discreet
    # default.  Do not let that legacy default silently suppress the prompt
    # contract; an explicit discreet preference is still honoured.
    if server_mode == "discreet" and not server_mode_explicit:
        return "compact"
    return server_mode if server_mode in RECEIPT_MODES else "compact"


def _normalized_receipt(result: dict[str, Any] | None, *, role: str) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    receipt = result.get("receipt")
    if isinstance(receipt, dict):
        normalized = {**receipt, "role": role, "turn_id": receipt.get("turn_id") or result.get("turn_id")}
        if normalized.get("persistence_status") == "pending_review":
            normalized["persistence_status"] = SMART_PROMOTION_PENDING_REVIEW
        return normalized
    project = result.get("project") if isinstance(result.get("project"), dict) else {}
    triage = result.get("triage") if isinstance(result.get("triage"), dict) else {}
    decision = triage.get("decision") if isinstance(triage.get("decision"), dict) else {}
    status = str(result.get("status") or "unknown")
    persistence_status = (
        SMART_PROMOTION_PENDING_REVIEW
        if triage.get("requires_review")
        else "applied"
        if triage.get("applied") and decision.get("action") != "discard"
        else "triage_failed"
        if status == "triage_failed"
        else "metadata_only"
        if status == "metadata_only"
        else "not_created"
    )
    return {
        "role": role,
        "capture_status": status,
        "journal_status": "recorded" if result.get("journal_entry_id") else "not_recorded",
        "persistence_status": persistence_status,
        "project_id": project.get("id"),
        "project_name": project.get("name"),
        "journal_entry_id": result.get("journal_entry_id"),
        "turn_id": result.get("turn_id"),
        "source_ref": result.get("source_ref"),
        "triage_action": decision.get("action"),
        "temporal_layer": decision.get("temporal_layer"),
        "temporal_event_id": (triage.get("temporal_event") or {}).get("id")
        if isinstance(triage.get("temporal_event"), dict)
        else None,
        "decision_hash": triage.get("decision_hash"),
        "triage_error_code": result.get("triage_error_code"),
        "display_language": _result_receipt_language(result),
    }


def _is_project_capture_receipt(receipt: dict[str, Any] | None) -> bool:
    """Render receipts only for an actual project-scoped journal capture.

    Association is a conversational decision, not a memory write. A session
    without an active project must not produce a footer with null identifiers
    or imply that project memory was considered and discarded.
    """

    if not isinstance(receipt, dict):
        return False
    return bool(
        receipt.get("project_id")
        and str(receipt.get("journal_status") or "") in {"recorded", "existing"}
    )


def _result_receipt_language(result: dict[str, Any]) -> str:
    """Use SPM's resolved language when it is present; never infer from strings here."""

    session = result.get("session") if isinstance(result.get("session"), dict) else {}
    association = (
        session.get("project_association")
        if isinstance(session.get("project_association"), dict)
        else {}
    )
    return _language_code(association.get("response_language"))


def _language_code(value: Any) -> str:
    value = str(value or "").strip().casefold()
    if value in {"es", "es-es"}:
        return "es"
    if value in {"ca", "ca-es"}:
        return "ca"
    return "en"


def _store_iteration_receipt(
    event: dict[str, Any],
    state: dict[str, Any],
    *,
    role: str,
    result: dict[str, Any] | None,
) -> None:
    receipt = _normalized_receipt(result, role=role)
    if not _is_project_capture_receipt(receipt):
        return
    turn_key = _association_turn_key(event)
    pending = state.get("iteration_receipt")
    if not isinstance(pending, dict) or pending.get("turn_key") != turn_key:
        pending = {"turn_key": turn_key, "receipts": []}
    receipts = [
        item
        for item in list(pending.get("receipts") or [])
        if isinstance(item, dict) and item.get("role") != role
    ]
    receipts.append(receipt)
    state["iteration_receipt"] = {"turn_key": turn_key, "receipts": receipts}
    _write_state(event, state)


def _take_iteration_receipts(
    event: dict[str, Any], state: dict[str, Any]
) -> list[dict[str, Any]]:
    pending = state.pop("iteration_receipt", None)
    _write_state(event, state)
    if not isinstance(pending, dict):
        return []
    return [item for item in list(pending.get("receipts") or []) if isinstance(item, dict)]


def _report_receipt_delivery(
    event: dict[str, Any],
    state: dict[str, Any],
    *,
    receipt: dict[str, Any],
    delivery_event: str,
) -> None:
    """Persist lifecycle evidence without attempting to inspect Codex UI output."""

    session_id = str(state.get("spm_session_id") or "").strip()
    if not session_id:
        return
    payload: dict[str, Any] = {"session_id": session_id, "event": delivery_event}
    if receipt.get("turn_id"):
        payload["turn_id"] = receipt["turn_id"]
    if receipt.get("source_ref"):
        payload["source_ref"] = receipt["source_ref"]
    try:
        _rpc_call("spm_agent_session_receipt_delivery_report", payload)
    except Exception as exc:  # noqa: BLE001 - delivery telemetry must remain fail-open
        # Do not turn a user task into a failure. The session receipt endpoint
        # will accurately report the absence of delivery evidence.
        _log(event, status="receipt_delivery_unavailable", detail=str(exc))


def _combine_context(*parts: str | None) -> str:
    return "\n\n".join(str(part).strip() for part in parts if str(part or "").strip())


def _prompt_receipt_facts(
    mode: str, receipt: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Return canonical receipt facts known before Codex starts answering.

    The hook must not choose the language of a conversational response. It
    supplies evidence only; Codex renders the final receipt in the language it
    uses for the substantive answer. A UserPromptSubmit hook can attest to the
    input it just ingested, but not to the assistant response captured later by
    Stop.
    """

    if not _is_project_capture_receipt(receipt):
        return None
    persistence_status = str(receipt.get("persistence_status") or "not_created")
    if persistence_status == "pending_review":
        persistence_status = SMART_PROMOTION_PENDING_REVIEW
    if mode == "discreet" and persistence_status not in {
        SMART_PROMOTION_PENDING_REVIEW,
        "triage_failed",
    }:
        return None

    journal_status = str(receipt.get("journal_status") or "unknown")
    if journal_status in {"recorded", "existing"}:
        journal_outcome = "input_saved"
    elif journal_status == "not_recorded":
        journal_outcome = "input_not_saved"
    else:
        journal_outcome = "input_status_unknown"

    memory_outcomes = {
        "applied": "project_memory_updated",
        SMART_PROMOTION_PENDING_REVIEW: "memory_saved_without_automatic_promotion",
        "triage_failed": "smart_memory_classification_not_completed",
        "metadata_only": "source_saved_as_evidence",
        "not_applicable": "no_persistent_project_memory_needed",
    }
    receipt_hash = _short_identifier(
        receipt.get("entry_hash") or receipt.get("decision_hash")
    )
    facts = {
        "turns": 1,
        "journal_outcome": journal_outcome,
        "project_name": receipt.get("project_name"),
        "temporal_layer": receipt.get("temporal_layer"),
        "hash": receipt_hash,
    }
    if persistence_status != "analysis_pending":
        facts["memory_outcome"] = memory_outcomes.get(
            persistence_status, "memory_saved_without_automatic_promotion"
        )
    return facts


def _response_receipt_contract(facts: dict[str, Any]) -> str:
    """Give Codex a truthful, same-turn receipt contract.

    This makes the receipt part of the normal answer without asking the model
    to invent a hash for an assistant response that has not been emitted. Stop
    remains the authoritative capture point for that response.
    """

    return (
        "SPM response footer requirement: this is mandatory for the current turn. The current "
        "user input has already been recorded. Complete the substantive request first, then end "
        "your user-facing response with exactly one compact SPM receipt as its final non-empty "
        "line, in the same language as your substantive response. Do not omit it, even for a "
        "short answer. Preserve `SPM`, the project name and the hash exactly. "
        "The receipt facts below are canonical identifiers, not user-facing copy: translate "
        "their labels naturally into the response language without adding or omitting facts. "
        f"Receipt facts: {json.dumps(facts, sort_keys=True, ensure_ascii=True)}\n"
        "This receipt attests to the input only. Do not claim that your final answer "
        "has already been captured or invent another hash. The lifecycle Stop hook "
        "will capture and attest to the exact final answer after it is sent. For "
        "meaningful implemented work, still call spm_agent_action_report before the "
        "final answer and report only evidence returned by that tool."
    )


def _short_identifier(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned[:12] if cleaned else None


def _receipt_journal_outcome(
    receipts: list[dict[str, Any]],
    language: str,
) -> str:
    explicit_message = next(
        (
            str(item["source_message"]).strip()
            for item in reversed(receipts)
            if str(item.get("source_message") or "").strip()
        ),
        None,
    )
    if explicit_message:
        return explicit_message
    journal_statuses = {str(item.get("journal_status") or "") for item in receipts}
    if journal_statuses & {"recorded", "existing"}:
        return _localized_receipt_text(language, en="input saved", es="entrada guardada", ca="entrada desada")
    if journal_statuses == {"not_recorded"}:
        return _localized_receipt_text(language, en="input not saved", es="entrada no guardada", ca="entrada no desada")
    return _localized_receipt_text(
        language,
        en="input status unavailable",
        es="estado de la entrada no disponible",
        ca="estat de l'entrada no disponible",
    )


def _receipt_memory_outcome(
    persistence: list[str],
    receipts: list[dict[str, Any]],
    language: str,
) -> str | None:
    completed_receipts = [
        item
        for item in receipts
        if str(item.get("persistence_status") or "") != "analysis_pending"
    ]
    if not completed_receipts:
        return None
    explicit_message = next(
        (
            str(item["memory_message"]).strip()
            for item in reversed(completed_receipts)
            if str(item.get("memory_message") or "").strip()
        ),
        None,
    )
    if explicit_message:
        return explicit_message
    persistence = [value for value in persistence if value != "analysis_pending"]
    if "triage_failed" in persistence:
        return _localized_receipt_text(
            language,
            en="smart memory classification not completed",
            es="clasificación inteligente de memoria no completada",
            ca="classificació intel·ligent de memòria no completada",
        )
    if SMART_PROMOTION_PENDING_REVIEW in persistence:
        return _localized_receipt_text(
            language,
            en="memory saved without automatic promotion",
            es="memoria guardada sin promoción automática",
            ca="memòria desada sense promoció automàtica",
        )
    if "applied" in persistence:
        return _localized_receipt_text(
            language,
            en="project memory updated",
            es="memoria del proyecto actualizada",
            ca="memòria del projecte actualitzada",
        )
    if all(item.get("capture_status") == "duplicate" for item in receipts):
        return _localized_receipt_text(
            language,
            en="already saved",
            es="ya guardada",
            ca="ja desada",
        )
    if all(value == "metadata_only" for value in persistence):
        return _localized_receipt_text(
            language,
            en="source saved as evidence",
            es="fuente guardada como evidencia",
            ca="font desada com a evidència",
        )
    if any(item.get("journal_status") in {"recorded", "existing"} for item in receipts):
        return _localized_receipt_text(
            language,
            en="memory saved without automatic promotion",
            es="memoria guardada sin promoción automática",
            ca="memòria desada sense promoció automàtica",
        )
    return _localized_receipt_text(
        language,
        en="no persistent project memory needed",
        es="no se necesita memoria persistente de proyecto",
        ca="no cal memòria persistent de projecte",
    )


def _localized_receipt_text(language: str, *, en: str, es: str, ca: str) -> str:
    if language == "es":
        return es
    if language == "ca":
        return ca
    return en


def _localized_input_label(language: str) -> str:
    return _localized_receipt_text(
        language,
        en="input",
        es="entrada",
        ca="entrada",
    )


def _localized_temporal_layer(layer: str, language: str) -> str:
    if language == "en":
        return layer
    labels = {
        "original": ("original", "original"),
        "working": ("trabajo", "treball"),
        "current": ("actual", "actual"),
        "history": ("historial", "històric"),
    }
    localized = labels.get(layer)
    if localized is None:
        return layer
    return localized[0] if language == "es" else localized[1]


def _receipt_summary(mode: str, receipts: list[dict[str, Any]]) -> str | None:
    if not receipts:
        return None
    persistence = [str(item.get("persistence_status") or "not_created") for item in receipts]
    persistence = [
        SMART_PROMOTION_PENDING_REVIEW if value == "pending_review" else value
        for value in persistence
    ]
    if mode == "discreet" and not any(
        value in {SMART_PROMOTION_PENDING_REVIEW, "triage_failed"} for value in persistence
    ):
        return None
    project_name = next(
        (str(item["project_name"]) for item in reversed(receipts) if item.get("project_name")),
        None,
    )
    latest_hash = next(
        (
            _short_identifier(item.get("entry_hash") or item.get("decision_hash"))
            for item in reversed(receipts)
            if item.get("entry_hash") or item.get("decision_hash")
        ),
        None,
    )
    layers = list(
        dict.fromkeys(
            str(item["temporal_layer"])
            for item in receipts
            if item.get("temporal_layer")
        )
    )
    language = next(
        (
            str(item["display_language"])
            for item in reversed(receipts)
            if item.get("display_language") in {"en", "es", "ca"}
        ),
        "en",
    )
    journal_outcome = _receipt_journal_outcome(receipts, language)
    memory_outcome = _receipt_memory_outcome(persistence, receipts, language)
    rendered_layers = [_localized_temporal_layer(layer, language) for layer in layers]
    if mode != "audit":
        turn_label = _localized_turn_label(language, len(receipts))
        parts = [
            "SPM",
            f"{len(receipts)} {turn_label}",
            journal_outcome,
        ]
        if memory_outcome:
            parts.append(memory_outcome)
        if project_name:
            parts.append(project_name)
        if rendered_layers:
            parts.append("/".join(rendered_layers))
        if latest_hash:
            parts.append(f"hash {latest_hash}")
        return " · ".join(parts)

    project_id = next(
        (str(item["project_id"]) for item in reversed(receipts) if item.get("project_id")),
        None,
    )
    heading = "SPM receipt"
    if project_name:
        heading += f" · {project_name}"
    if project_id:
        heading += f" ({project_id})"
    lines = [heading]
    for item in receipts:
        item_persistence = str(item.get("persistence_status") or "unknown")
        if item_persistence == "pending_review":
            item_persistence = SMART_PROMOTION_PENDING_REVIEW
        item_memory_message = str(item.get("memory_message") or "").strip()
        fields = [str(item.get("role") or "turn")]
        item_memory_outcome = item_memory_message or _receipt_memory_outcome(
            [item_persistence],
            [item],
            _language_code(item.get("display_language")),
        )
        if item_memory_outcome:
            fields.append(item_memory_outcome)
        if item.get("temporal_layer"):
            fields.append(
                _localized_temporal_layer(
                    str(item["temporal_layer"]),
                    _language_code(item.get("display_language")),
                )
            )
        if item.get("journal_entry_id"):
            fields.append(f"journal {_short_identifier(item['journal_entry_id'])}")
        if item.get("temporal_event_id"):
            fields.append(f"event {_short_identifier(item['temporal_event_id'])}")
        if item.get("decision_hash"):
            fields.append(f"decision {_short_identifier(item['decision_hash'])}")
        if item.get("entry_hash"):
            fields.append(f"entry {_short_identifier(item['entry_hash'])}")
        lines.append(" · ".join(fields))
    lines.append("Hashes attest to integrity and provenance, not semantic truth.")
    return "\n".join(lines)


def _localized_turn_label(language: str, count: int) -> str:
    if language == "es":
        return "turno capturado" if count == 1 else "turnos capturados"
    if language == "ca":
        return "torn capturat" if count == 1 else "torns capturats"
    return "turn captured" if count == 1 else "turns captured"


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


def _turn_text_with_source(event: dict[str, Any], role: str) -> tuple[str | None, str | None]:
    direct = _direct_turn_text(event, role)
    if direct:
        return direct, "hook_event"
    transcript = _transcript_turn(event, role)
    if transcript:
        return transcript, "transcript"
    return None, None


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
    event: dict[str, Any],
    state: dict[str, Any],
    *,
    role: str,
    external_turn_id: str | None = None,
) -> dict[str, Any] | None:
    content, source = _turn_text_with_source(event, role)
    if not content:
        return None
    turn_id = str(external_turn_id or event.get("turn_id") or "").strip()
    if not turn_id:
        turn_id = hashlib.sha256(f"{role}:{content}".encode()).hexdigest()
    _trace_capture(
        event,
        direction="received_from_codex",
        label=f"{role}_turn",
        text=content,
        source=source,
    )
    arguments = {
        "session_id": state["spm_session_id"],
        "external_turn_id": turn_id,
        "role": role,
        "content": content,
        "workspace_hint": str(event.get("cwd") or "") or None,
        "conversation_context": _resolution_context_for_turn(
            state,
            role=role,
            content=content,
        ),
        "actor_ref": "codex-user" if role == "user" else "codex-agent",
        "actor_role": "user" if role == "user" else "agent",
        "authority_mode": "advisory",
        "relevance_target": "Maintain persistent memory for the active Codex project task.",
        # Source capture and delivery of the final-response receipt must stay
        # within the host hook deadline. The completed work bundle and the
        # next-turn context snapshot perform the expensive LLM work after the
        # answer is available.
        "analysis_mode": "deferred",
        "include_prompt_context": False,
        "response_language": state.get("response_language"),
        "metadata": {
            "surface": "codex_plugin_hook",
            "model": str(event.get("model") or "unknown"),
        },
    }
    _trace_capture(
        event,
        direction="sent_to_spm",
        label="spm_agent_turn_ingest.content",
        text=content,
        source=source,
    )
    result = _rpc_call(
        "spm_agent_turn_ingest",
        arguments,
    )
    _remember_resolution_turn(state, role=role, content=content)
    _write_state(event, state)
    return result


def _resolution_context_for_turn(
    state: dict[str, Any], *, role: str, content: str
) -> list[dict[str, str]]:
    """Return bounded local task history for LLM-first project resolution.

    This transport-only history lets a terse follow-up retain the identity
    established in earlier conversation. It is neither SPM project memory nor
    a lexical resolver; SPM's LLM receives it as labelled evidence.
    """

    history = state.get("resolution_history")
    turns = [
        {"role": str(item.get("role")), "content": str(item.get("content"))}
        for item in history
        if isinstance(item, dict)
        # A project resolver must use what the user has said about the work,
        # never an earlier agent-created association prompt as project evidence.
        # Assistant turns remain in the append-only capture journal; they are
        # intentionally excluded from this transient resolver input.
        and str(item.get("role")) == "user"
        and str(item.get("content") or "").strip()
    ] if isinstance(history, list) else []
    if role == "user":
        turns.append({"role": role, "content": content})
    return _bounded_resolution_context(turns)


def _remember_resolution_turn(state: dict[str, Any], *, role: str, content: str) -> None:
    # The agent response is captured by SPM's journal and work bundle. It is
    # not retained as resolver evidence: an agent can quote a prior candidate
    # or association question, which must never make that candidate look like
    # user-confirmed project identity on a later turn.
    if role != "user":
        return
    history = _resolution_context_for_turn(state, role=role, content=content)
    state["resolution_history"] = history


def _bounded_resolution_context(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    used = 0
    for turn in reversed(turns[-MAX_RESOLUTION_CONTEXT_TURNS:]):
        clean = str(turn.get("content") or "").strip()
        if not clean:
            continue
        remaining = MAX_RESOLUTION_CONTEXT_CHARS - used
        if remaining <= 0:
            break
        clipped = clean[:remaining]
        kept.append({"role": str(turn.get("role") or "user"), "content": clipped})
        used += len(clipped)
    return list(reversed(kept))


def _remember_pending_work(
    event: dict[str, Any], state: dict[str, Any], *, content: str
) -> None:
    """Keep one transient prompt until Stop can bind the matching final answer.

    The state file is 0600 and the value is deleted after finalization. The
    canonical durable source remains the SPM journal; this is transport state,
    not a second project-memory store.
    """

    state["pending_work"] = {
        "external_turn_id": str(event.get("turn_id") or hashlib.sha256(content.encode()).hexdigest()),
        "user_content": content,
        "user_content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }
    _write_state(event, state)


def _finalize_pending_work(
    event: dict[str, Any], state: dict[str, Any], *, assistant_content: str
) -> dict[str, Any] | None:
    pending = state.get("pending_work")
    if not isinstance(pending, dict) or not str(pending.get("user_content") or "").strip():
        return None
    external_turn_id = str(pending.get("external_turn_id") or event.get("turn_id") or "").strip()
    if not external_turn_id:
        return None
    arguments = {
        "session_id": state["spm_session_id"],
        "external_turn_id": external_turn_id,
        "user_content": str(pending["user_content"]),
        "assistant_content": assistant_content,
        "evidence": {},
        "apply": True,
        "response_language": state.get("response_language"),
    }
    _trace_capture(
        event,
        direction="sent_to_spm",
        label="spm_agent_work_bundle_finalize.user_content",
        text=arguments["user_content"],
        source="pending_work_state",
    )
    _trace_capture(
        event,
        direction="sent_to_spm",
        label="spm_agent_work_bundle_finalize.assistant_content",
        text=assistant_content,
        source="hook_event_or_transcript",
    )
    result = _rpc_call("spm_agent_work_bundle_finalize", arguments)
    state.pop("pending_work", None)
    _write_state(event, state)
    return result


def handle(event: dict[str, Any]) -> None:
    # Codex hooks historically provide ``hook_event_name``.  Accept the
    # documented event-type alias as well so a host-side transport update does
    # not turn a valid lifecycle invocation into a false outage.
    event_name = _event_name(event)
    state = _read_state(event)
    session, state = _start_or_resume(event, state)
    if event_name == "SessionStart":
        _log(event, status="ready", detail=session.get("resolution_status", "unknown"))
        # A session can carry a proposal created before the latest connector
        # version or before the current task supplied enough evidence. Do not
        # show that proposal on startup: it would be evaluated without the
        # user's current prompt and can leak into the answer before the actual
        # task starts. UserPromptSubmit resolves the association from the
        # captured prompt and is the only lifecycle point that may ask the
        # user to choose, create, or skip project memory.
        context = _project_context(session) if session.get("active_project") else ""
        _hook_output(event_name, context, event=event)
        return
    if event_name == "UserPromptSubmit":
        result = _ingest(event, state, role="user")
        user_text, _ = _turn_text_with_source(event, "user")
        if result and result.get("status") in {"captured", "triaged", "duplicate"} and user_text:
            _remember_pending_work(event, state, content=user_text)
        if result and result.get("status") in {
            "requires_project_confirmation",
            "bootstrap_required",
            "not_linked",
        }:
            _store_iteration_receipt(event, state, role="user", result=result)
            current_session = result.get("session") or session
            _remember_response_language(event, state, current_session)
            context = _project_context(current_session)
            input_receipt = _prompt_receipt_facts(
                _receipt_mode(current_session),
                _normalized_receipt(result, role="user"),
            )
            if input_receipt:
                context = _combine_context(
                    context,
                    _response_receipt_contract(input_receipt),
                )
                _report_receipt_delivery(
                    event,
                    state,
                    receipt=_normalized_receipt(result, role="user") or {},
                    delivery_event="instruction_delivered",
                )
            # Keep surfacing pending association decisions until SPM receives an
            # explicit semantic decision. A prior hook delivery only proves that
            # Codex received context; it does not prove that the user saw or
            # answered the project-memory question.
            _mark_association_context_delivered(event, state, current_session)
            _log(event, status="requires_project_confirmation", detail=context)
            _hook_output(
                event_name,
                context,
                event=event,
            )
        else:
            _store_iteration_receipt(event, state, role="user", result=result)
            current_session = (result or {}).get("session") or session
            _remember_response_language(event, state, current_session)
            input_receipt = _prompt_receipt_facts(
                _receipt_mode(current_session),
                _normalized_receipt(result, role="user"),
            )
            prompt_context = (
                _cached_project_context(state, current_session)
                if (current_session.get("active_project") if isinstance(current_session, dict) else None)
                else None
            )
            if input_receipt:
                _log(
                    event,
                    status=(result or {}).get("status", "no_content"),
                    detail="user turn with same-turn receipt contract",
                )
                _hook_output(
                    event_name,
                    _combine_context(
                        prompt_context,
                        _response_receipt_contract(input_receipt),
                    ),
                    event=event,
                )
                _report_receipt_delivery(
                    event,
                    state,
                    receipt=_normalized_receipt(result, role="user") or {},
                    delivery_event="instruction_delivered",
                )
                return
            if prompt_context:
                _log(
                    event,
                    status=(result or {}).get("status", "no_content"),
                    detail="user turn with project context",
                )
                _hook_output(event_name, prompt_context, event=event)
                return
            _log(
                event,
                status=(result or {}).get("status", "no_content"),
                detail="user turn",
            )
        return
    if event_name == "Stop":
        pending_work = state.get("pending_work")
        paired_turn_id = (
            str(pending_work.get("external_turn_id") or "").strip()
            if isinstance(pending_work, dict)
            else None
        )
        result = _ingest(
            event,
            state,
            role="assistant",
            external_turn_id=paired_turn_id,
        )
        assistant_text, _ = _turn_text_with_source(event, "assistant")
        bundle = None
        if result and result.get("status") in {"captured", "triaged", "duplicate"} and assistant_text:
            try:
                bundle = _finalize_pending_work(event, state, assistant_content=assistant_text)
            except SpmHookError as exc:
                # Keep the pending source only for a later Stop retry. This never
                # blocks Codex and is visible in local lifecycle diagnostics.
                _log(event, status="work_bundle_unavailable", detail=str(exc))
        current_session = (result or {}).get("session") or session
        _remember_response_language(event, state, current_session)
        _store_iteration_receipt(event, state, role="assistant", result=result)
        refreshed = _refresh_cached_project_context(event, state)
        if refreshed is not None:
            current_session = refreshed
        if _association_requires_decision(current_session):
            # A previous injected instruction can be missed by the model. Let the
            # next user turn receive it again, without duplicating one turn.
            _clear_association_context_delivery(event, state)
        completed_receipts = _take_iteration_receipts(event, state)
        for receipt in completed_receipts:
            if receipt.get("role") == "user":
                _report_receipt_delivery(
                    event,
                    state,
                    receipt=receipt,
                    delivery_event="finalization_observed",
                )
        # Stop runs after Codex has emitted its answer.  It is the authoritative
        # capture point for the response, but cannot reliably add a visible
        # footer to that already-completed answer.  The UserPromptSubmit hook
        # carries the receipt contract for the model; Stop only finalizes the
        # source capture and keeps local lifecycle diagnostics.
        _log(
            event,
            status=(result or {}).get("status", "no_content"),
            detail="assistant turn with work bundle" if bundle else "assistant turn",
        )
        return
    _log(event, status="ignored", detail=event_name)


def main() -> int:
    event: dict[str, Any] = {}
    try:
        raw_event = sys.stdin.read()
        # Some Codex host paths invoke registered commands without lifecycle
        # JSON.  They are not capture failures and must not inject a misleading
        # "unavailable" instruction into the agent conversation.
        if not raw_event.strip():
            _log(event, status="ignored_empty_input", detail="no lifecycle event payload")
            return 0
        decoded = json.loads(raw_event)
        if not isinstance(decoded, dict):
            raise SpmHookError("Hook input must be a JSON object")
        event = decoded
        if not _event_name(event):
            _log(event, status="ignored_unknown_event", detail="missing lifecycle event name")
            return 0
        handle(event)
        return 0
    except Exception as exc:  # noqa: BLE001 - lifecycle hooks must not block Codex
        _log(event, status="error", detail=str(exc))
        event_name = _event_name(event)
        # Stop is invoked after Codex has already published its response.  An
        # additionalContext there cannot repair a missing receipt and can only
        # pollute the next lifecycle phase with a stale failure message.  The
        # UserPromptSubmit hook is the sole user-visible receipt instruction
        # boundary; Stop remains capture/diagnostics only.
        if event_name in {"SessionStart", "UserPromptSubmit"}:
            _hook_output(
                event_name,
                "SPM lifecycle capture is unavailable for this turn. Do not claim that project memory was persisted.",
                event=event,
            )
        return 0


def _event_name(event: dict[str, Any]) -> str:
    return str(event.get("hook_event_name") or event.get("type") or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
