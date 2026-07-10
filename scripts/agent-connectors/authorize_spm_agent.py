#!/usr/bin/env python3
"""Authorize any SPM agent connector with the browser-approved device flow."""

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
DEFAULT_ENV_PATH = Path.home() / ".spm" / "agent.env"


def _post_json(url: str, payload: dict[str, Any], *, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        raise RuntimeError(str(detail)) from exc
    if not isinstance(value, dict):
        raise RuntimeError("SPM returned an invalid device authorization response")
    return value


def _write_env(path: Path, access_token: str) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        f"export SPM_AGENT_TOKEN={shlex.quote(access_token)}\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Authorize Codex, Claude Code, Cursor, OpenClaw or another SPM agent connector."
    )
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--project-id", required=True, type=uuid.UUID, help="Authorization anchor project.")
    parser.add_argument(
        "--access-mode",
        choices=("project", "project_set", "organization"),
        default="organization",
    )
    parser.add_argument("--allowed-project-id", action="append", type=uuid.UUID, default=[])
    parser.add_argument("--allowed-external-mount-id", action="append", type=uuid.UUID, default=[])
    parser.add_argument("--client-name", default="SPM agent connector")
    parser.add_argument("--scope", action="append", dest="scopes")
    parser.add_argument("--write-env", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--no-write-env", action="store_true")
    parser.add_argument("--open-browser", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--timeout-sec", type=int, default=600)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.access_mode != "project_set" and (
        args.allowed_project_id or args.allowed_external_mount_id
    ):
        print(
            "Selected project and mount ids require --access-mode project_set.",
            file=sys.stderr,
        )
        return 2
    base = args.api_base_url.rstrip("/")
    code = _post_json(
        f"{base}/v1/mcp/device/code",
        {
            "project_id": str(args.project_id),
            "access_mode": args.access_mode,
            "allowed_project_ids": [str(value) for value in args.allowed_project_id],
            "allowed_external_mount_ids": [
                str(value) for value in args.allowed_external_mount_id
            ],
            "client_name": args.client_name,
            "scopes": args.scopes,
        },
    )
    print(f"Approve SPM access in your browser with code {code['user_code']}.")
    print(code["verification_uri_complete"])
    if args.open_browser:
        webbrowser.open(code["verification_uri_complete"])

    deadline = time.monotonic() + min(args.timeout_sec, int(code["expires_in"]))
    interval = max(1, int(code.get("interval", 5)))
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            token_response = _post_json(
                f"{base}/v1/mcp/device/token",
                {"device_code": code["device_code"]},
            )
        except RuntimeError as exc:
            message = str(exc)
            if "authorization_pending" in message:
                continue
            if "slow_down" in message:
                interval += 2
                continue
            print(f"SPM authorization failed: {message}", file=sys.stderr)
            return 1
        if not args.no_write_env:
            _write_env(args.write_env, token_response["access_token"])
            print(f"Authorized. Token stored with mode 0600 in {args.write_env.expanduser()}.")
            print(f"Load it with: source {shlex.quote(str(args.write_env.expanduser()))}")
        else:
            print("Authorized. Token was not written; repeat without --no-write-env to persist it.")
        print(
            "Access: "
            f"{token_response['access_mode']} / "
            f"{len(token_response.get('allowed_project_ids', []))} selected projects / "
            f"{len(token_response.get('allowed_external_mount_ids', []))} external mounts"
        )
        return 0
    print("SPM authorization expired before approval.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
