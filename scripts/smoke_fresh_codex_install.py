#!/usr/bin/env python3
"""Verify the Codex connector from a fresh marketplace installation.

This is intentionally separate from the hosted MCP lifecycle E2E suite. It
proves that the public artifact Codex installs contains the expected version,
hook runtime and remote metadata contract without modifying a user's Codex
configuration or requiring an SPM bearer token.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "spm-codex"
MARKETPLACE_NAME = "personal"


class FreshInstallFailure(RuntimeError):
    """Raised when a fresh Codex plugin installation is not usable."""


def run_command(
    command: list[str], *, environment: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
    )


def require_success(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode == 0:
        return result.stdout
    detail = (result.stderr or result.stdout).strip()
    raise FreshInstallFailure(f"{label} failed: {detail or 'no diagnostic output'}")


def expected_version(source_root: Path) -> str:
    manifest = source_root / "plugins" / PLUGIN_NAME / ".codex-plugin" / "plugin.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreshInstallFailure(f"cannot read plugin manifest: {exc}") from exc
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise FreshInstallFailure("plugin manifest has no version")
    return version


def parse_install_output(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FreshInstallFailure(f"Codex plugin installation did not return JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise FreshInstallFailure("Codex plugin installation did not return an object")
    return payload


def run_fresh_install_smoke(source_root: Path, *, codex_binary: str) -> dict[str, Any]:
    source_root = source_root.resolve()
    version = expected_version(source_root)
    with tempfile.TemporaryDirectory(prefix="spm-codex-fresh-install-") as temporary:
        codex_home = Path(temporary) / "codex-home"
        codex_home.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(codex_home)
        environment.pop("PLUGIN_ROOT", None)

        require_success(
            run_command(
                [codex_binary, "plugin", "marketplace", "add", str(source_root)],
                environment=environment,
                cwd=source_root,
            ),
            "adding temporary marketplace",
        )
        install = parse_install_output(
            require_success(
                run_command(
                    [
                        codex_binary,
                        "plugin",
                        "add",
                        f"{PLUGIN_NAME}@{MARKETPLACE_NAME}",
                        "--json",
                    ],
                    environment=environment,
                    cwd=source_root,
                ),
                "installing connector from temporary marketplace",
            )
        )

        if install.get("version") != version:
            raise FreshInstallFailure(
                f"installed version {install.get('version')!r} does not match {version!r}"
            )
        installed_path = Path(str(install.get("installedPath") or ""))
        hook = installed_path / "scripts" / "spm_codex_hook.py"
        manifest = installed_path / ".codex-plugin" / "plugin.json"
        if not hook.is_file() or not manifest.is_file():
            raise FreshInstallFailure("installed connector is missing its hook runtime or manifest")
        installed_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        if installed_manifest.get("version") != version:
            raise FreshInstallFailure("installed manifest version differs from source manifest")
        require_success(
            run_command(
                [sys.executable, "-m", "py_compile", str(hook)],
                environment=environment,
                cwd=source_root,
            ),
            "compiling installed hook",
        )
        require_success(
            run_command(
                [
                    sys.executable,
                    str(installed_path / "scripts" / "doctor_spm_codex.py"),
                    "--metadata-only",
                    "--json",
                ],
                environment=environment,
                cwd=source_root,
            ),
            "checking installed connector metadata",
        )
        return {
            "ok": True,
            "plugin": PLUGIN_NAME,
            "version": version,
            "installed_hook": str(hook),
            "marketplace": MARKETPLACE_NAME,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the public SPM Codex connector in a disposable Codex home."
    )
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--codex-binary", default=shutil.which("codex") or "codex")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        report = run_fresh_install_smoke(args.source_root, codex_binary=args.codex_binary)
    except FreshInstallFailure as exc:
        report = {"ok": False, "error": str(exc)}
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print("fresh Codex connector installation: " + ("ok" if report["ok"] else "failed"))
        for key, value in report.items():
            if key != "ok":
                print(f"{key}={value}")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
