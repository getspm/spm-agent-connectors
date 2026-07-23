#!/usr/bin/env python3
"""Authorize Codex against SPM using a browser-approved device flow."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from pathlib import Path
from typing import Any

DEFAULT_API_BASE_URL = "https://getspm.com"
DEFAULT_TOKEN_ENV_VAR = "SPM_CODEX_MCP_TOKEN"


def api_base_from_endpoint(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if cleaned.endswith("/v1/mcp"):
        return cleaned[: -len("/v1/mcp")]
    return cleaned


def post_json(url: str, payload: dict[str, Any], *, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        raise RuntimeError(str(detail)) from exc


def write_env_file(path: Path, *, token_env_var: str, access_token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"export {token_env_var}={shlex.quote(access_token)}\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authorize SPM remote MCP for Codex.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--mcp-endpoint", help="Alternative full MCP endpoint; /v1/mcp is stripped to derive API base URL.")
    parser.add_argument(
        "--project-id",
        help="Optional SPM authorization anchor. Omit it to choose after browser sign-in.",
    )
    parser.add_argument(
        "--access-mode",
        choices=("project", "project_set", "organization"),
        default="organization",
        help="Authorize one project, a selected project/mount set, or all authorized organization projects.",
    )
    parser.add_argument("--allowed-project-id", action="append", type=uuid.UUID, default=[])
    parser.add_argument(
        "--external-access-mode",
        choices=("none", "selected", "all_authorized"),
        default="all_authorized",
        help="Authorize no external projects, selected governed mounts, or every authorized mount.",
    )
    parser.add_argument("--allowed-external-mount-id", action="append", type=uuid.UUID, default=[])
    parser.add_argument("--client-name", default="Codex")
    parser.add_argument("--scope", action="append", dest="scopes", help="Requested scope. Can be repeated.")
    parser.add_argument(
        "--capture-mode",
        choices=("selective", "complete", "summaries_only", "metadata_only"),
        default="selective",
    )
    parser.add_argument("--retention-days", type=int, default=90)
    parser.add_argument("--include-user-turns", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-assistant-turns", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--review-threshold", type=float, default=0.62)
    parser.add_argument("--auto-apply-threshold", type=float, default=0.78)
    parser.add_argument("--attention-briefing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--attention-mode",
        choices=("critical", "actionable", "relevant", "all", "off"),
        default="relevant",
    )
    parser.add_argument("--attention-limit", type=int, default=8)
    parser.add_argument(
        "--memory-receipt-mode",
        choices=("discreet", "compact", "audit"),
        default="compact",
        help="Show no normal receipt, one compact receipt, or full integrity evidence after each iteration.",
    )
    parser.add_argument(
        "--project-association-mode",
        choices=("confirm_first", "auto_high_confidence", "manual"),
        default="confirm_first",
    )
    parser.add_argument("--project-auto-match-threshold", type=float, default=0.93)
    parser.add_argument("--project-candidate-limit", type=int, default=3)
    parser.add_argument(
        "--new-project-suggestions",
        choices=("explicit", "disabled"),
        default="explicit",
    )
    parser.add_argument("--token-env-var", default=DEFAULT_TOKEN_ENV_VAR)
    parser.add_argument("--write-env", type=Path, help="Write shell export to this file with mode 0600.")
    parser.add_argument("--print-export", action="store_true", help="Print an export command containing the token.")
    parser.add_argument("--open-browser", action="store_true", default=True)
    parser.add_argument("--no-open-browser", action="store_false", dest="open_browser")
    parser.add_argument("--timeout-sec", type=int, default=600)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.access_mode != "organization" and not args.project_id:
        print(
            "--project-id is required for project and project_set authorization.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if args.access_mode != "project_set" and args.allowed_project_id:
        print(
            "Selected local project ids require --access-mode project_set.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if args.external_access_mode != "selected" and args.allowed_external_mount_id:
        print(
            "Selected external mount ids require --external-access-mode selected.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if args.external_access_mode == "selected" and not args.allowed_external_mount_id:
        print(
            "--external-access-mode selected requires at least one --allowed-external-mount-id.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    api_base_url = api_base_from_endpoint(args.mcp_endpoint or args.api_base_url)
    code_url = f"{api_base_url}/v1/mcp/device/code"
    token_url = f"{api_base_url}/v1/mcp/device/token"
    code = post_json(
        code_url,
        {
            "project_id": args.project_id or None,
            "access_mode": args.access_mode,
            "allowed_project_ids": [str(value) for value in args.allowed_project_id],
            "external_access_mode": args.external_access_mode,
            "allowed_external_mount_ids": [
                str(value) for value in args.allowed_external_mount_id
            ],
            "client_name": args.client_name,
            "scopes": args.scopes,
            "connector_config": {
                "capture": {
                    "capture_mode": args.capture_mode,
                    "retention_days": args.retention_days,
                    "include_user_turns": args.include_user_turns,
                    "include_assistant_turns": args.include_assistant_turns,
                    "review_threshold": args.review_threshold,
                    "auto_apply_threshold": args.auto_apply_threshold,
                    "enabled": True,
                },
                "include_attention_briefing": args.attention_briefing,
                "attention_mode": args.attention_mode,
                "attention_limit": args.attention_limit,
                "memory_receipt_mode": args.memory_receipt_mode,
                "memory_receipt_mode_explicit": "--memory-receipt-mode" in sys.argv,
                "project_association": {
                    "mode": args.project_association_mode,
                    "auto_match_threshold": args.project_auto_match_threshold,
                    "candidate_limit": args.project_candidate_limit,
                    "new_project_suggestions": args.new_project_suggestions,
                },
            },
        },
    )
    print("SPM Codex authorization requested.")
    print(f"user_code={code['user_code']}")
    print(f"verification_uri={code['verification_uri_complete']}")
    print(f"expires_in={code['expires_in']}s")
    if args.open_browser:
        webbrowser.open(code["verification_uri_complete"])

    deadline = time.monotonic() + min(args.timeout_sec, int(code["expires_in"]))
    interval = max(1, int(code.get("interval", 5)))
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            token_response = post_json(token_url, {"device_code": code["device_code"]})
            access_token = token_response["access_token"]
            if args.write_env:
                write_env_file(args.write_env.expanduser(), token_env_var=args.token_env_var, access_token=access_token)
                print(f"wrote {args.write_env.expanduser()}")
            if args.print_export or not args.write_env:
                print(f"export {args.token_env_var}={shlex.quote(access_token)}")
            print("authorization=approved")
            return
        except RuntimeError as exc:
            message = str(exc)
            if "authorization_pending" in message:
                continue
            if "slow_down" in message:
                interval += 2
                continue
            print(f"authorization=failed error={message}", file=sys.stderr)
            raise SystemExit(1)
    print("authorization=expired", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
