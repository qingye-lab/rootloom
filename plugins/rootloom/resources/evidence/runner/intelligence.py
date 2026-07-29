"""Explainable task risk and verification recommendations for Personal Core."""

from __future__ import annotations

import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any


PLUGIN_LIB = Path(__file__).resolve().parents[3] / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
from rootloom_paths import is_security_domain_path, normalize_repo_path, path_words


ASSESSMENT_FORMAT = "rootloom-change-assessment-v1"
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
TIER_FOR_RISK = {"low": 0, "medium": 1, "high": 2}
MAX_PATCH_BYTES = 1024 * 1024
MAX_TASK_CHARS = 32 * 1024
MAX_CHANGED_PATHS = 1000
MAX_SIGNAL_PATHS = 20
MAX_COMMAND_DISCOVERY_BYTES = 256 * 1024
WORD = re.compile(r"[\w.-]+", re.UNICODE)
DOC_SUFFIXES = {".md", ".mdx", ".rst", ".png", ".svg", ".webp"}
DEPENDENCY_EXACT_NAMES = {
    "cargo.lock",
    "cargo.toml",
    "gemfile",
    "gemfile.lock",
    "go.mod",
    "go.sum",
    "gradle.lockfile",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pyproject.toml",
    "uv.lock",
    "yarn.lock",
}


def normalized_path(raw: str) -> str:
    return normalize_repo_path(raw, label="analysis path")


def tokens(value: str) -> set[str]:
    return {token.lower() for token in WORD.findall(value) if len(token) > 1}


def path_parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(path).parts)


def is_documentation_or_test(path: str) -> bool:
    parsed = PurePosixPath(path)
    parts = path_parts(path)
    name = parsed.name.lower()
    if any(part in {"doc", "docs", "example", "examples", "test", "tests", "fixtures"} for part in parts):
        return True
    if name.startswith(("readme", "changelog", "contributing", "license", "code_of_conduct")):
        return True
    if is_dependency_path(path):
        return False
    return parsed.suffix.lower() in DOC_SUFFIXES


