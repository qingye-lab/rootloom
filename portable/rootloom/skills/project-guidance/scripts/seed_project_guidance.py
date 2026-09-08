#!/usr/bin/env python3
"""Create small, evidence-backed AGENTS.md files without overwriting user guidance."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
NATIVE_PLUGIN_LIB = Path(__file__).resolve().parents[3] / "lib"
LOCAL_LOCK_MODULE = SCRIPT_DIR / "rootloom_lock.py"
NATIVE_LOCK_MODULE = NATIVE_PLUGIN_LIB / "rootloom_lock.py"
if LOCAL_LOCK_MODULE.is_file() and not LOCAL_LOCK_MODULE.is_symlink():
    LOCK_MODULE_DIR = SCRIPT_DIR
elif NATIVE_LOCK_MODULE.is_file() and not NATIVE_LOCK_MODULE.is_symlink():
    LOCK_MODULE_DIR = NATIVE_PLUGIN_LIB
else:
    raise ImportError("rootloom_lock.py is unavailable or symlinked")
sys.path.insert(0, str(LOCK_MODULE_DIR))

from rootloom_lock import LockBusyError, LockFileError, simple_lock

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Codex currently ships Python 3.11+
    tomllib = None  # type: ignore[assignment]


VERSION = "1"
MANAGED_START_PREFIX = "<!-- rootloom:managed-start"
MANAGED_END = "<!-- rootloom:managed-end -->"
PRESERVE_NOTE = (
    "<!-- Add durable project-only rules below this line. "
    "The seeder preserves content outside the managed block. -->"
)
MAX_READ_BYTES = 256 * 1024
MAX_GUIDANCE_BYTES = 24 * 1024
MAX_SESSION_CONTEXT_BYTES = 4 * 1024
MAX_HOOK_INPUT_BYTES = 1024 * 1024
MAX_MODULE_DEPTH = 3
MAX_MODULE_CANDIDATES = 12

MANIFEST_NAMES = (
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "go.work",
    "Package.swift",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "mix.exs",
    "pubspec.yaml",
    "Makefile",
    "justfile",
)
LOCKFILE_NAMES = (
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "package-lock.json",
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "Package.resolved",
    "Gemfile.lock",
    "composer.lock",
    "mix.lock",
    "pubspec.lock",
)
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "Pods",
    "DerivedData",
    "dist",
    "build",
    "coverage",
    "target",
    "__pycache__",
}
UNSAFE_PATH_PARTS = {".git", ".codex", ".agents", "node_modules", ".venv", "venv", "vendor", "Pods", "DerivedData"}
TEMP_PREFIXES = (
    "/tmp/",
    "/private/tmp/",
    "/var/folders/",
    "/private/var/folders/",
)
KNOWN_DIR_PURPOSES = {
    "app": "application entry points and product code",
    "apps": "independently runnable applications",
    "api": "API surface and request handling",
    "backend": "backend services",
    "client": "client application code",
    "cmd": "executable entry points",
    "config": "project configuration",
    "database": "database integration and schema assets",
    "docs": "canonical project documentation",
    "frontend": "frontend application code",
    "infra": "infrastructure and deployment definitions",
    "ios": "iOS application code",
    "android": "Android application code",
    "migrations": "database or data migrations",
    "packages": "shared or workspace packages",
    "scripts": "project automation",
    "server": "server application code",
    "src": "primary source code",
    "test": "test suites",
    "tests": "test suites",
    "tools": "developer tooling",
    "web": "web application code",
}
COMMAND_PRIORITY = {
    "verify": 0,
    "test": 1,
    "typecheck": 2,
    "lint": 3,
    "check": 4,
    "build": 5,
    "format": 6,
    "dev": 7,
    "other": 8,
}
PACKAGE_SCRIPT_NAME = re.compile(r"^[A-Za-z0-9@][A-Za-z0-9@:._-]{0,127}$")
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def _read_text(path: Path, limit: int = MAX_READ_BYTES) -> str:
    try:
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except (OSError, UnicodeError):
        return ""
    if len(data) > limit:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(path))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _load_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:
        return {}
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _clean_inline(value: Any, limit: int = 240) -> str:
    text = str(value or "")
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[`\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -#|:")
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return ""
    return text[:limit].rstrip()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _safe_repo_file(path: Path, root: Path) -> bool:
    return path.is_file() and not path.is_symlink() and _is_within(path, root)


def _git_common_dir(root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    common = Path(result.stdout.strip())
    return common.resolve() if common.is_absolute() else (root / common).resolve()


@contextmanager
def guidance_lock(project_root: Path) -> Iterator[Path]:
    """Serialize Rootloom guidance writers for one Git common directory."""

    lock_path = _git_common_dir(project_root) / "rootloom-guidance.lock"
    try:
        with simple_lock(lock_path):
            yield lock_path
    except LockBusyError as exc:
        raise RuntimeError("guidance lock is busy") from exc
    except LockFileError as exc:
        raise ValueError(f"guidance lock safety check failed: {exc}") from exc


def _git_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    root_text = result.stdout.strip()
    return Path(root_text).resolve() if root_text else None


def _trusted_project_roots() -> list[Path]:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    config = _load_toml(codex_home / "config.toml")
    projects = config.get("projects", {})
    trusted: list[Path] = []
    if not isinstance(projects, dict):
        return trusted
    for raw_path, settings in projects.items():
        if isinstance(settings, dict) and settings.get("trust_level") == "trusted":
            trusted.append(Path(str(raw_path)).expanduser().resolve())
    return trusted


def _is_trusted(root: Path) -> bool:
    return any(_is_within(root, trusted) for trusted in _trusted_project_roots())


def _disabled(root: Path) -> bool:
    env_value = os.environ.get("ROOTLOOM_PROJECT_GUIDANCE", "").strip().lower()
    if env_value in {"0", "false", "off", "disabled"}:
        return True
    return any(
        path.exists()
        for path in (
            root / ".rootloom" / "disable-project-guidance",
            root / ".codex" / "disable-project-guidance-seeding",
        )
    )


def _unsafe_location(root: Path) -> bool:
    resolved = root.resolve().as_posix() + "/"
    if resolved.startswith(TEMP_PREFIXES):
        return True
    home = Path.home().resolve()
    protected = (home / ".codex", home / ".agents")
    if any(_is_within(root, path) for path in protected):
        return True
    return any(part in UNSAFE_PATH_PARTS for part in root.parts)


def _readme_metadata(root: Path) -> tuple[str, str, str | None]:
    readmes = sorted(
        path for path in root.glob("README*") if _safe_repo_file(path, root)
    )
    if not readmes:
        return "", "", None
    path = readmes[0]
    text = _read_text(path, 64 * 1024)
    name = ""
    description = ""
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not name and stripped.startswith("# "):
            name = _clean_inline(stripped[2:], 100)
            continue
        if not name:
            html_heading = re.fullmatch(r"<h1\b[^>]*>(.*?)</h1>", stripped, re.IGNORECASE)
            if html_heading:
                name = _clean_inline(html_heading.group(1), 100)
                continue
        if (
            not description
            and stripped
            and not stripped.startswith(("#", "[!", "![", "<", "```", "---"))
            and not re.fullmatch(r"[-=*_| ]+", stripped)
        ):
            description = _clean_inline(stripped)
        if name and description:
            break
    return name, description, _relative(path, root)


def _project_metadata(root: Path) -> tuple[str, str, str | None]:
    name = root.name
    description = ""
    source: str | None = None

    package_path = root / "package.json"
    package = _load_json(package_path) if _safe_repo_file(package_path, root) else {}
    if package:
        name = _clean_inline(package.get("name"), 100) or name
        package_description = _clean_inline(package.get("description"))
        if package_description:
            description = package_description
            source = "package.json"

    pyproject_path = root / "pyproject.toml"
    pyproject = _load_toml(pyproject_path) if _safe_repo_file(pyproject_path, root) else {}
    project = pyproject.get("project", {}) if pyproject else {}
    poetry = pyproject.get("tool", {}).get("poetry", {}) if pyproject else {}
    if isinstance(project, dict) and project:
        name = _clean_inline(project.get("name"), 100) or name
        project_description = _clean_inline(project.get("description"))
        if project_description and not description:
            description = project_description
            source = "pyproject.toml"
    elif isinstance(poetry, dict) and poetry:
        name = _clean_inline(poetry.get("name"), 100) or name
        poetry_description = _clean_inline(poetry.get("description"))
        if poetry_description and not description:
            description = poetry_description
            source = "pyproject.toml"

    cargo_path = root / "Cargo.toml"
    cargo = _load_toml(cargo_path) if _safe_repo_file(cargo_path, root) else {}
    cargo_package = cargo.get("package", {}) if cargo else {}
    if isinstance(cargo_package, dict) and cargo_package:
        name = _clean_inline(cargo_package.get("name"), 100) or name
        cargo_description = _clean_inline(cargo_package.get("description"))
        if cargo_description and not description:
            description = cargo_description
            source = "Cargo.toml"

    readme_name, readme_description, readme_path = _readme_metadata(root)
    name = readme_name or name
    if readme_description and not description:
        description = readme_description
        source = readme_path
    return name, description, source


def _detect_documents(root: Path) -> list[str]:
    candidates: list[Path] = []
    patterns = (
        "README*",
        "CONTRIBUTING*",
        "ARCHITECTURE*",
        "PRODUCT.md",
        "docs/architecture*",
        "docs/project-architecture*",
        "docs/design-language*",
        "docs/quality/verification-matrix*",
    )
    for pattern in patterns:
        candidates.extend(path for path in root.glob(pattern) if _safe_repo_file(path, root))
    return sorted({_relative(path, root) for path in candidates})[:16]


def _detect_ci(root: Path) -> list[str]:
    candidates: list[Path] = []
    candidates.extend(
        path for path in root.glob(".github/workflows/*") if _safe_repo_file(path, root)
    )
    for name in (".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml", ".circleci/config.yml"):
        path = root / name
        if _safe_repo_file(path, root):
            candidates.append(path)
    return sorted({_relative(path, root) for path in candidates})[:20]


def _detect_root_dirs(root: Path) -> list[dict[str, str]]:
    directories: list[dict[str, str]] = []
    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name.lower())
    except OSError:
        return directories
    for path in entries:
        if not path.is_dir() or path.is_symlink() or path.name in IGNORED_DIRS:
            continue
        if path.name.startswith(".") and path.name != ".github":
            continue
        purpose = KNOWN_DIR_PURPOSES.get(path.name.lower())
        if purpose is None:
            if not any(_safe_repo_file(path / name, root) for name in MANIFEST_NAMES):
                continue
            purpose = "independent module or toolchain boundary"
        directories.append({"path": path.name + "/", "purpose": purpose})
        if len(directories) >= 20:
            break
    return directories


def _command_category(name: str) -> str | None:
    lowered = name.lower().replace("-", "").replace("_", "")
    if lowered in {"verify", "validate", "ci", "precommit"}:
        return "verify"
    if lowered.startswith("test"):
        return "test"
    if "typecheck" in lowered or lowered in {"types", "tsc"}:
        return "typecheck"
    if lowered.startswith("lint"):
        return "lint"
    if lowered in {"check", "checks"}:
        return "check"
    if lowered.startswith("build"):
        return "build"
    if lowered.startswith("format") or lowered in {"fmt", "prettier"}:
        return "format"
    if lowered in {"dev", "start", "serve", "run"}:
        return "dev"
    return None


def _detect_package_manager(root: Path, package: dict[str, Any]) -> str:
    declared = str(package.get("packageManager", "")).split("@", 1)[0].strip()
    if declared in {"pnpm", "yarn", "bun", "npm"}:
        return declared
    for filename, manager in (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lock", "bun"),
        ("bun.lockb", "bun"),
        ("package-lock.json", "npm"),
    ):
        if _safe_repo_file(root / filename, root):
            return manager
    return "npm"


def _detect_commands(root: Path) -> tuple[list[dict[str, str]], str | None]:
    commands: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(command: str, source: str, category: str) -> None:
        if command in seen:
            return
        seen.add(command)
        commands.append({"command": command, "source": source, "category": category})

    package_path = root / "package.json"
    package = _load_json(package_path) if _safe_repo_file(package_path, root) else {}
    package_manager: str | None = None
    scripts = package.get("scripts", {}) if package else {}
    if package:
        package_manager = _detect_package_manager(root, package)
    if package_manager and isinstance(scripts, dict):
        for name in sorted(scripts, key=lambda item: (COMMAND_PRIORITY.get(_command_category(item) or "other", 9), item)):
            if PACKAGE_SCRIPT_NAME.fullmatch(name) is None:
                continue
            category = _command_category(name)
            if category:
                add(f"{package_manager} run {name}", f"package.json scripts.{name}", category)

    for filename, runner in (("Makefile", "make"), ("justfile", "just")):
        path = root / filename
        if not _safe_repo_file(path, root):
            continue
        for line in _read_text(path, 128 * 1024).splitlines():
            match = re.match(r"^([A-Za-z][A-Za-z0-9_.-]*):(?:\s|$)", line)
            if not match:
                continue
            target = match.group(1)
            category = _command_category(target)
            if category:
                add(f"{runner} {target}", f"{filename} target {target}", category)

    if _safe_repo_file(root / "Cargo.toml", root):
        add("cargo test", "Cargo.toml", "test")
        add("cargo check", "Cargo.toml", "check")
        add("cargo fmt --check", "Cargo.toml", "format")
    if _safe_repo_file(root / "go.mod", root):
        add("go test ./...", "go.mod", "test")
        add("go vet ./...", "go.mod", "check")
    if _safe_repo_file(root / "Package.swift", root):
        add("swift test", "Package.swift", "test")

    pyproject_path = root / "pyproject.toml"
    if _safe_repo_file(pyproject_path, root):
        pyproject_text = _read_text(pyproject_path)
        prefix = "uv run " if (root / "uv.lock").exists() else ""
        if "[tool.pytest" in pyproject_text or re.search(r"\bpytest\b", pyproject_text):
            add(f"{prefix}python -m pytest", "pyproject.toml", "test")
        if "[tool.ruff" in pyproject_text or re.search(r"\bruff\b", pyproject_text):
            add(f"{prefix}ruff check .", "pyproject.toml", "lint")
        if "[tool.mypy" in pyproject_text:
            add(f"{prefix}mypy .", "pyproject.toml", "typecheck")

    commands.sort(key=lambda item: (COMMAND_PRIORITY.get(item["category"], 9), item["command"]))
    return commands[:16], package_manager


def _detect_manifests(root: Path) -> tuple[list[str], list[str]]:
    manifests = [name for name in MANIFEST_NAMES if _safe_repo_file(root / name, root)]
    lockfiles = [name for name in LOCKFILE_NAMES if _safe_repo_file(root / name, root)]
    return manifests, lockfiles


def _detect_module_candidates(root: Path) -> list[dict[str, Any]]:
    found: dict[str, set[str]] = {}
    for depth_pattern in ("*", "*/*", "*/*/*"):
        for directory in root.glob(depth_pattern):
            if not directory.is_dir() or directory.is_symlink():
                continue
            relative = directory.relative_to(root)
            if len(relative.parts) > MAX_MODULE_DEPTH or any(part in IGNORED_DIRS for part in relative.parts):
                continue
            manifests = [
                name
                for name in MANIFEST_NAMES
                if _safe_repo_file(directory / name, root)
            ]
            if not manifests:
                continue
            found.setdefault(relative.as_posix(), set()).update(manifests)
            if len(found) >= MAX_MODULE_CANDIDATES * 2:
                break
    candidates = [
        {"path": path + "/", "manifests": sorted(manifests)}
        for path, manifests in sorted(found.items())
    ]
    return candidates[:MAX_MODULE_CANDIDATES]


def _resolve_scope(project_root: Path, target: Path | None) -> tuple[Path | None, str | None]:
    if target is None:
        scope_root = project_root
    else:
        expanded = target.expanduser()
        scope_root = (expanded if expanded.is_absolute() else project_root / expanded).resolve()
    if not _is_within(scope_root, project_root):
        return None, "target_outside_repository"
    relative = scope_root.relative_to(project_root)
    if len(relative.parts) > MAX_MODULE_DEPTH:
        return None, "target_too_deep"
    if scope_root != project_root and not any(
        _safe_repo_file(scope_root / name, project_root) for name in MANIFEST_NAMES
    ):
        return None, "not_a_module_boundary"
    return scope_root, None


def probe(cwd: Path, target: Path | None = None) -> dict[str, Any]:
    project_root = _git_root(cwd)
    if project_root is None:
        return {"status": "skipped", "reason": "not_a_git_repository", "cwd": str(cwd)}
    scope_root, error = _resolve_scope(project_root, target)
    if scope_root is None:
        return {"status": "skipped", "reason": error, "project_root": str(project_root)}

    name, description, metadata_source = _project_metadata(scope_root)
    manifests, lockfiles = _detect_manifests(scope_root)
    commands, package_manager = _detect_commands(scope_root)
    documents = _detect_documents(scope_root)
    ci = _detect_ci(scope_root)
    directories = _detect_root_dirs(scope_root)
    modules = _detect_module_candidates(scope_root)
    scope = scope_root.relative_to(project_root).as_posix() or "."

    structural = {
        "scope": scope,
        "name": name,
        "description": description,
        "metadata_source": metadata_source,
        "manifests": manifests,
        "lockfiles": lockfiles,
        "commands": commands,
        "documents": documents,
        "ci": ci,
        "directories": directories,
        "module_candidates": modules,
        "package_manager": package_manager,
    }
    fingerprint = hashlib.sha256(
        json.dumps(structural, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    return {
        "status": "ready",
        "project_root": str(project_root),
        "scope_root": str(scope_root),
        "scope": scope,
        "agents_path": str(scope_root / "AGENTS.md"),
        "fingerprint": fingerprint,
        **structural,
    }


def _render_managed(data: dict[str, Any]) -> str:
    scope = data["scope"]
    heading = (
        f"# Project guidance for {data['name']}"
        if scope == "."
        else f"# Module guidance for {data['name']}"
    )
    lines = [
        f"{MANAGED_START_PREFIX} version={VERSION} fingerprint={data['fingerprint']} scope={scope} -->",
        heading,
        "",
        "## Scope and sources of truth",
        "",
    ]
    if scope != ".":
        lines.append(f"- This guidance applies only under `{scope}/` and refines repository-level guidance.")
    if data.get("description"):
        source = data.get("metadata_source") or "repository metadata"
        lines.append(f"- Project purpose: {data['description']} (from `{source}`).")
    else:
        lines.append("- Project purpose was not safely inferable; verify behavior from source and canonical docs before changing it.")

    truth_sources = data["documents"] + data["manifests"] + data["ci"]
    if truth_sources:
        rendered = ", ".join(f"`{item}`" for item in truth_sources[:16])
        lines.append(f"- Detected sources of truth: {rendered}.")
    if data["lockfiles"]:
        rendered = ", ".join(f"`{item}`" for item in data["lockfiles"])
        lines.append(f"- Dependency state is pinned by {rendered}; avoid unrelated lockfile churn.")
    if data.get("package_manager"):
        lines.append(f"- Use `{data['package_manager']}` for JavaScript package scripts in this scope.")

    if data["directories"]:
        lines.extend(["", "## Repository map", ""])
        for item in data["directories"]:
            lines.append(f"- `{item['path']}` — {item['purpose']}.")

    lines.extend(["", "## Canonical commands", ""])
    if data["commands"]:
        for item in data["commands"]:
            lines.append(f"- `{item['command']}` — detected from `{item['source']}`.")
    else:
        lines.append("- No canonical command was safely detected; inspect repository docs and CI before claiming verification.")

    if data["module_candidates"]:
        lines.extend(["", "## Independent module candidates", ""])
        for item in data["module_candidates"]:
            manifests = ", ".join(f"`{name}`" for name in item["manifests"])
            lines.append(
                f"- `{item['path']}` — owns {manifests}; add nested guidance only when its commands or invariants differ."
            )

    lines.extend(
        [
            "",
            "## Verification contract",
            "",
            "- Run the smallest detected command set that proves the changed behavior, then expand with blast radius.",
            "- If a required command cannot run, report the exact gap and do not convert it into a passing claim.",
            "- Keep generated guidance factual: project-only invariants belong below the managed block and must cite real paths.",
            MANAGED_END,
        ]
    )
    return "\n".join(lines)


def _existing_project_guidance(project_root: Path, cwd: Path) -> list[str]:
    project_root = project_root.resolve()
    try:
        relative_cwd = cwd.resolve().relative_to(project_root)
    except ValueError:
        relative_cwd = Path()
    directories = [project_root]
    current = project_root
    for part in relative_cwd.parts:
        current /= part
        directories.append(current)

    names: list[str] = []
    for directory in directories:
        for name in ("AGENTS.override.md", "AGENTS.md"):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                continue
            names.append(path.relative_to(project_root).as_posix())
    return names


def _render_session_context(data: dict[str, Any], *, cwd: Path) -> str:
    """Render only incremental cold-start facts, never persistent guidance."""

    scope_root = Path(data["scope_root"])
    guidance_names = _existing_project_guidance(Path(data["project_root"]), cwd)
    name = _clean_inline(data.get("name"), 100) or scope_root.name
    scope = _clean_inline(data.get("scope"), 160) or "."
    manifests = [
        value
        for raw in data.get("manifests", [])
        if (value := _clean_inline(raw, 160))
    ]
    primary_manifest = manifests[0] if manifests else None

    lines = [
        "# Temporary project facts",
        "",
        f"- Project: {name}.",
        f"- Scope: `{scope}`.",
    ]
    if primary_manifest:
        lines.append(f"- Primary manifest: `{primary_manifest}`.")
    elif data.get("package_manager"):
        package_manager = _clean_inline(data["package_manager"], 40)
        lines.append(f"- Detected package manager: `{package_manager}`.")
    else:
        lines.append("- No primary manifest was safely detected.")

    if guidance_names:
        rendered = ", ".join(f"`{item}`" for item in guidance_names)
        lines.append(
            f"- Existing project guidance: {rendered}; treat it as authoritative."
        )
    else:
        lines.append(
            "- No project guidance was detected; use these facts temporarily and "
            "persist guidance only on the user's explicit create, refresh, or refine request."
        )

    commands: list[str] = []
    if not guidance_names:
        for item in data.get("commands", []):
            command = _clean_inline(item.get("command"), 180)
            if not command:
                continue
            commands.append(command)
            if len(commands) == 3:
                break
    if commands:
        lines.extend(["", "## Incremental verification commands", ""])
        lines.extend(f"- `{command}`" for command in commands)
    elif guidance_names:
        lines.append("- Verification commands are omitted because project guidance already exists.")
    else:
        lines.append(
            "- No canonical verification command was safely detected; inspect repository docs and CI."
        )
    return "\n".join(lines)


def _replace_managed(existing: str, managed: str) -> tuple[str | None, str | None]:
    start = existing.find(MANAGED_START_PREFIX)
    end = existing.find(MANAGED_END)
    if start == -1 and end == -1:
        return None, "user_owned_guidance"
    if start == -1 or end == -1 or end < start:
        return None, "malformed_managed_block"
    end += len(MANAGED_END)
    return existing[:start] + managed + existing[end:], None


def _contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"refusing to write symlinked guidance: {path}")
    descriptor, temp_name = tempfile.mkstemp(prefix=".AGENTS.md.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _read_guidance_bytes(path: Path) -> bytes | None:
    if path.is_symlink():
        raise ValueError(f"refusing symlinked guidance: {path}")
    try:
        with path.open("rb") as handle:
            return handle.read(MAX_GUIDANCE_BYTES + 1)
    except FileNotFoundError:
        return None


def _seed_locked(data: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    project_root = Path(data["project_root"])
    scope_root = Path(data["scope_root"])
    agents_path = Path(data["agents_path"])
    override_path = scope_root / "AGENTS.override.md"
    if override_path.exists():
        return {**data, "status": "skipped", "reason": "override_exists"}
    if agents_path.is_symlink() or override_path.is_symlink():
        return {**data, "status": "skipped", "reason": "symlinked_guidance"}

    managed = _render_managed(data)
    original = _read_guidance_bytes(agents_path)
    if original is not None:
        if len(original) > MAX_GUIDANCE_BYTES:
            return {**data, "status": "skipped", "reason": "existing_guidance_too_large"}
        existing = original.decode("utf-8", errors="replace")
        content, reason = _replace_managed(existing, managed)
        if content is None:
            return {**data, "status": "skipped", "reason": reason}
        status = "updated"
    else:
        content = managed + "\n\n" + PRESERVE_NOTE + "\n"
        status = "created"

    if _contains_secret(content):
        return {**data, "status": "error", "reason": "secret_like_content_detected"}
    if len(content.encode("utf-8")) > MAX_GUIDANCE_BYTES:
        return {**data, "status": "error", "reason": "generated_guidance_too_large"}
    if original is not None and original.decode("utf-8", errors="replace") == content:
        return {**data, "status": "unchanged", "reason": "fingerprint_current"}
    if not dry_run:
        if _read_guidance_bytes(agents_path) != original:
            return {
                **data,
                "status": "skipped",
                "reason": "guidance_changed_during_seed",
            }
        _atomic_write(agents_path, content)
    return {**data, "status": status, "dry_run": dry_run}


def seed(
    cwd: Path,
    target: Path | None = None,
    *,
    allow_untrusted: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    data = probe(cwd, target)
    if data.get("status") != "ready":
        return data

    project_root = Path(data["project_root"])
    if _disabled(project_root):
        return {**data, "status": "skipped", "reason": "disabled"}
    if _unsafe_location(project_root):
        return {**data, "status": "skipped", "reason": "unsafe_location"}
    if not allow_untrusted and not _is_trusted(project_root):
        return {**data, "status": "skipped", "reason": "untrusted_project"}

    try:
        with guidance_lock(project_root):
            refreshed = probe(cwd, target)
            if refreshed.get("status") != "ready":
                return refreshed
            return _seed_locked(refreshed, dry_run=dry_run)
    except RuntimeError as exc:
        if str(exc) == "guidance lock is busy":
            return {**data, "status": "skipped", "reason": "guidance_lock_busy"}
        raise
    except ValueError as exc:
        if str(exc) == "refusing symlinked guidance":
            return {**data, "status": "skipped", "reason": "symlinked_guidance"}
        raise


def validate(file_path: Path) -> dict[str, Any]:
    if not file_path.is_file() or file_path.is_symlink():
        return {"valid": False, "errors": ["guidance_file_missing_or_symlinked"], "path": str(file_path)}
    content = _read_text(file_path, MAX_GUIDANCE_BYTES + 1)
    errors: list[str] = []
    if len(content.encode("utf-8")) > MAX_GUIDANCE_BYTES:
        errors.append("guidance_too_large")
    if _contains_secret(content):
        errors.append("secret_like_content_detected")
    if "[TODO" in content or "[TBD" in content:
        errors.append("placeholder_content_detected")
    if MANAGED_START_PREFIX in content or MANAGED_END in content:
        start = content.find(MANAGED_START_PREFIX)
        end = content.find(MANAGED_END)
        if (
            content.count(MANAGED_START_PREFIX) != 1
            or content.count(MANAGED_END) != 1
            or end < start
        ):
            errors.append("malformed_managed_block")
        elif not re.match(
            r"<!-- rootloom:managed-start version=\S+ fingerprint=\S+ scope=\S+ -->",
            content[start:],
        ):
            errors.append("not_project_managed_guidance")
        else:
            data = probe(file_path.parent, file_path.parent)
            if data.get("status") != "ready":
                errors.append(f"probe_failed:{data.get('reason', 'unknown')}")
            else:
                expected = _render_managed(data)
                actual = content[start : end + len(MANAGED_END)]
                if actual != expected:
                    errors.append("managed_block_drift")
    if not re.search(r"(?m)^#\s+\S", content):
        errors.append("missing_title")
    return {"valid": not errors, "errors": errors, "path": str(file_path)}


def temporary_project_context(
    cwd: Path,
    *,
    allow_untrusted: bool = False,
) -> dict[str, Any]:
    """Render current repository facts for one session without writing files."""

    data = probe(cwd)
    if data.get("status") != "ready":
        return data
    project_root = Path(data["project_root"])
    if _disabled(project_root):
        return {**data, "status": "skipped", "reason": "disabled"}
    if _unsafe_location(project_root):
        return {**data, "status": "skipped", "reason": "unsafe_location"}
    if not allow_untrusted and not _is_trusted(project_root):
        return {**data, "status": "skipped", "reason": "untrusted_project"}
    content = _render_session_context(data, cwd=cwd)
    if _contains_secret(content):
        return {**data, "status": "error", "reason": "secret_like_content_detected"}
    if len(content.encode("utf-8")) > MAX_SESSION_CONTEXT_BYTES:
        return {
            **data,
            "status": "error",
            "reason": "generated_session_context_too_large",
        }
    return {**data, "status": "context-ready", "context": content}


def _advisory_context(content: str) -> str:
    return (
        "Rootloom detected the following repository facts for this session without "
        "creating or updating AGENTS.md. Treat them as advisory context subordinate "
        "to current repository evidence and any existing project guidance. Persist "
        "guidance only on the user's explicit request to create, refresh, or refine it; "
        "the user need not name a Skill.\n\n"
        f"<rootloom_project_context>\n{content}\n</rootloom_project_context>"
    )


def _auto_protocol(event: dict[str, Any]) -> str | None:
    """Disambiguate only the shared VS Code/Copilot SessionStart configuration."""

    if event.get("hook_event_name") == "SessionStart" and "sessionId" not in event:
        return "vscode"
    if (
        isinstance(event.get("sessionId"), str)
        and bool(event["sessionId"])
        and "hook_event_name" not in event
    ):
        return "copilot"
    return None


def _context_envelope(protocol: str, context: str) -> dict[str, Any] | str:
    if protocol in {"codex", "vscode"}:
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
        }
    if protocol == "cursor":
        return {"additional_context": context}
    if protocol == "copilot":
        return {"additionalContext": context}
    if protocol == "kiro":
        return context
    raise ValueError(f"unsupported hook protocol: {protocol}")


def _hook_diagnostic(protocol: str, message: str) -> dict[str, Any] | None:
    if protocol in {"codex", "vscode"}:
        return {"continue": True, "systemMessage": message}
    print(message, file=sys.stderr)
    return None


def _hook_output(
    event: dict[str, Any],
    *,
    protocol: str = "codex",
    allow_untrusted: bool = False,
) -> dict[str, Any] | str | None:
    if protocol == "auto":
        resolved = _auto_protocol(event)
        if resolved is None:
            return None
        protocol = resolved
    source = str(event.get("source", ""))
    permission_mode = str(
        event.get("permission_mode", event.get("permissionMode", ""))
    )
    cwd = Path(str(event.get("cwd") or os.getcwd())).expanduser()
    if source == "compact" or permission_mode == "plan":
        return None
    trust_override = allow_untrusted or os.environ.get("ROOTLOOM_ALLOW_UNTRUSTED") == "1"
    result = temporary_project_context(cwd, allow_untrusted=trust_override)
    status = result.get("status")
    if status != "context-ready":
        if status == "error":
            return _hook_diagnostic(
                protocol,
                f"Project context detection skipped: {result.get('reason', 'unknown error')}",
            )
        return None

    context = _advisory_context(result["context"])
    if len(context.encode("utf-8")) > MAX_SESSION_CONTEXT_BYTES:
        return _hook_diagnostic(
            protocol,
            "Project context detection skipped: generated session context exceeded 4 KiB",
        )
    return _context_envelope(protocol, context)


def _read_hook_event() -> dict[str, Any]:
    data = sys.stdin.buffer.read(MAX_HOOK_INPUT_BYTES + 1)
    if len(data) > MAX_HOOK_INPUT_BYTES:
        raise ValueError("hook input exceeded 1 MiB")
    try:
        event = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"hook input is not valid JSON: {exc.msg}") from exc
    if not isinstance(event, dict):
        raise ValueError("hook input must be a JSON object")
    return event


def _json_print(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser("probe", help="Inspect repository facts without writing")
    probe_parser.add_argument("--cwd", default=os.getcwd())
    probe_parser.add_argument("--target")

    seed_parser = subparsers.add_parser("seed", help="Create or refresh a managed AGENTS.md block")
    seed_parser.add_argument("--cwd", default=os.getcwd())
    seed_parser.add_argument("--target")
    seed_parser.add_argument("--allow-untrusted", action="store_true")
    seed_parser.add_argument("--dry-run", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate an AGENTS.md file")
    validate_parser.add_argument("--file", required=True)

    hook_parser = subparsers.add_parser("hook", help="Handle a SessionStart hook event")
    hook_parser.add_argument(
        "--protocol",
        choices=("codex", "cursor", "copilot", "kiro", "vscode", "auto"),
        default="codex",
    )
    hook_parser.add_argument("--allow-untrusted", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "probe":
        _json_print(probe(Path(args.cwd), Path(args.target) if args.target else None))
        return 0
    if args.command == "seed":
        result = seed(
            Path(args.cwd),
            Path(args.target) if args.target else None,
            allow_untrusted=args.allow_untrusted,
            dry_run=args.dry_run,
        )
        _json_print(result)
        return 1 if result.get("status") == "error" else 0
    if args.command == "validate":
        result = validate(Path(args.file).expanduser().absolute())
        _json_print(result)
        return 0 if result["valid"] else 1
    if args.command == "hook":
        try:
            event = _read_hook_event()
        except ValueError as exc:
            if args.protocol not in {"codex", "vscode"}:
                print(f"Project guidance seeder input error: {exc}", file=sys.stderr)
                return 0
            _json_print({"continue": True, "systemMessage": f"Project guidance seeder input error: {exc}"})
            return 0
        output = _hook_output(
            event,
            protocol=args.protocol,
            allow_untrusted=args.allow_untrusted,
        )
        if output is not None:
            if isinstance(output, str):
                print(output)
            else:
                print(json.dumps(output, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
