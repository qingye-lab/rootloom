#!/usr/bin/env python3
"""Plan, install, inspect, and roll back Rootloom Personal Core."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from typing import Any, Iterator


PLUGIN_LIB = Path(__file__).resolve().parents[3] / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
from rootloom_lock import LockBusyError, LockFileError, simple_lock
from rootloom_paths import normalize_repo_path, validate_nonsensitive_managed_targets


MANAGED_TOKEN = "rootloom:managed"
STATE_DIRNAME = ".rootloom"
STATE_PATH = f"{STATE_DIRNAME}/state.json"
COMPONENT_POLICY_PATH = f"{STATE_DIRNAME}/components.json"
TRANSACTION_PATH = f"{STATE_DIRNAME}/transaction.json"
TRANSACTION_FORMAT = "rootloom-setup-transaction-v1"
COMPONENT_DESCRIPTIONS = {
    "global-guidance": "Install the personal engineering working agreement.",
    "project-guidance-hook": "Inject read-only evidence-backed project context at SessionStart.",
    "command-rules": "Apply the optional low-confirmation authorization policy.",
}
CAPABILITY_DESCRIPTIONS = {
    "global-policy": "Apply the lean cross-project working agreement.",
    "project-context": "Detect and inject temporary repository context without writing files.",
    "autonomy": "Install authorization Rules plus their required global policy.",
}
CAPABILITY_ALIASES = {"command-safety": "autonomy"}
CAPABILITY_COMPONENTS = {
    "global-policy": ("global-guidance",),
    "project-context": ("project-guidance-hook",),
    "autonomy": ("command-rules",),
}
FULL_CAPABILITIES = tuple(CAPABILITY_DESCRIPTIONS)
PRESETS = {
    "skills-only": (),
    "guidance": ("global-policy", "project-context"),
    "personal": FULL_CAPABILITIES,
}
PRESET_ALIASES = {"engineering": "personal"}


@dataclass(frozen=True)
class Target:
    relative_path: str
    source: Path | None
    component: str
    kind: str = "file"


@dataclass(frozen=True)
class Action:
    path: str
    action: str
    reason: str
    before_hash: str | None
    after_hash: str | None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def file_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
    except FileNotFoundError:
        return None


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def plugin_version(root: Path) -> str:
    payload = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("plugin manifest has no version")
    return version


def normalize_capabilities(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    canonical = [CAPABILITY_ALIASES.get(value, value) for value in values]
    unknown = sorted(set(canonical) - set(CAPABILITY_DESCRIPTIONS))
    if unknown:
        raise ValueError(f"unknown setup capabilities: {', '.join(unknown)}")
    selected = set(canonical)
    if "autonomy" in selected:
        selected.add("global-policy")
    return tuple(name for name in FULL_CAPABILITIES if name in selected)


def components_for_capabilities(capabilities: tuple[str, ...]) -> tuple[str, ...]:
    selected: set[str] = set()
    for capability in normalize_capabilities(capabilities):
        selected.update(CAPABILITY_COMPONENTS[capability])
    return tuple(name for name in COMPONENT_DESCRIPTIONS if name in selected)


def all_targets(root: Path) -> list[Target]:
    assets = root / "assets" / "system"
    targets = [
        Target("AGENTS.md", assets / "AGENTS.md", "global-guidance"),
        Target("rules/rootloom.rules", assets / "rules" / "rootloom.rules", "command-rules"),
        Target(COMPONENT_POLICY_PATH, None, "hook-policy", kind="hook-policy"),
    ]
    validate_nonsensitive_managed_targets(
        [target.relative_path for target in targets]
    )
    return targets


def target_catalog(root: Path, capabilities: tuple[str, ...]) -> list[Target]:
    selected = set(components_for_capabilities(capabilities))
    return [
        target
        for target in all_targets(root)
        if target.kind == "hook-policy" or target.component in selected
    ]


def render_component_policy(capabilities: tuple[str, ...]) -> bytes:
    selected_capabilities = normalize_capabilities(capabilities)
    components = components_for_capabilities(selected_capabilities)
    payload = {
        "managed_by": MANAGED_TOKEN,
        "version": 1,
        "selected_capabilities": list(selected_capabilities),
        "hooks": {"project-guidance-hook": "project-guidance-hook" in components},
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def desired_bytes(target: Target, capabilities: tuple[str, ...]) -> bytes:
    if target.kind == "hook-policy":
        return render_component_policy(capabilities)
    if target.source is None:
        raise ValueError(f"target has no source: {target.relative_path}")
    return target.source.read_bytes()


def has_symlink_component(path: Path, root: Path) -> bool:
    root = root.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def is_managed(path: Path, current: bytes) -> bool:
    if path.name in {"components.json", "state.json"}:
        try:
            payload = json.loads(current)
        except json.JSONDecodeError:
            return False
        return payload.get("managed_by") == MANAGED_TOKEN
    return MANAGED_TOKEN.encode() in current[:16_384]


def build_plan(
    codex_home: Path,
    capabilities: tuple[str, ...] = FULL_CAPABILITIES,
) -> tuple[str, list[Target], list[Action], dict[str, bytes]]:
    root = plugin_root()
    selected = normalize_capabilities(capabilities)
    targets = target_catalog(root, selected)
    desired = {target.relative_path: desired_bytes(target, selected) for target in targets}
    actions: list[Action] = []
    for target in targets:
        destination = codex_home / target.relative_path
        after = desired[target.relative_path]
        if has_symlink_component(destination, codex_home):
            action = "conflict"
            reason = "target or parent is symlinked"
            before = read_bytes(destination)
        else:
            before = read_bytes(destination)
            if before is None:
                action, reason = "create", "managed target is absent"
            elif before == after:
                action, reason = "unchanged", "content already matches"
            elif is_managed(destination, before):
                action, reason = "update", "managed content differs"
            else:
                action, reason = "conflict", "user-owned content differs"
        actions.append(
            Action(
                path=target.relative_path,
                action=action,
                reason=reason,
                before_hash=sha256_bytes(before) if before is not None else None,
                after_hash=sha256_bytes(after),
            )
        )
    return plugin_version(root), targets, actions, desired


def atomic_write(path: Path, value: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def load_pending_transaction(codex_home: Path) -> dict[str, Any] | None:
    path = codex_home / TRANSACTION_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("managed_by") != MANAGED_TOKEN
        or payload.get("format") != TRANSACTION_FORMAT
    ):
        raise ValueError("invalid pending setup transaction")

    backup_relative = Path(str(payload.get("backup", "")))
    if (
        not backup_relative.parts
        or backup_relative.is_absolute()
        or ".." in backup_relative.parts
    ):
        raise ValueError("invalid pending setup transaction backup path")
    backup = (codex_home / STATE_DIRNAME / backup_relative).resolve()
    backup_root = (codex_home / STATE_DIRNAME / "backups").resolve()
    if not backup.is_relative_to(backup_root) or not backup.is_dir():
        raise ValueError("pending setup transaction escaped the backup directory")

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("invalid pending setup transaction entries")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("invalid pending setup transaction entry")
        relative = raw.get("path")
        if not isinstance(relative, str) or not relative:
            raise ValueError("invalid pending setup transaction target")
        normalized = normalize_repo_path(relative, label="pending setup transaction target")
        if normalized != relative or normalized in seen:
            raise ValueError("pending setup transaction targets must be unique normalized paths")
        seen.add(normalized)
        operation = raw.get("operation")
        if operation not in {"write", "remove"}:
            raise ValueError("invalid pending setup transaction operation")
        before_hash = raw.get("before_hash")
        after_hash = raw.get("after_hash")
        if before_hash is not None and (
            not isinstance(before_hash, str) or len(before_hash) != 64
        ):
            raise ValueError("invalid pending setup transaction before hash")
        if after_hash is not None and (
            not isinstance(after_hash, str) or len(after_hash) != 64
        ):
            raise ValueError("invalid pending setup transaction after hash")
        staged = raw.get("staged")
        if operation == "write":
            if not isinstance(staged, str) or not staged:
                raise ValueError("missing staged pending setup transaction file")
            staged_path = Path(staged)
            if staged_path.is_absolute() or ".." in staged_path.parts:
                raise ValueError("invalid staged pending setup transaction file")
            source = (backup / staged_path).resolve()
            if not source.is_relative_to(backup) or not source.is_file():
                raise ValueError("staged pending setup transaction file is unavailable")
            if not isinstance(after_hash, str):
                raise ValueError("write transaction entry has no after hash")
        elif after_hash is not None or staged is not None:
            raise ValueError("remove transaction entry has unexpected staged data")
        entries.append(
            {
                "path": normalized,
                "operation": operation,
                "before_hash": before_hash,
                "after_hash": after_hash,
                "staged": staged,
            }
        )
    if sum(entry["path"] == STATE_PATH for entry in entries) != 1:
        raise ValueError("pending setup transaction must contain one state entry")
    return {
        "path": path,
        "backup": backup,
        "backup_relative": str(backup_relative),
        "entries": entries,
    }


def recover_pending_transaction(codex_home: Path) -> bool:
    pending = load_pending_transaction(codex_home)
    if pending is None:
        return False

    backup = pending["backup"]
    entries = pending["entries"]
    ordered = [entry for entry in entries if entry["path"] != STATE_PATH]
    ordered.extend(entry for entry in entries if entry["path"] == STATE_PATH)
    prepared: list[tuple[dict[str, Any], Path, bytes | None]] = []
    for entry in ordered:
        destination = codex_home / entry["path"]
        if has_symlink_component(destination, codex_home):
            raise RuntimeError(
                f"pending setup transaction target became symlinked: {entry['path']}"
            )
        current = read_bytes(destination)
        current_hash = sha256_bytes(current) if current is not None else None
        after_hash = entry["after_hash"]
        if current_hash == after_hash:
            prepared.append((entry, destination, None))
            continue
        if current_hash != entry["before_hash"]:
            raise RuntimeError(
                "pending setup transaction conflicts with "
                f"{entry['path']}; restore the expected pre-transaction content first"
            )
        if entry["operation"] == "remove":
            prepared.append((entry, destination, None))
            continue
        source = (backup / entry["staged"]).resolve()
        value = source.read_bytes()
        if sha256_bytes(value) != after_hash:
            raise RuntimeError(
                f"pending setup transaction staged content hash mismatch: {entry['path']}"
            )
        prepared.append((entry, destination, value))

    for entry, destination, value in prepared:
        current = read_bytes(destination)
        current_hash = sha256_bytes(current) if current is not None else None
        if current_hash == entry["after_hash"]:
            continue
        if entry["operation"] == "remove":
            destination.unlink(missing_ok=True)
        else:
            assert value is not None
            atomic_write(destination, value)

    for entry, destination, _value in prepared:
        current = read_bytes(destination)
        current_hash = sha256_bytes(current) if current is not None else None
        if current_hash != entry["after_hash"]:
            raise RuntimeError(
                f"pending setup transaction did not converge: {entry['path']}"
            )
    pending["path"].unlink()
    return True


def pending_transaction_payload(codex_home: Path) -> dict[str, Any] | None:
    pending = load_pending_transaction(codex_home)
    if pending is None:
        return None
    return {
        "format": TRANSACTION_FORMAT,
        "backup": pending["backup_relative"],
        "paths": [entry["path"] for entry in pending["entries"]],
    }


@contextmanager
def setup_lock(codex_home: Path) -> Iterator[Path]:
    state_root = codex_home / STATE_DIRNAME
    if state_root.is_symlink():
        raise ValueError("refusing symlinked setup state directory")
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / "setup.lock"
    try:
        with simple_lock(lock_path):
            yield lock_path
    except LockBusyError as exc:
        raise RuntimeError(f"another Rootloom setup operation holds {lock_path}") from exc
    except LockFileError as exc:
        raise ValueError(f"setup lock could not be used: {exc}") from exc


def load_state(codex_home: Path) -> dict[str, Any]:
    path = codex_home / STATE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict) or payload.get("managed_by") != MANAGED_TOKEN:
        raise ValueError("invalid Rootloom setup state")
    return payload


def installed_capabilities(state: dict[str, Any]) -> tuple[str, ...] | None:
    if state.get("status") != "installed":
        return None
    raw = state.get("capabilities")
    if raw is None:
        return None
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError("invalid installed capability selection")
    return normalize_capabilities(raw)


def make_backup_dir(codex_home: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = codex_home / STATE_DIRNAME / "backups" / stamp
    path.mkdir(parents=True, exist_ok=False)
    return path


def apply_installed_drift(
    codex_home: Path,
    state: dict[str, Any],
    actions: list[Action],
) -> tuple[list[Action], list[str]]:
    installed_files = state.get("files")
    if not isinstance(installed_files, dict) or any(
        not isinstance(path, str) or not isinstance(digest, str)
        for path, digest in installed_files.items()
    ):
        raise ValueError("invalid installed target hashes")
    normalized_installed: dict[str, str] = {}
    for raw_path, digest in installed_files.items():
        normalized = normalize_repo_path(raw_path, label="installed setup target")
        if normalized != raw_path or normalized in normalized_installed:
            raise ValueError("installed setup targets must be unique normalized paths")
        normalized_installed[normalized] = digest
    validate_nonsensitive_managed_targets(list(normalized_installed))
    drifted: list[str] = []
    updated: list[Action] = []
    for action in actions:
        expected = normalized_installed.get(action.path)
        if expected is None:
            updated.append(action)
            continue
        destination = codex_home / action.path
        current = None if has_symlink_component(destination, codex_home) else read_bytes(destination)
        current_hash = sha256_bytes(current) if current is not None else None
        if current_hash != expected:
            drifted.append(action.path)
            updated.append(
                Action(
                    path=action.path,
                    action="conflict",
                    reason="managed target changed after setup",
                    before_hash=current_hash,
                    after_hash=action.after_hash,
                )
            )
        else:
            updated.append(action)
    current_targets = {action.path for action in actions}
    for retired in sorted(set(normalized_installed) - current_targets):
        destination = codex_home / retired
        current = None if has_symlink_component(destination, codex_home) else read_bytes(destination)
        current_hash = sha256_bytes(current) if current is not None else None
        expected = normalized_installed[retired]
        if current_hash != expected:
            drifted.append(retired)
            updated.append(
                Action(
                    path=retired,
                    action="conflict",
                    reason="retired managed target changed after setup",
                    before_hash=current_hash,
                    after_hash=None,
                )
            )
        else:
            updated.append(
                Action(
                    path=retired,
                    action="remove",
                    reason="managed target is absent from the upgraded catalog",
                    before_hash=current_hash,
                    after_hash=None,
                )
            )
    return updated, sorted(drifted)


def apply_plan(
    codex_home: Path,
    replace_conflicts: bool,
    capabilities: tuple[str, ...] = FULL_CAPABILITIES,
    operation: str = "apply",
) -> dict[str, Any]:
    with setup_lock(codex_home):
        if operation not in {"apply", "install", "upgrade"}:
            raise ValueError(f"unsupported setup operation: {operation}")
        recover_pending_transaction(codex_home)
        selected = normalize_capabilities(capabilities)
        previous_state = load_state(codex_home)
        current = installed_capabilities(previous_state)
        if operation == "install" and current is not None:
            raise RuntimeError("Rootloom setup is already installed; use upgrade")
        if operation == "upgrade" and current is None:
            raise RuntimeError("no installed Rootloom setup is available to upgrade")
        if current is not None and current != selected:
            raise RuntimeError(
                "capability selection differs from the installed setup; roll back first"
            )
        version, targets, actions, desired = build_plan(codex_home, selected)
        drifted: list[str] = []
        if current is not None:
            actions, drifted = apply_installed_drift(
                codex_home, previous_state, actions
            )
        if drifted:
            raise RuntimeError(
                "managed setup targets changed after installation; restore or roll back before "
                "upgrade: "
                + ", ".join(drifted)
            )
        conflicts = [item for item in actions if item.action == "conflict"]
        if conflicts and not replace_conflicts:
            raise RuntimeError(
                "setup has user-owned conflicts; inspect plan and use --replace-conflicts "
                "only after exact replacement authorization"
            )
        changed = [item for item in actions if item.action != "unchanged"]
        if not changed:
            previous_version = previous_state.get("version")
            if current is not None and previous_version != version:
                state = {**previous_state, "version": version}
                atomic_write(
                    codex_home / STATE_PATH,
                    (json.dumps(state, indent=2, sort_keys=True) + "\n").encode(),
                )
                return {
                    "status": "upgraded",
                    "version": version,
                    "previous_version": previous_version,
                    "capabilities": list(selected),
                    "components": list(components_for_capabilities(selected)),
                    "actions": [asdict(item) for item in actions],
                }
            return {
                "status": "up_to_date" if operation == "upgrade" else "unchanged",
                "version": version,
                "capabilities": list(selected),
                "components": list(components_for_capabilities(selected)),
                "actions": [asdict(item) for item in actions],
            }

        backup = make_backup_dir(codex_home)
        manifest_entries: list[dict[str, Any]] = []
        for action in changed:
            destination = codex_home / action.path
            before = read_bytes(destination)
            before_mode = file_mode(destination)
            backup_path: str | None = None
            if before is not None:
                backup_target = backup / "files" / action.path
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup_target, follow_symlinks=False)
                backup_path = str(backup_target.relative_to(backup))
            manifest_entries.append(
                {
                    "path": action.path,
                    "before_exists": before is not None,
                    "before_hash": sha256_bytes(before) if before is not None else None,
                    "before_mode": before_mode,
                    "after_hash": action.after_hash,
                    "backup": backup_path,
                }
            )
        manifest = {
            "managed_by": MANAGED_TOKEN,
            "format": "rootloom-simple-backup-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "capabilities": list(selected),
            "previous_state": previous_state,
            "files": manifest_entries,
        }
        atomic_write(
            backup / "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        )
        state = {
            "managed_by": MANAGED_TOKEN,
            "status": "installed",
            "version": version,
            "capabilities": list(selected),
            "components": list(components_for_capabilities(selected)),
            "backup": str(backup.relative_to(codex_home / STATE_DIRNAME)),
            "files": {
                action.path: action.after_hash
                for action in actions
                if action.after_hash is not None
            },
        }
        state_bytes = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode()
        staged_entries: list[dict[str, Any]] = []
        for entry in manifest_entries:
            if entry["path"] in desired:
                staged_path = Path("staged") / entry["path"]
                atomic_write(backup / staged_path, desired[entry["path"]])
                staged_entries.append(
                    {
                        "path": entry["path"],
                        "operation": "write",
                        "before_hash": entry["before_hash"],
                        "after_hash": entry["after_hash"],
                        "staged": str(staged_path),
                    }
                )
            else:
                staged_entries.append(
                    {
                        "path": entry["path"],
                        "operation": "remove",
                        "before_hash": entry["before_hash"],
                        "after_hash": None,
                        "staged": None,
                    }
                )
        state_path = codex_home / STATE_PATH
        staged_state_path = Path("staged") / STATE_PATH
        atomic_write(backup / staged_state_path, state_bytes)
        staged_entries.append(
            {
                "path": STATE_PATH,
                "operation": "write",
                "before_hash": (
                    sha256_bytes(read_bytes(state_path))
                    if read_bytes(state_path) is not None
                    else None
                ),
                "after_hash": sha256_bytes(state_bytes),
                "staged": str(staged_state_path),
            }
        )
        transaction = {
            "managed_by": MANAGED_TOKEN,
            "format": TRANSACTION_FORMAT,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "capabilities": list(selected),
            "backup": str(backup.relative_to(codex_home / STATE_DIRNAME)),
            "entries": staged_entries,
        }
        atomic_write(
            codex_home / TRANSACTION_PATH,
            (json.dumps(transaction, indent=2, sort_keys=True) + "\n").encode(),
        )
        recover_pending_transaction(codex_home)
        return {
            "status": (
                "installed"
                if operation == "install"
                else "upgraded"
                if operation == "upgrade"
                else "applied"
            ),
            "version": version,
            "previous_version": previous_state.get("version"),
            "capabilities": list(selected),
            "components": list(components_for_capabilities(selected)),
            "backup": str(backup),
            "actions": [asdict(item) for item in actions],
        }


def rollback(codex_home: Path) -> dict[str, Any]:
    with setup_lock(codex_home):
        recover_pending_transaction(codex_home)
        state = load_state(codex_home)
        if state.get("status") != "installed":
            raise RuntimeError("no installed Rootloom setup is available to roll back")
        backup_relative = Path(str(state.get("backup", "")))
        if not backup_relative.parts or backup_relative.is_absolute() or ".." in backup_relative.parts:
            raise ValueError("invalid setup backup path")
        backup = (codex_home / STATE_DIRNAME / backup_relative).resolve()
        backup_root = (codex_home / STATE_DIRNAME / "backups").resolve()
        if not backup.is_relative_to(backup_root):
            raise ValueError("setup backup escaped the backup directory")
        manifest_path = backup / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("managed_by") != MANAGED_TOKEN or manifest.get("format") != "rootloom-simple-backup-v1":
            raise ValueError("invalid setup backup manifest")
        entries = manifest.get("files")
        if not isinstance(entries, list):
            raise ValueError("invalid setup backup entries")
        previous_state = manifest.get("previous_state")
        if not isinstance(previous_state, dict):
            raise ValueError("invalid previous setup state")

        installed_files = state.get("files")
        if not isinstance(installed_files, dict) or any(
            not isinstance(path, str) or not isinstance(digest, str)
            for path, digest in installed_files.items()
        ):
            raise ValueError("invalid installed target hashes")
        for relative, expected_hash in installed_files.items():
            destination = codex_home / relative
            if has_symlink_component(destination, codex_home):
                raise RuntimeError(f"refusing symlinked rollback target: {relative}")
            current = read_bytes(destination)
            current_hash = sha256_bytes(current) if current is not None else None
            if current_hash != expected_hash:
                raise RuntimeError(f"refusing rollback because {relative} changed after setup")

        restores: list[tuple[Path, bytes | None, int]] = []
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid setup backup entry")
            relative = entry.get("path")
            if (
                not isinstance(relative, str)
                or not relative
                or relative in seen
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
            ):
                raise ValueError("invalid setup backup target")
            seen.add(relative)
            destination = codex_home / relative
            if has_symlink_component(destination, codex_home):
                raise RuntimeError(f"refusing symlinked rollback target: {relative}")
            current = read_bytes(destination)
            current_hash = sha256_bytes(current) if current is not None else None
            if current_hash != entry.get("after_hash"):
                raise RuntimeError(f"refusing rollback because {relative} changed after setup")
            if entry.get("before_exists"):
                backup_name = entry.get("backup")
                if not isinstance(backup_name, str):
                    raise ValueError(f"missing setup backup: {relative}")
                source = (backup / backup_name).resolve()
                if not source.is_relative_to(backup.resolve()) or not source.is_file():
                    raise ValueError(f"invalid setup backup: {relative}")
                value = source.read_bytes()
                if sha256_bytes(value) != entry.get("before_hash"):
                    raise RuntimeError(f"setup backup hash mismatch: {relative}")
                raw_mode = entry.get("before_mode")
                mode = raw_mode if isinstance(raw_mode, int) else 0o600
                restores.append((destination, value, mode))
            else:
                restores.append((destination, None, 0o600))
        for destination, value, mode in restores:
            if value is None:
                destination.unlink(missing_ok=True)
            else:
                atomic_write(destination, value, mode)
        if previous_state.get("status") == "installed":
            next_state = previous_state
            rollback_status = "rolled_back_to_previous"
        else:
            next_state = {
                **state,
                "status": "rolled_back",
                "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            }
            rollback_status = "rolled_back"
        atomic_write(
            codex_home / STATE_PATH,
            (json.dumps(next_state, indent=2, sort_keys=True) + "\n").encode(),
        )
        return {
            "status": rollback_status,
            "capabilities": state.get("capabilities", []),
            "restored": [entry["path"] for entry in entries],
        }


def rollback_all(codex_home: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    while load_state(codex_home).get("status") == "installed":
        steps.append(rollback(codex_home))
    if not steps:
        raise RuntimeError("no installed Rootloom setup is available to roll back")
    return {
        "status": "rolled_back_all",
        "steps": len(steps),
        "restored": [path for step in steps for path in step["restored"]],
    }


def status_payload(
    codex_home: Path,
    capabilities: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    state = load_state(codex_home)
    pending = pending_transaction_payload(codex_home)
    installed = installed_capabilities(state)
    selected = (
        capabilities
        if capabilities is not None
        else installed
        if installed is not None
        else PRESETS["personal"]
    )
    version, _targets, actions, _desired = build_plan(codex_home, selected)
    drifted: list[str] = []
    if installed is not None:
        actions, drifted = apply_installed_drift(codex_home, state, actions)
    payload = {
        "status": state.get("status", "not-installed"),
        "version": version,
        "installed_version": state.get("version"),
        "upgrade_available": bool(
            installed is not None and state.get("version") != version
        ),
        "drifted_paths": drifted,
        "capabilities": list(normalize_capabilities(selected)),
        "components": list(components_for_capabilities(selected)),
        "actions": [asdict(item) for item in actions],
    }
    if pending is not None:
        payload["pending_transaction"] = pending
    return payload


def catalog_payload() -> dict[str, Any]:
    return {
        "presets": {name: list(values) for name, values in PRESETS.items()},
        "capabilities": CAPABILITY_DESCRIPTIONS,
        "components": COMPONENT_DESCRIPTIONS,
        "compatibility_aliases": {
            "capabilities": CAPABILITY_ALIASES,
            "presets": PRESET_ALIASES,
        },
        "default_preset": "personal",
    }


def print_payload(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--preset",
        type=normalize_preset,
        metavar="{skills-only,guidance,personal}",
    )
    group.add_argument("--capabilities", help="comma-separated capabilities or 'none'")


def normalize_preset(value: str) -> str:
    canonical = PRESET_ALIASES.get(value, value)
    if canonical not in PRESETS:
        choices = ", ".join(PRESETS)
        raise argparse.ArgumentTypeError(f"preset must be one of: {choices}")
    return canonical


def selected_capabilities(args: argparse.Namespace, codex_home: Path) -> tuple[str, ...]:
    if getattr(args, "preset", None):
        return PRESETS[normalize_preset(args.preset)]
    raw = getattr(args, "capabilities", None)
    if raw is not None:
        if raw.strip().lower() == "none":
            return ()
        values = tuple(item.strip() for item in raw.split(",") if item.strip())
        if not values:
            raise ValueError("--capabilities requires names or 'none'")
        return normalize_capabilities(values)
    installed = installed_capabilities(load_state(codex_home))
    return installed if installed is not None else PRESETS["personal"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-components")
    for name in ("plan", "status"):
        sub = commands.add_parser(name)
        add_selection_arguments(sub)
    apply = commands.add_parser("apply")
    add_selection_arguments(apply)
    apply.add_argument("--replace-conflicts", action="store_true")
    install = commands.add_parser("install")
    add_selection_arguments(install)
    install.add_argument("--replace-conflicts", action="store_true")
    upgrade = commands.add_parser("upgrade")
    upgrade.add_argument("--replace-conflicts", action="store_true")
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("--all", action="store_true", help="compatibility alias")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    codex_home = args.codex_home.expanduser().resolve()
    codex_home.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == "list-components":
            payload = catalog_payload()
        elif args.command == "plan":
            selected = selected_capabilities(args, codex_home)
            version, _targets, actions, _desired = build_plan(codex_home, selected)
            state = load_state(codex_home)
            installed = installed_capabilities(state)
            drifted: list[str] = []
            if installed is not None and installed == selected:
                actions, drifted = apply_installed_drift(
                    codex_home, state, actions
                )
            payload = {
                "status": "planned",
                "version": version,
                "installed_version": state.get("version"),
                "upgrade_available": bool(
                    installed is not None and state.get("version") != version
                ),
                "drifted_paths": drifted,
                "capabilities": list(selected),
                "components": list(components_for_capabilities(selected)),
                "actions": [asdict(item) for item in actions],
            }
        elif args.command in {"apply", "install"}:
            selected = selected_capabilities(args, codex_home)
            payload = apply_plan(
                codex_home,
                args.replace_conflicts,
                selected,
                operation=args.command,
            )
        elif args.command == "upgrade":
            installed = installed_capabilities(load_state(codex_home))
            if installed is None:
                raise RuntimeError("no installed Rootloom setup is available to upgrade")
            payload = apply_plan(
                codex_home,
                args.replace_conflicts,
                installed,
                operation="upgrade",
            )
        elif args.command == "status":
            selected = selected_capabilities(args, codex_home)
            payload = status_payload(codex_home, selected)
        else:
            payload = rollback_all(codex_home) if args.all else rollback(codex_home)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    print_payload(payload, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