def is_dependency_path(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    if name in DEPENDENCY_EXACT_NAMES:
        return True
    return bool(
        re.fullmatch(r"requirements(?:[._-][^/]*)?\.txt", name)
        or re.fullmatch(r"constraints(?:[._-][^/]*)?\.txt", name)
        or name.endswith("-lock.json")
        or name.endswith("-lock.yaml")
        or name.endswith("-lock.yml")
    )


def is_product_path(path: str) -> bool:
    if is_documentation_or_test(path):
        return False
    return True


def path_has(path: str, values: set[str]) -> bool:
    return bool(path_words(path) & values)


def add_signal(
    signals: dict[str, dict[str, Any]],
    signal_id: str,
    *,
    risk: str,
    reason: str,
    paths: list[str] | None = None,
) -> None:
    candidate = {
        "id": signal_id,
        "risk": risk,
        "minimum_tier": TIER_FOR_RISK[risk],
        "reason": reason,
        "paths": sorted(set(paths or []))[:MAX_SIGNAL_PATHS],
        "paths_truncated": len(set(paths or [])) > MAX_SIGNAL_PATHS,
    }
    existing = signals.get(signal_id)
    if existing is None or RISK_ORDER[risk] > RISK_ORDER[existing["risk"]]:
        signals[signal_id] = candidate
    elif paths:
        combined = sorted(set(existing["paths"]) | set(paths))
        existing["paths"] = combined[:MAX_SIGNAL_PATHS]
        existing["paths_truncated"] = existing["paths_truncated"] or len(combined) > MAX_SIGNAL_PATHS


def change_paths(
    changes: list[dict[str, str]], anticipated_paths: list[str]
) -> tuple[list[str], dict[str, str]]:
    operations: dict[str, str] = {}
    for item in changes:
        path = normalized_path(item["path"])
        status = item["status"]
        operations[path] = status
        if item.get("original_path"):
            operations[normalized_path(item["original_path"])] = status
    for raw in anticipated_paths:
        operations.setdefault(normalized_path(raw), "planned")
    return sorted(operations), operations


def semantic_match(text: str, english: set[str], localized: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return bool(tokens(lowered) & english) or any(value in text for value in localized)


def read_bounded_repository_text(path: Path, *, max_bytes: int) -> str:
    """Read one regular repository file without following a symlink or size drift."""

    if path.is_symlink():
        raise ValueError(f"repository command file must not be a symlink: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError(f"repository command file must be regular: {path}")
        raw = bytearray()
        while len(raw) <= max_bytes:
            chunk = os.read(descriptor, min(64 * 1024, max_bytes + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(descriptor)
        if (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError(f"repository command file changed during read: {path}")
        if len(raw) > max_bytes or after.st_size > max_bytes:
            raise ValueError(f"repository command file exceeds {max_bytes} bytes: {path}")
    finally:
        os.close(descriptor)
    return bytes(raw).decode("utf-8", errors="replace")


def repository_commands(repo: Path, risk: str) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    makefile = repo / "Makefile"
    targets: set[str] = set()
    try:
        text = read_bounded_repository_text(
            makefile, max_bytes=MAX_COMMAND_DISCOVERY_BYTES
        )
    except (FileNotFoundError, OSError, ValueError):
        text = ""
    if text:
        targets = set(re.findall(r"^([A-Za-z0-9_.-]+):", text, re.MULTILINE))
    if risk == "low" and "validate" in targets:
        suggestions.append(
            {"command": "make validate", "reason": "repository contract and documentation checks"}
        )
    elif "check" in targets:
        suggestions.append(
            {"command": "make check", "reason": "repository-wide validation and tests"}
        )
    elif "test" in targets:
        suggestions.append({"command": "make test", "reason": "repository test target"})
    elif (repo / "tests").is_dir():
        suggestions.append(
            {
                "command": "python3 -m unittest discover -s tests -p 'test_*.py'",
                "reason": "detected Python unittest tree",
            }
        )
    return suggestions


def verification_plan(
    repo: Path,
    *,
    product_scope: bool,
    has_paths: bool,
    signals: list[dict[str, Any]],
    risk: str,
    allow_repository_reads: bool,
) -> dict[str, Any]:
    signal_ids = {signal["id"] for signal in signals}
    behaviors: list[dict[str, str]] = []

    def require(item_id: str, behavior: str, reason: str) -> None:
        if any(item["id"] == item_id for item in behaviors):
            return
        behaviors.append({"id": item_id, "behavior": behavior, "reason": reason})

    if product_scope:
        require(
            "primary-behavior",
            "Exercise the user-visible or caller-visible behavior changed by this patch.",
            "A passing helper test does not prove the primary behavior.",
        )
        require(
            "owning-invariant",
            "Prove the invariant at the module or contract that owns the changed behavior.",
            "This distinguishes an owning fix from symptom suppression.",
        )
        require(
            "adjacent-path",
            "Exercise one negative, failure, rollback, or alternate path next to the change.",
            "Adjacent coverage challenges the strongest nearby counterexample.",
        )
    elif has_paths:
        require(
            "documentation-contract",
            "Validate local links, examples, synchronized translations, and rendered assets affected by the change.",
            "Documentation-only changes fail through broken public instructions or assets.",
        )
    else:
        require(
            "scope-needed",
            "Locate the owning paths and consumers before selecting implementation verification.",
            "Task text alone cannot identify the executable verification boundary.",
        )
    if signal_ids & {"authentication", "security"}:
        require(
            "auth-boundaries",
            "Verify success, invalid/expired credential, and unauthorized/insufficient-permission paths.",
            "Authentication and authorization regress at boundary conditions.",
        )
    if signal_ids & {"persistence", "migration"}:
        require(
            "data-compatibility",
            "Verify existing data, forward change, partial failure, and rollback or compensating repair.",
            "Persisted-state changes must account for old/new coexistence.",
        )
    if "money" in signal_ids:
        require(
            "financial-boundaries",
            "Verify rounding, idempotency, duplicate delivery, and failure/retry behavior.",
            "Money paths amplify small consistency errors.",
        )
    if signal_ids & {"concurrency", "state-machine"}:
        require(
            "ordering-and-races",
            "Verify competing orderings, repeated transitions, cancellation, and cleanup.",
            "Happy-path tests rarely expose race or state-transition defects.",
        )
    if "infrastructure" in signal_ids:
        require(
            "deployment-contract",
            "Validate configuration syntax, least privilege, rollout, failure detection, and rollback.",
            "Infrastructure changes affect execution outside the local process.",
        )
    if "public-contract" in signal_ids:
        require(
            "consumer-compatibility",
            "Verify current consumers plus one old/new or omitted/invalid input compatibility path.",
            "Public contracts fail at consumer boundaries, not only at the producer.",
        )
    if "destructive-change" in signal_ids:
        require(
            "destructive-effect",
            "Verify the exact deletion/rename set, dependent references, and a recovery or revert path.",
            "Destructive changes can pass tests while losing required state or assets.",
        )
    return {
        "status": "suggested-not-executed",
        "required_behaviors": behaviors,
        "suggested_commands": (
            repository_commands(repo, risk) if allow_repository_reads else []
        ),
    }


def code_signal_text(line: str) -> str:
    without_strings = re.sub(r'"(?:\\.|[^"\\])*"', " ", line)
    without_strings = re.sub(r"'(?:\\.|[^'\\])*'", " ", without_strings)
    if without_strings.lstrip().startswith(("#", "//", "/*", "*")):
        return ""
    return re.split(r"\s(?:#|//)", without_strings, maxsplit=1)[0]


def changed_patch_text(value: bytes, product_paths: list[str]) -> tuple[str, bool]:
    selected: list[str] = []
    selected_bytes = 0
    truncated = False
    product_markers = tuple(f"b/{path}" for path in product_paths)
    include_section = False
    binary_section = False
    for raw in io.BytesIO(value):
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line.startswith("diff --git "):
            include_section = any(
                _patch_header_contains_path(line, marker)
                for marker in product_markers
            )
            binary_section = False
            continue
        if not include_section:
            continue
        if line in {"GIT binary patch"} or line.startswith("Binary files "):
            binary_section = True
            continue
        if binary_section or not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        candidate = code_signal_text(line[1:]).strip()
        if not candidate:
            continue
        encoded_size = len(candidate.encode("utf-8", errors="replace")) + 1
        if selected_bytes + encoded_size > MAX_PATCH_BYTES:
            truncated = True
            continue
        selected.append(candidate)
        selected_bytes += encoded_size
    return "\n".join(selected), truncated


def _patch_header_contains_path(line: str, marker: str) -> bool:
    """Find one literal Git path in a normal or double-quoted diff header."""

    offset = 0
    while True:
        index = line.find(marker, offset)
        if index < 0:
            return False
        before = line[index - 1] if index else ""
        end = index + len(marker)
        after = line[end] if end < len(line) else ""
        if before in {" ", '"'} and after in {"", " ", '"'}:
            return True
        offset = index + 1


def analyze_change(
    repo: Path,
    *,
    task: str,
    anticipated_paths: list[str],
    changes: list[dict[str, str]],
    tracked_patch: bytes,
    declared_risk: str | None,
    reviewable_paths: list[str] | None = None,
    allow_repository_reads: bool = True,
) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    if len(task) > MAX_TASK_CHARS:
        raise ValueError(f"task text exceeds {MAX_TASK_CHARS} characters")
    if declared_risk is not None and declared_risk not in RISK_ORDER:
        raise ValueError(f"unsupported declared risk: {declared_risk}")
    paths, operations = change_paths(changes, anticipated_paths)
    normalized_reviewable = {
        normalized_path(path) for path in reviewable_paths or []
    }
    if len(paths) > MAX_CHANGED_PATHS:
        raise ValueError(f"change analysis exceeds {MAX_CHANGED_PATHS} paths")
    product_paths = [path for path in paths if is_product_path(path)]
    docs_or_tests_only = bool(paths) and all(is_documentation_or_test(path) for path in paths)
    signal_paths = product_paths or ([] if docs_or_tests_only else paths)
    signals: dict[str, dict[str, Any]] = {}

    if product_paths:
        add_signal(
            signals,
            "behavioral-code",
            risk="medium",
            reason="Product code or executable configuration changed.",
            paths=product_paths,
        )
    elif docs_or_tests_only:
        add_signal(
            signals,
            "docs-or-tests-only",
            risk="low",
            reason="Only documentation, examples, assets, fixtures, or tests are in scope.",
            paths=paths,
        )

    dependency_paths = [path for path in paths if is_dependency_path(path)]
    if dependency_paths:
        add_signal(
            signals,
            "dependency-supply-chain",
            risk="high",
            reason="A dependency manifest or lockfile changes executable supply-chain inputs.",
            paths=dependency_paths,
        )

    security_domain_paths = [
        path
        for path in signal_paths
        if is_security_domain_path(
            path,
            reviewable_paths=normalized_reviewable,
        )
    ]
    auth_paths = [
        path
        for path in security_domain_paths
        if path_has(path, {"auth", "authentication", "authorization", "oauth", "permission", "permissions", "token", "tokens"})
    ]
    if auth_paths:
        add_signal(
            signals,
            "authentication",
            risk="high",
            reason="Authentication, authorization, permission, or token behavior is in scope.",
            paths=auth_paths,
        )
    security_paths = [
        path
        for path in security_domain_paths
        if path not in auth_paths
        or path_has(
            path,
            {
                "security",
                "crypto",
                "credential",
                "credentials",
                "secret",
                "secrets",
            },
        )
    ]
    if security_paths:
        add_signal(
            signals,
            "security",
            risk="high",
            reason="Security or credential handling is in scope.",
            paths=security_paths,
        )
    persistence_paths = [
        path
        for path in signal_paths
        if path_has(path, {"database", "databases", "db", "model", "models", "persistence", "repository", "repositories", "schema", "schemas"})
        or PurePosixPath(path).suffix.lower() == ".sql"
    ]
    if persistence_paths:
        add_signal(
            signals,
            "persistence",
            risk="high",
            reason="Persisted data or schema ownership is in scope.",
            paths=persistence_paths,
        )
    migration_paths = [path for path in signal_paths if path_has(path, {"migration", "migrations", "migrate"})]
    if migration_paths:
        add_signal(
            signals,
            "migration",
            risk="high",
            reason="A data or schema migration path is in scope.",
            paths=migration_paths,
        )
    infrastructure_paths = [
        path
        for path in signal_paths
        if path.startswith(".github/workflows/")
        or path_has(path, {"docker", "terraform", "deploy", "deployment", "infra", "infrastructure", "k8s", "kubernetes"})
        or PurePosixPath(path).name.lower() == "dockerfile"
    ]
    if infrastructure_paths:
        add_signal(
            signals,
            "infrastructure",
            risk="high",
            reason="CI, deployment, container, or infrastructure behavior is in scope.",
            paths=infrastructure_paths,
        )
    money_paths = [path for path in signal_paths if path_has(path, {"billing", "invoice", "money", "payment", "payments", "price", "pricing"})]
    if money_paths:
        add_signal(
            signals,
            "money",
            risk="high",
            reason="Money, billing, pricing, or payment behavior is in scope.",
            paths=money_paths,
        )
    public_paths = [
        path
        for path in signal_paths
        if path_has(path, {"api", "cli", "contract", "contracts"})
        or PurePosixPath(path).name.lower() in {"package.json", "pyproject.toml", "plugin.json", "cargo.toml", "go.mod"}
    ]
    if public_paths:
        add_signal(
            signals,
            "public-contract",
            risk="high",
            reason="A public API, CLI, package, plugin, or persisted contract is in scope.",
            paths=public_paths,
        )

    deleted = [path for path, status in operations.items() if "D" in status or "R" in status]
    if deleted:
        add_signal(
            signals,
            "destructive-change",
            risk="high" if any(path_has(path, {"database", "db", "migration", "secret", ".env"}) for path in deleted) else "medium",
            reason="Deletion or rename changes the available path set and requires dependent-reference review.",
            paths=deleted,
        )
    top_levels = {PurePosixPath(path).parts[0] for path in product_paths}
    if len(product_paths) >= 12 or (len(product_paths) >= 6 and len(top_levels) >= 3):
        add_signal(
            signals,
            "broad-blast-radius",
            risk="high",
            reason="The change spans many product files or top-level ownership areas.",
            paths=product_paths,
        )

    patch_text, patch_text_truncated = changed_patch_text(tracked_patch, product_paths)
    semantic_text = f"{task}\n{patch_text}" if product_paths or not paths else ""
    if product_paths and semantic_match(
        task,
        {"bug", "defect", "fix", "regression", "repair"},
        ("修复", "缺陷", "回归", "故障"),
    ):
        add_signal(
            signals,
            "defect-repair",
            risk="medium",
            reason="The task describes a behavioral defect repair requiring root-cause alignment.",
            paths=product_paths,
        )
    if not paths and semantic_match(
        semantic_text,
        {"add", "build", "change", "fix", "implement", "refactor", "remove"},
        ("修改", "修复", "新增", "实现", "重构", "删除"),
    ):
        add_signal(
            signals,
            "behavioral-task",
            risk="medium",
            reason="The task describes a behavioral implementation or defect before paths are known.",
        )
    if semantic_match(semantic_text, {"concurrency", "concurrent", "race", "deadlock", "mutex", "lock"}, ("并发", "竞态", "死锁")):
        add_signal(
            signals,
            "concurrency",
            risk="high",
            reason="Task or tracked patch contains concurrency, race, or lock semantics.",
            paths=signal_paths,
        )
    if semantic_match(semantic_text, {"state-machine", "state_machine", "transition", "lifecycle"}, ("状态机", "状态转换", "生命周期")):
        add_signal(
            signals,
            "state-machine",
            risk="high",
            reason="State-machine or lifecycle transitions are in scope.",
            paths=signal_paths,
        )
    if semantic_match(
        semantic_text,
        {
            "access-token",
            "auth",
            "authentication",
            "authorization",
            "jwt",
            "login",
            "oauth",
            "permission",
            "refresh-token",
        },
        ("登录", "认证", "授权", "权限", "令牌"),
    ):
        add_signal(
            signals,
            "authentication",
            risk="high",
            reason="Task or tracked patch contains authentication or authorization semantics.",
            paths=signal_paths,
        )
    if semantic_match(semantic_text, {"migration", "database", "schema", "persisted"}, ("迁移", "数据库", "持久化", "数据结构")):
        add_signal(
            signals,
            "persistence",
            risk="high",
            reason="Task or tracked patch contains persisted-data or migration semantics.",
            paths=signal_paths,
        )
    if semantic_match(
        semantic_text,
        {"argparse", "command-line", "public-api", "public_contract", "add_argument"},
        ("公共接口", "命令行", "契约格式"),
    ):
        add_signal(
            signals,
            "public-contract",
            risk="high",
            reason="Task or tracked patch contains public API, CLI, or contract semantics.",
            paths=signal_paths,
        )
    if semantic_match(semantic_text, {"payment", "billing", "invoice", "money", "price"}, ("支付", "账单", "金额", "价格")):
        add_signal(
            signals,
            "money",
            risk="high",
            reason="Task or tracked patch contains money or billing semantics.",
            paths=signal_paths,
        )

    ordered_signals = sorted(
        signals.values(), key=lambda item: (-RISK_ORDER[item["risk"]], item["id"])
    )
    detected_risk = max(
        (item["risk"] for item in ordered_signals),
        key=lambda value: RISK_ORDER[value],
        default="low",
    )
    effective_risk = detected_risk
    if declared_risk and RISK_ORDER[declared_risk] > RISK_ORDER[effective_risk]:
        effective_risk = declared_risk
    risk_was_raised = bool(
        declared_risk and RISK_ORDER[detected_risk] > RISK_ORDER[declared_risk]
    )
    confidence = "high" if ordered_signals and paths else "medium" if ordered_signals else "low"
    return {
        "format": ASSESSMENT_FORMAT,
        "advisory": True,
        "changed_paths": paths,
        "detected_risk": detected_risk,
        "declared_risk": declared_risk,
        "effective_risk": effective_risk,
        "minimum_tier": TIER_FOR_RISK[detected_risk],
        "risk_was_raised": risk_was_raised,
        "confidence": confidence,
        "input_bounds": {
            "tracked_patch_truncated": patch_text_truncated,
            "maximum_paths": MAX_CHANGED_PATHS,
        },
        "signals": ordered_signals,
        "memory": {
            "matches": [],
            "stale": [],
            "warnings": [],
        },
        "verification_plan": verification_plan(
            repo,
            product_scope=bool(product_paths or (not paths and ordered_signals)),
            has_paths=bool(paths),
            signals=ordered_signals,
            risk=effective_risk,
            allow_repository_reads=allow_repository_reads,
        ),
        "limitations": [
            "Static signals cannot prove semantic risk or test sufficiency.",
            "Project Memory is read only with explicit opt-in and remains advisory.",
            "Suggested verification is not executed by the analyzer.",
        ],
    }
