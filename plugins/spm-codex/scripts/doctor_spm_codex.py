#!/usr/bin/env python3
"""Smoke-check the hosted SPM remote MCP endpoint for Codex."""

from __future__ import annotations

import argparse
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
    "spm_agent_action_report",
    "spm_agent_session_get",
    "spm_agent_session_association_decide",
    "spm_agent_session_context_inject",
    "spm_agent_session_context_revoke",
    "spm_agent_session_receipt_status",
    "spm_agent_session_set_project",
    "spm_agent_session_start",
    "spm_agent_turn_ingest",
    "spm_memory_capture_policy_get",
    "spm_memory_capture_policy_set",
    "spm_memory_capture_journal_list",
    "spm_memory_capture_journal_verify",
    "spm_agent_policy_pack",
    "spm_agent_preflight",
    "spm_context_boundaries_list",
    "spm_context_boundary_get",
    "spm_context_boundary_pack",
    "spm_cross_project_context_pack",
    "spm_multi_project_context_pack",
    "spm_project_bootstrap_preview",
    "spm_project_bootstrap_status",
    "spm_project_resolve",
    "spm_projects_list",
    "spm_temporal_context_pack",
    "spm_temporal_context_pack_verify",
    "spm_temporal_event_create",
    "spm_temporal_graph_query",
    "spm_temporal_state",
    "spm_trust_remediation_plan",
    "spm_trust_status",
}
OPTIONAL_PRIVILEGED_TOOLS = {
    # Confirmation can create project state and is intentionally absent from
    # otherwise valid organization or project tokens without bootstrap scope.
    "spm_project_bootstrap_confirm",
}
FORBIDDEN_TOOL_FRAGMENTS = (
    "billing",
    "checkout",
    "payment",
    "invoice_payment",
    "customer_portal",
    "delete_project",
    "destructive_admin",
)


def http_json(method: str, url: str, *, token: str | None = None, payload: dict[str, Any] | None = None, timeout: int = 20) -> Any:
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


def rpc(endpoint: str, *, profile: str, token: str, method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> dict[str, Any]:
    separator = "&" if "?" in endpoint else "?"
    url = f"{endpoint}{separator}{urllib.parse.urlencode({'profile': profile})}"
    result = http_json(
        "POST",
        url,
        token=token,
        payload={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected JSON-RPC response for {method}: {result!r}")
    if "error" in result:
        raise RuntimeError(f"{method} failed: {result['error']}")
    return result


def validate_metadata(metadata: dict[str, Any]) -> list[str]:
    names = {item["name"] for item in metadata.get("tools", []) if isinstance(item, dict) and "name" in item}
    missing = sorted(REQUIRED_TOOLS - names)
    forbidden = sorted(name for name in names if any(fragment in name for fragment in FORBIDDEN_TOOL_FRAGMENTS))
    errors: list[str] = []
    security = metadata.get("security", {})
    if metadata.get("requires_auth") is not True:
        errors.append("metadata does not require auth")
    if security.get("project_scoped") != "supported":
        errors.append("metadata does not advertise project-scoped tokens")
    if security.get("org_scoped_project_resolution") is not True:
        errors.append("metadata does not advertise org-scoped project resolution")
    if security.get("default_project_behavior") != "active_project_only":
        errors.append("metadata default project behavior is not active_project_only")
    if security.get("cross_project_behavior") != "explicit_request_required":
        errors.append("metadata cross-project behavior is not explicit_request_required")
    if security.get("event_bodies") != "summaries_only":
        errors.append("metadata event body mode is not summaries_only")
    if security.get("secret_return") is not False:
        errors.append("metadata allows secret return")
    if security.get("billing_tools_exposed") is not False:
        errors.append("metadata exposes billing tools")
    if security.get("checkout_tools_exposed") is not False:
        errors.append("metadata exposes checkout tools")
    if security.get("destructive_admin_tools_exposed") is not False:
        errors.append("metadata exposes destructive admin tools")

    agent_core = metadata.get("profiles", {}).get("agent-core", {})
    if agent_core.get("mode") != "read-write":
        errors.append("agent-core profile is not read-write")
    if agent_core.get("allow_body") is not False:
        errors.append("agent-core profile allows event bodies")
    if agent_core.get("allow_secret_return") is not False:
        errors.append("agent-core profile allows secret return")

    if missing:
        errors.append(f"metadata missing required tools: {', '.join(missing)}")
    if forbidden:
        errors.append(f"metadata exposes forbidden tool names: {', '.join(forbidden)}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the SPM Codex remote MCP connector.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-env-var", default=DEFAULT_TOKEN_ENV_VAR)
    parser.add_argument("--profile", default="agent-core")
    parser.add_argument("--metadata-only", action="store_true", help="Do not require token or authenticated JSON-RPC checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report: dict[str, Any] = {
        "endpoint": args.endpoint,
        "profile": args.profile,
        "token_env_var": args.token_env_var,
        "token_present": False,
        "metadata_ok": False,
        "authenticated_ok": False,
        "authenticated_optional_privileged_tools": [],
        "errors": [],
    }
    try:
        metadata = http_json("GET", args.endpoint)
        if not isinstance(metadata, dict):
            raise RuntimeError("metadata endpoint did not return an object")
        report["metadata_tool_count"] = len(metadata.get("tools", []))
        metadata_errors = validate_metadata(metadata)
        report["metadata_ok"] = not metadata_errors
        report["errors"].extend(metadata_errors)

        token = os.getenv(args.token_env_var, "").strip()
        report["token_present"] = bool(token)
        if not args.metadata_only:
            if not token:
                report["errors"].append(f"{args.token_env_var} is not set")
            else:
                init = rpc(args.endpoint, profile=args.profile, token=token, method="initialize", request_id=1)
                tools = rpc(args.endpoint, profile=args.profile, token=token, method="tools/list", request_id=2)
                tool_names = {
                    item.get("name")
                    for item in tools.get("result", {}).get("tools", [])
                    if isinstance(item, dict)
                }
                missing = sorted(REQUIRED_TOOLS - tool_names)
                if missing:
                    report["errors"].append(f"authenticated tools/list missing: {', '.join(missing)}")
                report["authenticated_optional_privileged_tools"] = sorted(
                    OPTIONAL_PRIVILEGED_TOOLS & tool_names
                )
                report["server"] = init.get("result", {}).get("serverInfo")
                report["authenticated_tool_count"] = len(tool_names)
                report["authenticated_ok"] = not missing
    except (OSError, RuntimeError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        report["errors"].append(str(exc))

    report["ok"] = not report["errors"]
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"SPM Codex MCP doctor: {'ok' if report['ok'] else 'failed'}")
        print(f"endpoint={report['endpoint']}")
        print(f"metadata_ok={report['metadata_ok']}")
        print(f"token_env_var={report['token_env_var']}")
        print(f"token_present={report['token_present']}")
        print(f"authenticated_ok={report['authenticated_ok']}")
        for error in report["errors"]:
            print(f"error: {error}", file=sys.stderr)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
