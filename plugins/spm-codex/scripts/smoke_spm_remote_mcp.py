#!/usr/bin/env python3
"""Run an end-to-end smoke test against the hosted SPM remote MCP endpoint."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_ENDPOINT = "https://getspm.com/v1/mcp"
DEFAULT_TOKEN_ENV_VAR = "SPM_CODEX_MCP_TOKEN"
REQUIRED_TOOLS = {
    "spm_projects_list",
    "spm_project_resolve",
    "spm_cross_project_context_pack",
    "spm_multi_project_context_pack",
    "spm_agent_session_start",
    "spm_agent_session_get",
    "spm_agent_session_set_project",
    "spm_temporal_state",
    "spm_temporal_event_create",
    "spm_temporal_context_pack",
    "spm_temporal_context_pack_verify",
    "spm_temporal_graph_query",
    "spm_context_boundary_pack",
    "spm_agent_preflight",
    "spm_agent_policy_pack",
    "spm_agent_action_report",
}
FORBIDDEN_TOOL_FRAGMENTS = (
    "billing",
    "checkout",
    "invoice_payment",
    "customer_portal",
    "delete_project",
)
VALID_PREFLIGHT_DECISIONS = {"allow", "warn", "requires_approval", "block"}
VALID_ACTION_REPORT_STATUSES = {"valid", "violations_opened", "incomplete", "blocked"}


class SmokeFailure(RuntimeError):
    """Raised when the remote MCP endpoint responds but violates the smoke contract."""


def http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))


def endpoint_with_profile(endpoint: str, profile: str) -> str:
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}{urllib.parse.urlencode({'profile': profile})}"


def rpc(
    endpoint: str,
    *,
    profile: str,
    token: str,
    method: str,
    params: dict[str, Any] | None = None,
    request_id: int = 1,
    timeout: int = 20,
) -> dict[str, Any]:
    result = http_json(
        "POST",
        endpoint_with_profile(endpoint, profile),
        token=token,
        payload={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
        timeout=timeout,
    )
    if not isinstance(result, dict):
        raise SmokeFailure(f"unexpected JSON-RPC response for {method}: {result!r}")
    if "error" in result:
        raise SmokeFailure(f"{method} failed: {result['error']}")
    return result


def call_tool(
    endpoint: str,
    *,
    profile: str,
    token: str,
    name: str,
    arguments: dict[str, Any],
    request_id: int,
    timeout: int,
) -> dict[str, Any]:
    response = rpc(
        endpoint,
        profile=profile,
        token=token,
        method="tools/call",
        params={"name": name, "arguments": arguments},
        request_id=request_id,
        timeout=timeout,
    )
    result = response.get("result")
    if not isinstance(result, dict):
        raise SmokeFailure(f"{name} returned no JSON-RPC result object")
    if result.get("isError") is True:
        raise SmokeFailure(f"{name} returned MCP tool error")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise SmokeFailure(f"{name} returned no structuredContent object")
    return structured


def metadata_tool_names(metadata: dict[str, Any]) -> set[str]:
    return {
        item["name"]
        for item in metadata.get("tools", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def validate_metadata(metadata: dict[str, Any]) -> list[str]:
    names = metadata_tool_names(metadata)
    missing = sorted(REQUIRED_TOOLS - names)
    forbidden = sorted(name for name in names if any(fragment in name for fragment in FORBIDDEN_TOOL_FRAGMENTS))
    errors: list[str] = []
    if metadata.get("kind") != "spm.remote_mcp_metadata":
        errors.append("metadata kind is not spm.remote_mcp_metadata")
    if metadata.get("requires_auth") is not True:
        errors.append("metadata does not require auth")
    security = metadata.get("security") if isinstance(metadata.get("security"), dict) else {}
    expected_security = {
        "project_scoped": "supported",
        "secret_return": False,
        "billing_tools_exposed": False,
        "checkout_tools_exposed": False,
        "destructive_admin_tools_exposed": False,
        "org_scoped_project_resolution": True,
        "selected_project_set": "supported",
        "default_project_behavior": "active_project_only",
        "cross_project_behavior": "explicit_request_required",
        "external_project_mounts": "supported_with_live_boundary_enforcement",
    }
    for key, expected in expected_security.items():
        if security.get(key) != expected:
            errors.append(f"metadata security.{key} expected {expected!r}")
    if security.get("event_bodies") != "summaries_only":
        errors.append("metadata security.event_bodies is not summaries_only")
    if missing:
        errors.append(f"metadata missing required tools: {', '.join(missing)}")
    if forbidden:
        errors.append(f"metadata exposes forbidden tool names: {', '.join(forbidden)}")
    return errors


def assert_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SmokeFailure(f"{label} must be a non-empty string")
    return value


def assert_kind(payload: dict[str, Any], expected: str, label: str) -> None:
    if payload.get("kind") != expected:
        raise SmokeFailure(f"{label} kind expected {expected!r}, got {payload.get('kind')!r}")


def assert_contains_event(payload: dict[str, Any], event_id: str, label: str) -> None:
    selected = payload.get("selected_events")
    if not isinstance(selected, list):
        raise SmokeFailure(f"{label} did not include selected_events")
    ids = {str(item.get("id")) for item in selected if isinstance(item, dict)}
    if event_id not in ids:
        raise SmokeFailure(f"{label} did not select the smoke event")


def contains_raw_body(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "body" and nested not in (None, "", {}):
                return True
            if contains_raw_body(nested):
                return True
    if isinstance(value, list):
        return any(contains_raw_body(item) for item in value)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exercise the hosted SPM remote MCP endpoint with real tool calls.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-env-var", default=DEFAULT_TOKEN_ENV_VAR)
    parser.add_argument("--profile", default="agent-core")
    parser.add_argument("--topic", default="spm-connector-smoke")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--read-only", action="store_true", help="Skip mutating event/preflight/action-report checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    return parser.parse_args()


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "endpoint": args.endpoint,
        "profile": args.profile,
        "token_env_var": args.token_env_var,
        "token_present": False,
        "mode": "read-only" if args.read_only else "read-write",
        "metadata_ok": False,
        "authenticated_ok": False,
        "functional_ok": False,
        "checks": [],
        "artifacts": {},
        "errors": [],
    }

    metadata = http_json("GET", args.endpoint, timeout=args.timeout)
    if not isinstance(metadata, dict):
        raise SmokeFailure("metadata endpoint did not return an object")
    metadata_errors = validate_metadata(metadata)
    report["metadata_tool_count"] = len(metadata.get("tools", []))
    report["metadata_ok"] = not metadata_errors
    if metadata_errors:
        report["errors"].extend(metadata_errors)
        return report
    report["checks"].append("metadata")

    token = os.getenv(args.token_env_var, "").strip()
    report["token_present"] = bool(token)
    if not token:
        report["errors"].append(f"{args.token_env_var} is not set")
        return report

    init = rpc(args.endpoint, profile=args.profile, token=token, method="initialize", request_id=1, timeout=args.timeout)
    server_info = init.get("result", {}).get("serverInfo")
    if not isinstance(server_info, dict) or server_info.get("name") != "spm-remote-mcp":
        raise SmokeFailure("initialize did not return SPM remote MCP serverInfo")

    tools = rpc(args.endpoint, profile=args.profile, token=token, method="tools/list", request_id=2, timeout=args.timeout)
    tool_names = {
        item.get("name")
        for item in tools.get("result", {}).get("tools", [])
        if isinstance(item, dict)
    }
    missing = sorted((REQUIRED_TOOLS if not args.read_only else REQUIRED_TOOLS - {"spm_temporal_event_create", "spm_agent_preflight", "spm_agent_action_report"}) - tool_names)
    forbidden = sorted(name for name in tool_names if isinstance(name, str) and any(fragment in name for fragment in FORBIDDEN_TOOL_FRAGMENTS))
    if missing:
        raise SmokeFailure(f"authenticated tools/list missing: {', '.join(missing)}")
    if forbidden:
        raise SmokeFailure(f"authenticated tools/list exposes forbidden tools: {', '.join(forbidden)}")
    report["authenticated_tool_count"] = len(tool_names)
    report["authenticated_ok"] = True
    report["checks"].extend(["initialize", "tools/list"])

    run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    run_tag = f"spm-smoke-{run_id}"
    selected_tags = ["spm-smoke", run_tag]

    event_id: str | None = None
    event_hash: str | None = None
    if not args.read_only:
        event = call_tool(
            args.endpoint,
            profile=args.profile,
            token=token,
            name="spm_temporal_event_create",
            arguments={
                "event_type": "connector_smoke",
                "temporal_layer": "working",
                "status": "active",
                "title": f"Remote MCP connector smoke {run_id}",
                "summary": "Authenticated remote MCP smoke event generated by the public SPM agent connector package.",
                "topic": args.topic,
                "topics": [args.topic],
                "tags": selected_tags,
                "authority_role": "operator",
                "authority_scope": "connector-validation",
                "authority_weight": 0.8,
                "context_area": "connector-validation",
                "actor_role": "automation",
                "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
            },
            request_id=3,
            timeout=args.timeout,
        )
        event_id = assert_non_empty_string(event.get("id"), "event.id")
        event_hash = assert_non_empty_string(event.get("event_hash"), "event.event_hash")
        report["artifacts"]["event_id"] = event_id
        report["artifacts"]["event_hash"] = event_hash
        report["checks"].append("spm_temporal_event_create")

    state = call_tool(
        args.endpoint,
        profile=args.profile,
        token=token,
        name="spm_temporal_state",
        arguments={
            "topic": args.topic,
            "tags": selected_tags if event_id else ["spm-smoke"],
            "tag_mode": "any",
            "limit": 25,
            "validity_mode": "advisory",
            "authority_mode": "advisory",
            "context_area": "connector-validation",
            "actor_role": "automation",
        },
        request_id=4,
        timeout=args.timeout,
    )
    assert_non_empty_string(state.get("report_hash"), "state.report_hash")
    if event_hash and state.get("latest_event_hash") != event_hash:
        raise SmokeFailure("temporal state latest_event_hash did not match the smoke event")
    report["artifacts"]["state_report_hash"] = state["report_hash"]
    report["checks"].append("spm_temporal_state")

    pack = call_tool(
        args.endpoint,
        profile=args.profile,
        token=token,
        name="spm_temporal_context_pack",
        arguments={
            "action_name": "remote_mcp_smoke_context_pack",
            "query": "Validate that an agent receives scoped, temporal, hash-verifiable project memory.",
            "topic": args.topic,
            "tags": selected_tags if event_id else ["spm-smoke"],
            "tag_mode": "any",
            "max_events": 10,
            "max_history": 5,
            "temporal_validity_mode": "advisory",
            "authority_mode": "advisory",
            "context_area": "connector-validation",
            "actor_role": "automation",
            "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
        },
        request_id=5,
        timeout=args.timeout,
    )
    assert_kind(pack, "spm.temporal_context_pack", "context pack")
    pack_hash = assert_non_empty_string(pack.get("pack_hash"), "pack.pack_hash")
    if event_id:
        assert_contains_event(pack, event_id, "context pack")
    if contains_raw_body(pack):
        raise SmokeFailure("context pack exposed a raw event body")
    report["artifacts"]["context_pack_hash"] = pack_hash
    report["checks"].append("spm_temporal_context_pack")

    verification = call_tool(
        args.endpoint,
        profile=args.profile,
        token=token,
        name="spm_temporal_context_pack_verify",
        arguments={
            "pack": pack,
            "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
        },
        request_id=6,
        timeout=args.timeout,
    )
    assert_kind(verification, "spm.temporal_context_pack_verification", "context pack verification")
    if verification.get("matched") is not True or verification.get("status") != "verified":
        raise SmokeFailure("context pack verification did not return verified/matched")
    report["checks"].append("spm_temporal_context_pack_verify")

    graph = call_tool(
        args.endpoint,
        profile=args.profile,
        token=token,
        name="spm_temporal_graph_query",
        arguments={
            "query": "Trace the smoke event through topic, tag and temporal-memory graph edges.",
            "seed_topics": [args.topic],
            "seed_tags": selected_tags if event_id else ["spm-smoke"],
            "tag_mode": "any",
            "max_depth": 2,
            "max_events": 20,
            "include_context_nodes": True,
            "temporal_validity_mode": "advisory",
            "authority_mode": "advisory",
            "context_area": "connector-validation",
            "actor_role": "automation",
            "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
        },
        request_id=7,
        timeout=args.timeout,
    )
    assert_kind(graph, "spm.temporal_graph_query", "graph query")
    graph_hash = assert_non_empty_string(graph.get("graph_hash"), "graph.graph_hash")
    if event_id:
        assert_contains_event(graph, event_id, "graph query")
    report["artifacts"]["graph_hash"] = graph_hash
    report["checks"].append("spm_temporal_graph_query")

    if not args.read_only:
        action = {
            "action_type": "run_tests",
            "intent": "run_tests",
            "title": f"Remote MCP connector smoke action {run_id}",
            "summary": "Validate remote MCP tool use through temporal memory, context-pack verification, preflight and action report.",
            "agent_kind": "codex",
            "agent_ref": "public-spm-agent-connectors",
            "target_refs": ["getspm/spm-agent-connectors"],
            "proposed_changes": {"none": True, "purpose": "smoke-test"},
            "files_touched": [],
            "requested_permissions": ["objects:read", "objects:write", "agent_hardening:write"],
            "topics": [args.topic],
            "tags": selected_tags,
            "risk_level": "low",
            "context_pack_hash": pack_hash,
            "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
        }
        preflight = call_tool(
            args.endpoint,
            profile=args.profile,
            token=token,
            name="spm_agent_preflight",
            arguments={
                "action": action,
                "temporal_context_request": {
                    "action_name": "remote_mcp_smoke_preflight_context",
                    "topic": args.topic,
                    "tags": selected_tags,
                    "tag_mode": "any",
                    "max_events": 10,
                    "max_history": 5,
                    "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
                },
                "include_hardening_context_pack": True,
                "include_temporal_context": True,
                "persist": True,
                "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
            },
            request_id=8,
            timeout=args.timeout,
        )
        assert_kind(preflight, "spm.agent_preflight", "agent preflight")
        if preflight.get("decision") not in VALID_PREFLIGHT_DECISIONS:
            raise SmokeFailure(f"unexpected preflight decision: {preflight.get('decision')!r}")
        preflight_hash = assert_non_empty_string(preflight.get("preflight_hash"), "preflight.preflight_hash")
        evaluation_hash = assert_non_empty_string(preflight.get("evaluation_hash"), "preflight.evaluation_hash")
        report["artifacts"]["preflight_hash"] = preflight_hash
        report["artifacts"]["evaluation_hash"] = evaluation_hash
        if preflight.get("preflight_id"):
            report["artifacts"]["preflight_id"] = str(preflight["preflight_id"])
        if preflight.get("action_id"):
            report["artifacts"]["action_id"] = str(preflight["action_id"])
        report["checks"].append("spm_agent_preflight")

        action_report_arguments: dict[str, Any] = {
            "outcome": "completed",
            "summary": "Remote MCP public connector smoke completed with metadata, temporal memory, context-pack verification, graph query and preflight checks.",
            "changed_files": [],
            "target_refs": ["getspm/spm-agent-connectors"],
            "actual_changes": {"none": True, "purpose": "smoke-test"},
            "executed_tests": [
                {
                    "name": "public-connector-remote-mcp-smoke",
                    "status": "passed",
                    "evidence_ref": f"spm-mcp-smoke:{run_id}",
                }
            ],
            "permissions_used": ["objects:read", "objects:write", "agent_hardening:write"],
            "decisions": [
                {
                    "title": "Public connector remote MCP smoke passed",
                    "summary": "The public connector reached the authenticated SPM MCP tool surface and verified context pack integrity.",
                    "hash": pack_hash,
                }
            ],
            "evidence_refs": [f"spm-mcp-smoke:{run_id}"],
            "context_pack_hash": pack_hash,
            "preflight_hash": preflight_hash,
            "evaluation_hash": evaluation_hash,
            "create_temporal_event": True,
            "metadata": {"run_id": run_id, "source": "public-connector-smoke"},
        }
        for key in ("action_id", "preflight_id"):
            if key in report["artifacts"]:
                action_report_arguments[key] = report["artifacts"][key]
        action_report = call_tool(
            args.endpoint,
            profile=args.profile,
            token=token,
            name="spm_agent_action_report",
            arguments=action_report_arguments,
            request_id=9,
            timeout=args.timeout,
        )
        assert_kind(action_report, "spm.agent_action_report", "action report")
        if action_report.get("status") not in VALID_ACTION_REPORT_STATUSES:
            raise SmokeFailure(f"unexpected action report status: {action_report.get('status')!r}")
        report_hash = assert_non_empty_string(action_report.get("report_hash"), "action_report.report_hash")
        validation_hash = assert_non_empty_string(action_report.get("validation_hash"), "action_report.validation_hash")
        report["artifacts"]["action_report_hash"] = report_hash
        report["artifacts"]["validation_hash"] = validation_hash
        report["checks"].append("spm_agent_action_report")

    report["functional_ok"] = True
    return report


def main() -> None:
    args = parse_args()
    try:
        report = run_smoke(args)
    except (SmokeFailure, OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        report = {
            "endpoint": args.endpoint,
            "profile": args.profile,
            "token_env_var": args.token_env_var,
            "token_present": bool(os.getenv(args.token_env_var, "").strip()),
            "mode": "read-only" if args.read_only else "read-write",
            "metadata_ok": False,
            "authenticated_ok": False,
            "functional_ok": False,
            "checks": [],
            "artifacts": {},
            "errors": [str(exc)],
        }

    report["ok"] = not report.get("errors") and report.get("metadata_ok") and report.get("authenticated_ok") and report.get("functional_ok")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"SPM remote MCP functional smoke: {'ok' if report['ok'] else 'failed'}")
        print(f"endpoint={report['endpoint']}")
        print(f"profile={report['profile']}")
        print(f"mode={report['mode']}")
        print(f"metadata_ok={report['metadata_ok']}")
        print(f"token_env_var={report['token_env_var']}")
        print(f"token_present={report['token_present']}")
        print(f"authenticated_ok={report['authenticated_ok']}")
        print(f"functional_ok={report['functional_ok']}")
        if report.get("checks"):
            print(f"checks={','.join(report['checks'])}")
        for key, value in sorted(report.get("artifacts", {}).items()):
            print(f"{key}={value}")
        for error in report.get("errors", []):
            print(f"error: {error}", file=sys.stderr)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
