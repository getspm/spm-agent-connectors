#!/usr/bin/env python3
"""Run Cursor Agent while mirroring its natural turn lifecycle into SPM."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any


DEFAULT_HOOK_URL = "https://getspm.com/v1/agent-memory-hooks/cursor"


def _post_event(event: dict[str, Any]) -> None:
    token = os.environ.get("SPM_AGENT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SPM_AGENT_TOKEN is not configured")
    request = urllib.request.Request(
        os.environ.get("SPM_AGENT_HOOK_URL", DEFAULT_HOOK_URL),
        data=json.dumps(event).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"SPM lifecycle request failed: {exc}") from exc


def _emit_safely(event: dict[str, Any]) -> None:
    try:
        _post_event(event)
    except RuntimeError as exc:
        print(f"[spm-cursor] {exc}; Cursor work continues without claiming persistence", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run cursor-agent with automatic SPM user/assistant turn capture."
    )
    parser.add_argument("prompt")
    parser.add_argument("--project-ref")
    parser.add_argument("--cursor-agent", default="cursor-agent")
    parser.add_argument("cursor_args", nargs=argparse.REMAINDER)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    command = [
        args.cursor_agent,
        "--print",
        "--output-format",
        "stream-json",
        *args.cursor_args,
        args.prompt,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
    )
    session_id: str | None = None
    assistant_parts: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_session = event.get("session_id")
        if isinstance(event_session, str) and event_session:
            session_id = session_id or event_session
        if event.get("type") == "system" and event.get("subtype") == "init" and session_id:
            common = {
                "session_id": session_id,
                "cwd": event.get("cwd") or os.getcwd(),
                "project_ref": args.project_ref,
                "model": event.get("model"),
                "permission_mode": event.get("permissionMode"),
            }
            _emit_safely({"adapter_event": "session_start", **common})
            _emit_safely(
                {
                    "adapter_event": "user_turn",
                    "role": "user",
                    "content": args.prompt,
                    "turn_id": event.get("request_id") or "prompt-1",
                    **common,
                }
            )
        if event.get("type") == "assistant":
            message = event.get("message") if isinstance(event.get("message"), dict) else {}
            for part in message.get("content") or []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    assistant_parts.append(part["text"])
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            if not assistant_parts:
                assistant_parts.append(event["result"])
            if session_id and assistant_parts:
                _emit_safely(
                    {
                        "adapter_event": "assistant_turn",
                        "role": "assistant",
                        "session_id": session_id,
                        "content": "".join(assistant_parts)[-100_000:],
                        "turn_id": event.get("request_id") or "result-1",
                        "cwd": os.getcwd(),
                        "project_ref": args.project_ref,
                        "request_id": event.get("request_id"),
                    }
                )
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
