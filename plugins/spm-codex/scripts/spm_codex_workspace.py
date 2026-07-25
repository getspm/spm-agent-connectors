"""Body-free workspace observation for the Codex connector.

This module is a host adapter: it observes local material state and emits the
provider-neutral manifest contract owned by the SPM API. It never reads file
bodies into the connector response and never performs semantic classification.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "target",
        "vendor",
    }
)


class WorkspaceObservationError(ValueError):
    pass


def observe_workspace(
    path_value: str,
    *,
    capture_reason: str,
    max_files: int = 20_000,
    freshness_ttl_seconds: int = 900,
) -> dict[str, object]:
    root = Path(path_value).expanduser().resolve()
    if not root.exists():
        raise WorkspaceObservationError("Workspace path does not exist")
    if root.is_file():
        manifest = _document_manifest(root)
    else:
        git_root = _git_root(root)
        manifest = (
            _git_manifest(git_root)
            if git_root is not None
            else _filesystem_manifest(root, max_files=max_files)
        )
    manifest["capture_method"] = "connector"
    manifest["freshness_ttl_seconds"] = freshness_ttl_seconds
    manifest["metadata"] = {
        "source": "spm-codex-hook",
        "connector_kind": "codex",
        "host_kind": os.name,
        "inspection_scope": "body-free-material-state",
        "inventory_complete": True,
        "capture_reason": capture_reason,
    }
    return manifest


def _git_manifest(root: Path) -> dict[str, object]:
    revision = _git(root, "rev-parse", "HEAD")
    tree_hash = _git(root, "rev-parse", "HEAD^{tree}")
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    remote = _git(root, "config", "--get", "remote.origin.url", check=False)
    safe_remote = _safe_remote(remote) if remote else None
    root_commits = sorted(
        item
        for item in _git(root, "rev-list", "--max-parents=0", "HEAD").splitlines()
        if item
    )
    identity = safe_remote or "git-root-commits:" + _sha256_text(
        "\n".join(root_commits or [tree_hash])
    )
    status_bytes = _git_bytes(root, "status", "--porcelain=v1", "-z")
    workspace_state_hash = _git_workspace_state_hash(root, status_bytes=status_bytes)
    entries = [item for item in status_bytes.split(b"\0") if item]
    resource = {
        "resource_id": f"git:{_sha256_text(identity)[:24]}",
        "kind": "git_repository",
        "display_name": root.name,
        "locator_hash": _sha256_text(identity),
        "revision": revision,
        "version_ref": safe_remote,
        "content_hash": tree_hash,
        "workspace_state_hash": workspace_state_hash,
        "branch": branch or None,
        "dirty": bool(entries),
        "staged_count": sum(
            1 for item in entries if len(item) >= 2 and item[:1] not in {b" ", b"?"}
        ),
        "unstaged_count": sum(
            1 for item in entries if len(item) >= 2 and item[1:2] not in {b" ", b"?"}
        ),
        "untracked_count": sum(1 for item in entries if item[:2] == b"??"),
        "metadata": {
            "identity_basis": "remote" if safe_remote else "root_commits",
            "root_commit_count": len(root_commits),
        },
    }
    return {"workspace_kind": "git", "resources": [resource]}


def _filesystem_manifest(root: Path, *, max_files: int) -> dict[str, object]:
    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    for current_root, directory_names, file_names in os.walk(root):
        directory_names[:] = sorted(
            name for name in directory_names if name not in EXCLUDED_DIRECTORIES
        )
        current = Path(current_root)
        for name in sorted(file_names):
            file_path = current / name
            try:
                stat = file_path.stat()
            except OSError:
                continue
            relative = file_path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8"))
            content_hash = _hash_file(file_path)
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(content_hash.encode("ascii"))
            file_count += 1
            total_bytes += stat.st_size
            if file_count > max_files:
                raise WorkspaceObservationError(
                    f"Workspace exceeds the safe inventory limit of {max_files} files"
                )
    identity = f"filesystem:{root.name}:{file_count}"
    resource = {
        "resource_id": f"fs:{_sha256_text(identity)[:24]}",
        "kind": "filesystem_snapshot",
        "display_name": root.name,
        "locator_hash": _sha256_text(identity),
        "content_hash": digest.hexdigest(),
        "workspace_state_hash": digest.hexdigest(),
        "dirty": None,
        "metadata": {
            "identity_basis": "content_hashed_inventory",
            "file_count": file_count,
            "total_bytes": total_bytes,
            "excluded_directory_names": sorted(EXCLUDED_DIRECTORIES),
            "inventory_complete": True,
        },
    }
    return {"workspace_kind": "filesystem", "resources": [resource]}


def _document_manifest(path: Path) -> dict[str, object]:
    stat = path.stat()
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    identity = f"document:{path.name}:{digest}"
    resource = {
        "resource_id": f"doc:{_sha256_text(identity)[:24]}",
        "kind": "document",
        "display_name": path.name,
        "locator_hash": _sha256_text(identity),
        "content_hash": digest,
        "version_ref": digest,
        "workspace_state_hash": _sha256_text(f"{stat.st_size}:{stat.st_mtime_ns}:{digest}"),
        "dirty": None,
        "metadata": {
            "identity_basis": "content_hash",
            "file_count": 1,
            "total_bytes": stat.st_size,
            "inventory_complete": True,
        },
    }
    return {"workspace_kind": "document", "resources": [resource]}


def _git_root(path: Path) -> Path | None:
    value = _git(path, "rev-parse", "--show-toplevel", check=False)
    return Path(value).resolve() if value else None


def _git(root: Path, *args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if check and process.returncode != 0:
        raise WorkspaceObservationError("Git workspace inspection failed")
    return process.stdout.strip() if process.returncode == 0 else ""


def _git_bytes(root: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        timeout=15,
    )
    if process.returncode != 0:
        raise WorkspaceObservationError("Git workspace state inspection failed")
    return process.stdout


def _git_workspace_state_hash(root: Path, *, status_bytes: bytes) -> str:
    """Hash material working-tree state without returning file bodies."""

    digest = hashlib.sha256()
    digest.update(b"status\0")
    digest.update(status_bytes)
    for label, args in (
        (b"unstaged\0", ("diff", "--no-ext-diff", "--binary")),
        (b"staged\0", ("diff", "--cached", "--no-ext-diff", "--binary")),
    ):
        digest.update(label)
        digest.update(_git_bytes(root, *args))
    untracked = _git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z")
    digest.update(b"untracked\0")
    for item in sorted(value for value in untracked.split(b"\0") if value):
        relative = item.decode("utf-8", errors="surrogateescape")
        candidate = root / relative
        digest.update(item)
        digest.update(b"\0")
        if candidate.is_file() and not candidate.is_symlink():
            digest.update(_hash_file(candidate).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_remote(value: str) -> str:
    cleaned = value.strip()
    if "://" not in cleaned:
        if "@" in cleaned and ":" in cleaned:
            _, tail = cleaned.split("@", 1)
            host, path = tail.split(":", 1)
            return f"ssh://{host.lower()}/{path}"
        return cleaned
    parsed = urlsplit(cleaned)
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme.lower(), f"{hostname.lower()}{port}", parsed.path, "", ""))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
