#!/usr/bin/env python3
"""Validate Rootloom Core and optional plugin repository contracts."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN = ROOT / "plugins" / "rootloom"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
HOOKS = PLUGIN / "hooks" / "hooks.json"
SKILLS = PLUGIN / "skills"
EVIDENCE = PLUGIN / "resources" / "evidence"
SYSTEM = PLUGIN / "assets" / "system"
PORTABLE_PLUGIN = ROOT / "portable" / "rootloom"
PORTABLE_MANIFEST = PORTABLE_PLUGIN / "plugin.json"
PORTABLE_SKILLS = PORTABLE_PLUGIN / "skills"
PORTABLE_SYNC = ROOT / "scripts" / "sync_portable_plugin.py"
HOST_ADAPTERS = ROOT / "adapters" / "rootloom"
HOST_ADAPTER_SYNC = ROOT / "scripts" / "sync_host_adapters.py"
IMPACT_TESTS = ROOT / "scripts" / "impact_tests.py"
MEMORY_PLUGIN = ROOT / "experiments" / "rootloom-memory"
MEMORY_MANIFEST = MEMORY_PLUGIN / ".codex-plugin" / "plugin.json"
MEMORY_SKILLS = MEMORY_PLUGIN / "skills"
EXPECTED_SKILLS = {
    "operating-code-review",
    "operating-coding-change",
    "project-guidance",
    "setup-rootloom",
}
EXPECTED_MEMORY_SKILLS = {"project-memory"}
EXPECTED_PORTABLE_SKILLS = {
    "operating-code-review",
    "operating-coding-change",
    "project-guidance",
}
AGENT_PLUGINS_SCHEMA = (
    "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
)
AGENT_PLUGIN_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
AGENT_SKILL_FIELDS = {
    "name",
    "description",
}
AGENT_PLUGIN_NAME = re.compile(
    r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$"
)
AGENT_SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
ACTION_USE = re.compile(r"^\s*uses:\s*[^\s@]+@([^\s#]+)", re.MULTILINE)
LOCAL_LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
HTML_SRC = re.compile(r'<(?:img|source)\b[^>]*\bsrc="([^"]+)"', re.IGNORECASE)
HTML_REF = re.compile(
    r'<(?:a|img|link|script|source)\b[^>]*\b(?:href|src)="([^"]+)"',
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b"),
)
VIBELOFT_SCRIPT_URL = "https://vibeloft.ai/telemetry/v1.js"
VIBELOFT_PRODUCT_ID = "b34aed90-7b26-4ca0-b420-e31177be66e1"
VIBELOFT_PRODUCTION_URL = "https://liyanqing90.github.io/rootloom/"
VIBELOFT_AUTH_KEY_SHA256 = "cbe18f13cd6245e2c27402ce96677486236c105a9c18e96be3f425ecfb9a85fc"
VIBELOFT_AUTH_KEY = re.compile(r"vl_web\.[A-Za-z0-9_-]{43}")


class WebDocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str | None]] = []
        self.meta: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script":
            self.scripts.append(attributes)
        elif tag == "meta":
            self.meta.append(attributes)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing file: {path.relative_to(ROOT)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON: {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"expected JSON object: {path.relative_to(ROOT)}")
        return {}
    return payload


def repository_files() -> list[Path]:
    excluded_parts = {
        ".git",
        "__pycache__",
        "node_modules",
        "outputs",
        "dist",
        "build",
        "tmp",
    }
    try:
        completed = subprocess.run(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        candidates = [
            ROOT / raw.decode("utf-8", "surrogateescape")
            for raw in completed.stdout.split(b"\0")
            if raw
        ]
    except (OSError, subprocess.CalledProcessError):
        candidates = [path for path in ROOT.rglob("*") if path.is_file()]
    return sorted(
        path
        for path in candidates
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & excluded_parts)
    )


def validate_marketplace(errors: list[str]) -> None:
    payload = load_json(MARKETPLACE, errors)
    if payload.get("name") != "rootloom":
        errors.append("marketplace name must be rootloom")
    plugins = payload.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 2:
        errors.append("marketplace must contain Core and optional Memory plugins")
        return
    actual = {
        entry.get("name"): entry.get("source")
        for entry in plugins
        if isinstance(entry, dict)
    }
    expected = {
        "rootloom": {"source": "local", "path": "./plugins/rootloom"},
        "rootloom-memory": {
            "source": "local",
            "path": "./experiments/rootloom-memory",
        },
    }
    if actual != expected:
        errors.append(f"marketplace plugin sources differ: {actual!r}")


def validate_memory_manifest(errors: list[str]) -> None:
    payload = load_json(MEMORY_MANIFEST, errors)
    if payload.get("name") != "rootloom-memory":
        errors.append("Memory plugin name must be rootloom-memory")
    version = payload.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append("Memory plugin version must be strict semver")
    if payload.get("skills") != "./skills/":
        errors.append("Memory plugin must expose only its local skills directory")
    interface = payload.get("interface")
    if not isinstance(interface, dict) or interface.get("displayName") != "Rootloom Memory":
        errors.append("Memory plugin interface metadata is missing")


def validate_manifest(errors: list[str]) -> None:
    payload = load_json(MANIFEST, errors)
    if payload.get("name") != "rootloom":
        errors.append("plugin name must be rootloom")
    version = payload.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append("plugin version must be strict semver")
    elif f"## [{version}]" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        errors.append("plugin version must have a CHANGELOG section")
    else:
        producer_contracts = {
            EVIDENCE / "runner" / "baseline.py": (
                f'PRODUCER_VERSION = "{version}"'
            ),
            EVIDENCE / "finalize_change.py": (
                f'"producer_version": "{version}"'
            ),
        }
        for path, marker in producer_contracts.items():
            if marker not in path.read_text(encoding="utf-8"):
                errors.append(
                    f"plugin and evidence producer versions differ: {path.relative_to(ROOT)}"
                )
    for field in ("description", "author", "homepage", "repository", "license", "skills"):
        if not payload.get(field):
            errors.append(f"plugin manifest is missing {field}")
    interface = payload.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin interface metadata is missing")
        return
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ):
        if not interface.get(field):
            errors.append(f"plugin interface is missing {field}")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or len(prompts) > 3:
        errors.append("plugin defaultPrompt must be a list with at most three entries")
    elif any(not isinstance(item, str) or len(item) > 128 for item in prompts):
        errors.append("plugin defaultPrompt entries must be strings <= 128 chars")
    public_copy = " ".join(
        str(value)
        for value in (
            payload.get("description", ""),
            interface.get("shortDescription", ""),
            interface.get("longDescription", ""),
        )
    ).casefold()
    if "inspectable" not in public_copy:
        errors.append("plugin positioning must describe an inspectable workflow")
    for overclaim in ("quality layer", "verifiable", "verified change"):
        if overclaim in public_copy:
            errors.append(f"plugin positioning overclaims assurance: {overclaim}")
    for field in ("composerIcon", "logo", "logoDark"):
        raw = interface.get(field)
        if not isinstance(raw, str) or not raw.startswith("./"):
            errors.append(f"plugin interface {field} must be relative")
            continue
        target = (PLUGIN / raw).resolve()
        if not target.is_relative_to(PLUGIN.resolve()) or not target.is_file():
            errors.append(f"plugin interface {field} does not resolve to a file")


def validate_agent_plugin_manifest_payload(
    payload: dict[str, Any],
    codex_payload: dict[str, Any],
    errors: list[str],
) -> None:
    unknown = set(payload) - AGENT_PLUGIN_FIELDS
    if unknown:
        errors.append(
            "portable plugin manifest has unknown fields: "
            + ", ".join(sorted(unknown))
        )
    if payload.get("$schema") != AGENT_PLUGINS_SCHEMA:
        errors.append("portable plugin manifest must target Agent Plugins 1.0.0")

    name = payload.get("name")
    if (
        not isinstance(name, str)
        or not 1 <= len(name) <= 64
        or AGENT_PLUGIN_NAME.fullmatch(name) is None
    ):
        errors.append("portable plugin name violates Agent Plugins constraints")

    for field in ("version", "description", "homepage", "repository", "license"):
        if not isinstance(payload.get(field), str):
            errors.append(f"portable plugin manifest field {field} must be a string")
    version = payload.get("version")
    if isinstance(version, str) and SEMVER.fullmatch(version) is None:
        errors.append("portable plugin version must be strict semver")

    author = payload.get("author")
    if not isinstance(author, dict):
        errors.append("portable plugin author must be an object")
    else:
        unknown_author = set(author) - {"name", "email", "url"}
        if unknown_author:
            errors.append(
                "portable plugin author has unknown fields: "
                + ", ".join(sorted(unknown_author))
            )
        if any(not isinstance(value, str) for value in author.values()):
            errors.append("portable plugin author values must be strings")

    keywords = payload.get("keywords")
    if not isinstance(keywords, list) or any(
        not isinstance(value, str) for value in keywords
    ):
        errors.append("portable plugin keywords must be an array of strings")

    extensions = payload.get("extensions")
    if extensions is not None and (
        not isinstance(extensions, dict)
        or any(not isinstance(value, dict) for value in extensions.values())
    ):
        errors.append("portable plugin extensions must map namespaces to objects")

    for field in ("name", "version", "author", "homepage", "repository", "license"):
        if payload.get(field) != codex_payload.get(field):
            errors.append(f"portable and Codex manifests differ for shared field: {field}")


def validate_native_manifest_isolation(
    errors: list[str], plugin_root: Path = PLUGIN
) -> None:
    portable_manifest = plugin_root / "plugin.json"
    if portable_manifest.exists() or portable_manifest.is_symlink():
        errors.append(
            "Codex-native plugin root must not contain plugin.json; "
            "it would suppress native Hook loading"
        )


def validate_portable_plugin(errors: list[str]) -> None:
    validate_native_manifest_isolation(errors)
    payload = load_json(PORTABLE_MANIFEST, errors)
    codex_payload = load_json(MANIFEST, errors)
    validate_agent_plugin_manifest_payload(payload, codex_payload, errors)

    if not PORTABLE_PLUGIN.is_dir():
        errors.append("missing portable Agent Plugins package")
        return
    root_entries = {path.name for path in PORTABLE_PLUGIN.iterdir()}
    if root_entries != {"LICENSE", "plugin.json", "skills"}:
        errors.append(
            "portable package root must contain only LICENSE, plugin.json, and skills"
        )

    actual_skills = {
        path.parent.name for path in PORTABLE_SKILLS.glob("*/SKILL.md")
    }
    if actual_skills != EXPECTED_PORTABLE_SKILLS:
        errors.append(
            "portable skill catalog mismatch: expected "
            + ", ".join(sorted(EXPECTED_PORTABLE_SKILLS))
            + "; found "
            + ", ".join(sorted(actual_skills))
        )
    if (PORTABLE_SKILLS / "setup-rootloom").exists():
        errors.append("portable package must not expose Codex setup")
    if any(PORTABLE_SKILLS.glob("*/agents")):
        errors.append("portable package must not include Codex agents metadata")

    resolved_root = PORTABLE_PLUGIN.resolve()
    for path in PORTABLE_PLUGIN.rglob("*"):
        if path.is_symlink():
            errors.append(
                f"portable package must not contain symlinks: {path.relative_to(ROOT)}"
            )
            continue
        if not path.resolve().is_relative_to(resolved_root):
            errors.append(
                f"portable package path escapes its root: {path.relative_to(ROOT)}"
            )

    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(PORTABLE_SYNC),
                "--output",
                str(PORTABLE_PLUGIN),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append(f"portable package synchronization check failed: {exc}")
    else:
        if completed.returncode != 0:
            detail = (completed.stdout + completed.stderr).strip()
            errors.append(f"portable package is not synchronized: {detail}")

    portable_guidance = PORTABLE_SKILLS / "project-guidance" / "scripts"
    native_guidance = SKILLS / "project-guidance" / "scripts"
    for name, source in (
        ("seed_project_guidance.py", native_guidance / "seed_project_guidance.py"),
        ("rootloom_lock.py", PLUGIN / "lib" / "rootloom_lock.py"),
    ):
        target = portable_guidance / name
        if not target.is_file() or target.is_symlink():
            errors.append(f"portable Project Guidance helper is missing or symlinked: {name}")
        elif target.read_bytes() != source.read_bytes():
            errors.append(f"portable Project Guidance helper differs from native source: {name}")


def validate_host_adapters(errors: list[str]) -> None:
    if not HOST_ADAPTERS.is_dir():
        errors.append("missing Rootloom host adapter templates")
        return
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(HOST_ADAPTER_SYNC),
                "--output",
                str(HOST_ADAPTERS),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append(f"host adapter synchronization check failed: {exc}")
    else:
        if completed.returncode != 0:
            detail = (completed.stdout + completed.stderr).strip()
            errors.append(f"host adapters are not synchronized: {detail}")

    shared_hooks = load_json(
        HOST_ADAPTERS
        / "vscode-copilot"
        / "template"
        / ".github"
        / "hooks"
        / "rootloom.json",
        errors,
    )
    if set(shared_hooks) != {"version", "hooks"}:
        errors.append(
            "shared VS Code/Copilot hook config must contain only version and hooks"
        )
    if type(shared_hooks.get("version")) is not int or shared_hooks.get("version") != 1:
        errors.append("shared VS Code/Copilot hook config version must be integer 1")
    shared_hook_map = shared_hooks.get("hooks")
    if not isinstance(shared_hook_map, dict) or set(shared_hook_map) != {"sessionStart"}:
        errors.append(
            "shared VS Code/Copilot hook config must contain only sessionStart"
        )

    capability = load_json(HOST_ADAPTERS / "capabilities.json", errors)
    if capability.get("format") != "rootloom-host-capabilities-v1":
        errors.append("host adapter capability contract format differs")
    baseline = capability.get("baseline")
    baseline_skills = baseline.get("skills") if isinstance(baseline, dict) else None
    if (
        not isinstance(baseline_skills, list)
        or any(not isinstance(item, str) for item in baseline_skills)
        or set(baseline_skills) != EXPECTED_PORTABLE_SKILLS
    ):
        errors.append("host adapter capability contract must expose the portable three-Skill baseline")
    context = baseline.get("session_context", {}) if isinstance(baseline, dict) else {}
    if not isinstance(context, dict) or context.get("access") != "read-only" or context.get("maximum_bytes") != 4096:
        errors.append("host adapter capability contract must bound read-only session context to 4 KiB")
    hosts = capability.get("hosts")
    if not isinstance(hosts, dict):
        errors.append("host adapter capability contract lacks host mappings")
    else:
        for host in ("cursor", "vscode", "github-copilot", "kiro"):
            mapping = hosts.get(host)
            if not isinstance(mapping, dict) or mapping.get("runtime_status") != "pending":
                errors.append(f"host adapter runtime status must remain pending: {host}")


def canonical_yaml_string(value: str) -> bool:
    if (
        not value
        or value != value.strip()
        or not value[0].isascii()
        or not value[0].isalpha()
        or any(character < " " or character > "~" for character in value)
        or ":" in value
        or "#" in value
    ):
        return False
    lowered = value.casefold()
    if lowered in {
        "null",
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
        ".nan",
        ".inf",
        "+.inf",
        "-.inf",
        "~",
    }:
        return False
    return re.fullmatch(
        r"[-+]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?", value
    ) is None


def frontmatter_fields(path: Path) -> dict[str, str] | None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
    if not match:
        return None
    body = match.group("body")
    if any(character != "\n" and not " " <= character <= "~" for character in body):
        return None
    fields: dict[str, str] = {}
    for raw_line in body.split("\n"):
        if not raw_line.strip():
            continue
        line_match = re.fullmatch(
            r"(?P<key>[a-z][a-z0-9-]*): (?P<value>[\x20-\x7e]+)", raw_line
        )
        if line_match is None:
            return None
        key = line_match.group("key")
        value = line_match.group("value")
        if key in fields or not canonical_yaml_string(value):
            return None
        fields[key] = value
    return fields


def validate_agent_skill(path: Path, errors: list[str]) -> None:
    fields = frontmatter_fields(path)
    relative = path.relative_to(ROOT)
    if fields is None:
        errors.append(f"Skill has invalid YAML frontmatter envelope: {relative}")
        return
    unknown = set(fields) - AGENT_SKILL_FIELDS
    if unknown:
        errors.append(
            f"Skill has unsupported frontmatter fields: {relative}: "
            + ", ".join(sorted(unknown))
        )
    name = fields.get("name", "")
    if (
        name != path.parent.name
        or len(name) > 64
        or AGENT_SKILL_NAME.fullmatch(name) is None
    ):
        errors.append(f"Skill frontmatter name violates Agent Skills: {relative}")
    description = fields.get("description", "")
    if not description or len(description) > 1024:
        errors.append(f"Skill description violates Agent Skills: {relative}")
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n.*?\n---\n(?P<body>.*)", text, re.DOTALL)
    if match is None or not match.group("body").strip():
        errors.append(f"Skill body must not be empty: {relative}")


def validate_skills(errors: list[str]) -> None:
    actual = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
    if actual != EXPECTED_SKILLS:
        errors.append(
            "skill catalog mismatch: expected "
            + ", ".join(sorted(EXPECTED_SKILLS))
            + "; found "
            + ", ".join(sorted(actual))
        )
    for name in sorted(actual):
        path = SKILLS / name / "SKILL.md"
        validate_agent_skill(path, errors)
        agent = SKILLS / name / "agents" / "openai.yaml"
        if not agent.is_file():
            errors.append(f"Skill is missing agents/openai.yaml: {name}")
    memory_actual = {
        path.parent.name for path in MEMORY_SKILLS.glob("*/SKILL.md")
    }
    if memory_actual != EXPECTED_MEMORY_SKILLS:
        errors.append(
            "Memory Skill catalog mismatch: expected project-memory; found "
            + ", ".join(sorted(memory_actual))
        )
    for name in sorted(memory_actual):
        path = MEMORY_SKILLS / name / "SKILL.md"
        validate_agent_skill(path, errors)
        if not (MEMORY_SKILLS / name / "agents" / "openai.yaml").is_file():
            errors.append(f"Memory Skill is missing agents/openai.yaml: {name}")
    for name in sorted(EXPECTED_PORTABLE_SKILLS):
        path = PORTABLE_SKILLS / name / "SKILL.md"
        if path.is_file():
            validate_agent_skill(path, errors)
    for name in actual:
        if (SKILLS / name / "SKILL.md").stat().st_size > 24 * 1024:
            errors.append(f"Skill exceeds the 24 KiB context budget: {name}")
    if any(EVIDENCE.rglob("SKILL.md")):
        errors.append("Evidence resources must not expose a discoverable Skill")
    forbidden = (
        SKILLS / "high-assurance-coding-change" / "SKILL.md",
        SYSTEM / "profiles" / "high-assurance.config.toml",
    )
    for path in forbidden:
        if path.exists():
            errors.append(f"Assurance artifact must not ship on main: {path.relative_to(ROOT)}")
    if any((SYSTEM / "agents").glob("*.toml")):
        errors.append("Personal Core must not ship custom-agent TOMLs")


def validate_core_reset_eval(errors: list[str]) -> None:
    suite = load_json(ROOT / "evals" / "core-reset" / "scenarios.json", errors)
    scenarios = suite.get("scenarios")
    if suite.get("format") != "rootloom-core-reset-eval-v2":
        errors.append("Core Reset evaluation format differs")
    if suite.get("variants") != [
        "no-rootloom",
        "rootloom-3.4",
        "rootloom-4.1",
    ]:
        errors.append("Core Reset evaluation variants differ")
    required_metrics = {
        "input_tokens",
        "cached_input_tokens",
        "uncached_input_tokens",
        "command_count",
        "agent_message_count",
        "route_exact",
        "over_routing_count",
        "under_routing_count",
    }
    metrics = suite.get("metrics")
    if (
        not isinstance(metrics, list)
        or any(not isinstance(metric, str) for metric in metrics)
        or not required_metrics.issubset(set(metrics))
    ):
        errors.append("Core Reset evaluation lacks v2 token or routing metrics")
    if not isinstance(scenarios, list) or len(scenarios) != 15:
        errors.append("Core Reset evaluation must contain exactly fifteen scenarios")
    elif len({item.get("id") for item in scenarios if isinstance(item, dict)}) != 15:
        errors.append("Core Reset evaluation scenario IDs must be unique")
    else:
        mode_skills = {
            "direct": "operating-coding-change",
            "scoped": "operating-coding-change",
            "governed": "operating-coding-change",
            "evidence": "operating-coding-change",
            "review": "operating-code-review",
            "guidance": "project-guidance",
            "setup": "setup-rootloom",
        }
        for item in scenarios:
            if not isinstance(item.get("allowed_paths"), list):
                errors.append(f"Core Reset scenario lacks allowed_paths: {item.get('id')}")
            if not isinstance(item.get("verification_command"), str):
                errors.append(
                    f"Core Reset scenario lacks verification_command: {item.get('id')}"
                )
            graded = item.get("graded_metrics")
            if not isinstance(graded, list) or "task_success" not in graded:
                errors.append(
                    f"Core Reset scenario must grade task_success: {item.get('id')}"
                )
            mode = item.get("mode_group")
            route = item.get("expected_route")
            if mode not in mode_skills or not isinstance(route, dict):
                errors.append(
                    f"Core Reset scenario lacks a valid mode/route: {item.get('id')}"
                )
                continue
            references = route.get("references")
            if (
                route.get("skill") != mode_skills[mode]
                or not isinstance(references, list)
                or any(
                    not isinstance(reference, str)
                    or reference.startswith("/")
                    or any(part in {"", ".", ".."} for part in Path(reference).parts)
                    or not reference.endswith(".md")
                    for reference in references
                )
                or len(set(references)) != len(references)
            ):
                errors.append(
                    f"Core Reset scenario route contract differs: {item.get('id')}"
                )
            elif mode in {"direct", "scoped"} and references:
                errors.append(
                    f"Routine Core Reset route must load no Reference: {item.get('id')}"
                )
        if {item.get("mode_group") for item in scenarios} != set(mode_skills):
            errors.append("Core Reset evaluation must cover every public mode group")
        regenerable = next(
            (
                item
                for item in scenarios
                if item.get("id") == "regenerable-versioned-artifact"
            ),
            None,
        )
        if (
            not isinstance(regenerable, dict)
            or regenerable.get("mode_group") != "scoped"
            or regenerable.get("expected_route")
            != {"skill": "operating-coding-change", "references": []}
            or "must reject v1" not in str(regenerable.get("prompt", ""))
            or "historical replay uses its matching old runtime"
            not in str(regenerable.get("prompt", ""))
        ):
            errors.append(
                "regenerable versioned artifact must remain current-only Scoped work"
            )
    historical_suite = load_json(
        ROOT / "evals" / "core-reset" / "scenarios-v1.json",
        errors,
    )
    if (
        historical_suite.get("format") != "rootloom-core-reset-eval-v1"
        or not isinstance(historical_suite.get("scenarios"), list)
        or len(historical_suite["scenarios"]) != 10
    ):
        errors.append("historical Core Reset v1 scenario suite differs")
    evaluator = ROOT / "evals" / "core-reset" / "evaluate.py"
    text = evaluator.read_text(encoding="utf-8")
    for marker in (
        "EXPECTED_SKILLS",
        "ordinary_change_context_reduction",
        "--require-behavioral",
        "--minimum-repetitions",
        "uncached_input_tokens",
        "bootstrap_ratio_interval",
        "rootloom-core-reset-mechanical-v5",
        "rootloom-3.4",
        "rootloom-4.1",
    ):
        if marker not in text:
            errors.append(f"Core Reset evaluator is missing {marker!r}")
    for path, markers in (
        (
            ROOT / "evals" / "core-reset" / "run_matrix.py",
            (
                "--output-root",
                "CODEX_HOME",
                "PYTHONDONTWRITEBYTECODE",
                "--ephemeral",
                "--repetitions",
                "--random-seed",
                "runtime-homes",
            ),
        ),
        (
            ROOT / "evals" / "core-reset" / "score_matrix.py",
            (
                "task_success",
                "scope_escape",
                "activated_context",
                "run_reference",
                "turn.completed",
                "uncached_input_tokens",
                "route_score",
                "runtime_codex_home",
                "PLUGIN_SKILL_DIRECTORY",
                "QUOTED_PLUGIN_MARKDOWN",
                "QUOTED_PLUGIN_SKILL_DIRECTORY",
                "MANAGED_GUIDANCE_START",
                "rootloom-core-reset-mechanical-v5",
                "is_generated_python_cache",
                "observed_skill_directories",
                "repeat-safe",
                "byte-for-byte unchanged",
                "repeated migration",
                "false-connected",
                "future schema accepted",
            ),
        ),
    ):
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"Core Reset tool {path.name} is missing {marker!r}"
                )
    result = load_json(
        ROOT / "evals" / "core-reset" / "results-2026-07-29.json",
        errors,
    )
    if result.get("format") != "rootloom-core-reset-results-v1":
        errors.append("recorded Core Reset result format differs")
    runs = result.get("runs")
    if not isinstance(runs, list) or len(runs) != 30:
        errors.append("recorded Core Reset result must contain exactly 30 runs")
    candidate = result.get("candidate")
    if (
        not isinstance(candidate, dict)
        or candidate.get("root") != "plugins/rootloom"
        or not re.fullmatch(r"[0-9a-f]{64}", str(candidate.get("tree_sha256", "")))
    ):
        errors.append("recorded Core Reset result must identify its Core tree digest")
    example = load_json(
        ROOT / "evals" / "core-reset" / "results.example.json",
        errors,
    )
    if (
        example.get("format") != "rootloom-core-reset-results-v2"
        or example.get("suite") != "rootloom-core-reset-eval-v2"
        or example.get("scoring") != "rootloom-core-reset-mechanical-v5"
        or example.get("repetitions") != 3
    ):
        errors.append("Core Reset v2 result example differs")
    retained = load_json(
        ROOT / "evals" / "core-reset" / "results-4.1.0.json",
        errors,
    )
    retained_runs = retained.get("runs")
    retained_candidate = retained.get("candidate")
    if (
        retained.get("format") != "rootloom-core-reset-results-v2"
        or retained.get("suite") != "rootloom-core-reset-eval-v2"
        or retained.get("scoring") != "rootloom-core-reset-mechanical-v4"
        or retained.get("repetitions") != 3
        or not isinstance(retained_runs, list)
        or len(retained_runs) != 126
        or not isinstance(retained_candidate, dict)
        or retained_candidate.get("root") != "plugins/rootloom"
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(retained_candidate.get("tree_sha256", "")),
        )
    ):
        errors.append("retained 4.1 behavioral result contract differs")
    elif len(
        {
            (
                run.get("variant"),
                run.get("scenario"),
                run.get("repetition"),
            )
            for run in retained_runs
            if isinstance(run, dict)
        }
    ) != 126:
        errors.append("retained 4.1 behavioral result cells must be unique")
    retained_report = (
        ROOT / "evals" / "core-reset" / "reports" / "4.1.0.md"
    ).read_text(encoding="utf-8")
    for marker in (
        "formal behavioral gate accepted",
        "14 scenarios × 3 variants × 3 repetitions = 126",
        "Reference overreach",
        "Routine uncached input",
        "previous efficiency failures are corrected",
        "route-scoped recomposition",
        "verification-pollution failure",
    ):
        if marker not in retained_report:
            errors.append(f"retained 4.1 report is missing {marker!r}")

    release_result = load_json(
        ROOT / "evals" / "core-reset" / "results-4.3.0.json",
        errors,
    )
    release_runs = release_result.get("runs")
    release_candidate = release_result.get("candidate")
    if (
        release_result.get("format") != "rootloom-core-reset-results-v2"
        or release_result.get("suite") != "rootloom-core-reset-eval-v2"
        or release_result.get("scoring") != "rootloom-core-reset-mechanical-v5"
        or release_result.get("repetitions") != 3
        or not isinstance(release_runs, list)
        or len(release_runs) != 135
        or not isinstance(release_candidate, dict)
        or release_candidate.get("root") != "plugins/rootloom"
        or release_candidate.get("tree_sha256")
        != "6714b0f887f47da0595c243edcba6d21f36ce1a2305cf66c6199c3225b1c1593"
    ):
        errors.append("retained 4.3.0 behavioral result contract differs")
    elif len(
        {
            (
                run.get("variant"),
                run.get("scenario"),
                run.get("repetition"),
            )
            for run in release_runs
            if isinstance(run, dict)
        }
    ) != 135:
        errors.append("retained 4.3.0 behavioral result cells must be unique")
    release_report = (
        ROOT / "evals" / "core-reset" / "reports" / "4.3.0.md"
    ).read_text(encoding="utf-8")
    for marker in (
        "formal behavioral gate accepted",
        "15 scenarios × 3 variants × 3 repetitions = 135",
        "45/45 tasks",
        "regenerable-versioned-artifact",
        "successful-pair elapsed",
        "Direct command count",
        "6714b0f887f47da0595c243edcba6d21f36ce1a2305cf66c6199c3225b1c1593",
    ):
        if marker not in release_report:
            errors.append(f"retained 4.3 report is missing {marker!r}")


def validate_hooks(errors: list[str]) -> None:
    payload = load_json(HOOKS, errors)
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict) or set(hooks) != {"SessionStart"}:
        errors.append("Personal Core must expose exactly one SessionStart Hook type")
        return
    entries = hooks["SessionStart"]
    if not isinstance(entries, list) or len(entries) != 1:
        errors.append("SessionStart must contain exactly one entry")
        return
    entry = entries[0]
    handlers = entry.get("hooks") if isinstance(entry, dict) else None
    if entry.get("matcher") != "startup|resume|clear":
        errors.append("SessionStart matcher must remain startup|resume|clear")
    if not isinstance(handlers, list) or len(handlers) != 1:
        errors.append("SessionStart must contain exactly one command")
        return
    command = handlers[0]
    raw = command.get("command", "") if isinstance(command, dict) else ""
    if "$PLUGIN_ROOT" not in raw or "run_component_hook.py" not in raw or "project-guidance-hook" not in raw:
        errors.append("SessionStart must route through the managed component gate")


def validate_guidance_structure(
    path: Path, errors: list[str], *, maximum_bytes: int = 24 * 1024
) -> None:
    """Check document integrity without prescribing workflow wording or minimum length."""
    if path.is_symlink() or not path.is_file():
        errors.append(f"guidance must be a regular non-symlink file: {path}")
        return
    data = path.read_bytes()
    if len(data) > maximum_bytes:
        errors.append(f"guidance exceeds its context budget: {path}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"guidance must be UTF-8: {path}")
        return
    if not re.search(r"(?m)^#\s+\S", text):
        errors.append(f"guidance must have a title: {path}")
    start = "<!-- rootloom:managed-start"
    end = "<!-- rootloom:managed-end -->"
    if start in text or end in text:
        if (
            text.count(start) != 1
            or text.count(end) != 1
            or text.find(end) < text.find(start)
            or not re.search(r"<!-- rootloom:managed-start version=\S+(?: [^\n]*?)? -->", text)
        ):
            errors.append(f"malformed guidance managed markers: {path}")


def validate_personal_contracts(errors: list[str]) -> None:
    global_guidance = SYSTEM / "AGENTS.md"
    global_text = global_guidance.read_text(encoding="utf-8")
    validate_guidance_structure(global_guidance, errors, maximum_bytes=4096)
    seeder_text = (
        SKILLS / "project-guidance" / "scripts" / "seed_project_guidance.py"
    ).read_text(encoding="utf-8")
    if "MAX_SESSION_CONTEXT_BYTES = 4 * 1024" not in seeder_text:
        errors.append("SessionStart additional context must remain capped at 4 KiB")
    if 'permission_mode == "plan"' not in seeder_text:
        errors.append("SessionStart project context must remain disabled in Plan sessions")
    intelligence_text = (EVIDENCE / "runner" / "intelligence.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "import rootloom_memory",
        "load_memory_matches",
        "include_project_memory",
    ):
        if forbidden in intelligence_text:
            errors.append(f"Core Evidence must not read Project Memory: {forbidden}")
    for path, label in (
        (
            EVIDENCE / "analyze_change.py",
            "Analyzer",
        ),
        (
            EVIDENCE / "finalize_change.py",
            "Finalizer",
        ),
    ):
        if '"--include-project-memory"' in path.read_text(encoding="utf-8"):
            errors.append(f"{label} must not expose Core Project Memory opt-in")
    if (PLUGIN / "lib" / "rootloom_memory.py").exists():
        errors.append("Rootloom Core must not ship the Project Memory reader")
    validate_guidance_structure(ROOT / "AGENTS.md", errors)
    for directory, label in (
        (ROOT / ".codex" / "plans", "one-time task plans"),
        (ROOT / "docs" / "releases", "repository publication records"),
    ):
        if directory.exists() and any(path.is_file() for path in directory.rglob("*")):
            errors.append(f"repository must not retain {label}: {directory.relative_to(ROOT)}")

    contracts = {
        PLUGIN / "hooks" / "run_component_hook.py": (
            "type(version) is not int",
            "version != 1",
            "component policy version must be the integer 1",
        ),
        PLUGIN / ".codex-plugin" / "plugin.json": (
            "bounded artifact context",
        ),
        SKILLS / "project-guidance" / "scripts" / "seed_project_guidance.py": (
            "temporary_project_context",
            "MAX_SESSION_CONTEXT_BYTES",
            "PACKAGE_SCRIPT_NAME",
            "_render_session_context",
            'permission_mode == "plan"',
            "creating or updating AGENTS.md",
        ),
        SKILLS / "operating-coding-change" / "scripts" / "artifact_context.py": (
            'RECEIPT_FORMAT = "rootloom-artifact-context-v1"',
            "MAX_ARTIFACTS = 16",
            "MAX_RECEIPT_BYTES = 24 * 1024",
            "hashlib.sha256",
            '"status": "cached" if cached is not None else "needs-analysis"',
            "artifact changed after prepare",
            "must not embed raw artifact data",
        ),
        SKILLS / "operating-coding-change" / "references" / "evidence-mode.md": (
            "resources/evidence/analyze_change.py",
            "begin_review.py",
            "seal_contract.py",
            "orchestrate_evidence.py",
            "finalize_change.py",
            "single-command Evidence convenience path",
            "heterogeneous governed evidence",
            "suggestions are plans",
            "--strict",
            "report Evidence Mode as unavailable",
        ),
        SKILLS / "operating-coding-change" / "references" / "evidence-contract.md": (
            "Baseline v2–v4",
            "Summary revision 5",
            "rootloom-change-contract-v1",
            "--confirm-dangerous-delete",
            "REVIEW_EVIDENCE_COMPLETE",
            "REVIEW_REQUIRED_WITH_REDACTIONS",
            "--reviewable-path",
        ),
        EVIDENCE / "analyze_change.py": (
            "analyze_change",
            "--declared-risk",
            "--write-baseline",
            "tracked_patch",
            "--max-capture-seconds",
            "--max-git-seconds",
            "--max-sensitive-paths",
        ),
        EVIDENCE / "begin_review.py": (
            "REVIEW_MANIFEST_FORMAT",
            "change-contract.draft.json",
            "--allow-all-paths",
            "--allow-dirty-baseline",
            "--reviewable-path",
            "baseline_sha256",
            "rename_directory_no_replace",
            "CONTRACT_DRAFT_SENTINEL",
            "--max-capture-seconds",
            "--max-git-seconds",
            "--max-sensitive-paths",
        ),
        EVIDENCE / "seal_contract.py": (
            "contract.seal.json",
            "change-contract.json",
            "contains_contract_placeholder",
            "CONTRACT_HASH_BASIS",
            "--recover",
            "validate_contract_seal",
        ),
        EVIDENCE / "orchestrate_evidence.py": (
            "prepare",
            "finish",
            "--semantic-review-confirmed",
            "CONTRACT_DRAFT_SENTINEL",
            "load_change_contract",
            "prepared-and-sealed",
        ),
        EVIDENCE / "runner" / "intelligence.py": (
            "rootloom-change-assessment-v1",
            "dependency-supply-chain",
            "suggested-not-executed",
            "Static signals cannot prove semantic risk",
            "allow_repository_reads",
            "read_bounded_repository_text",
        ),
        EVIDENCE / "runner" / "baseline.py": (
            "rootloom-change-baseline-v1",
            "rootloom-change-baseline-v2",
            "rootloom-change-baseline-v3",
            "rootloom-change-baseline-v4",
            "reviewable_paths",
            "intake-sealed",
            "run_id",
            "task_sha256",
            "sensitive_preservation",
            "write_new_baseline",
            "head_ref",
        ),
        EVIDENCE / "runner" / "change_contract.py": (
            "rootloom-change-contract-v1",
            "allowed_paths",
            "verification_claim_bindings",
            "structured_contract_claimed_commands",
            "segment",
            "verification_coverage",
        ),
        EVIDENCE / "runner" / "review_run.py": (
            "rootloom-review-run-v2",
            "rootloom-contract-seal-v1",
            "canonical-json-without-contract_sha256",
            "review_manifest_sha256",
            "unexpected or missing fields",
            "CONTRACT_DRAFT_SENTINEL",
        ),
        EVIDENCE / "runner" / "evidence_paths.py": (
            "validate_no_symlink_chain",
            "validate_outside_repository_storage",
            "Git common directory",
            "lstat",
            "fsync_directory",
            "rename_directory_no_replace",
        ),
        EVIDENCE / "runner" / "strict_json.py": (
            "duplicate JSON key",
            "non-standard JSON constant",
            "out-of-range JSON number",
        ),
        EVIDENCE / "runner" / "state.py": (
            "stable_repository_capture",
            "canonical_reviewable_paths",
            "git_index_path_tags",
            "reviewable_path_metadata",
            "reviewable path is ignored and cannot be captured reliably",
            "reviewable path is hidden by Git index flags",
            "reviewable path must have link count one",
            "reference_sensitive_metadata",
            "sensitive_change_quarantine",
            "target_sha256",
            "repository path traverses a symlink parent",
            "DEFAULT_MAX_GIT_SECONDS",
            "DEFAULT_MAX_CAPTURE_SECONDS",
            "DEFAULT_MAX_SENSITIVE_PATHS",
            "MAX_REVIEWABLE_PATHS",
            "sensitive_material_git_pathspecs",
            "CaptureDeadline",
            "run_command",
        ),
        EVIDENCE / "runner" / "process.py": (
            "output_bytes_observed",
            "process_tree_converged",
            "TerminateJobObject",
            "_controlled_tree_active",
        ),
        EVIDENCE / "finalize_change.py": (
            "diff.patch",
            "test.log",
            "summary.json",
            '"risk_assessment"',
            '"verification_plan"',
            '"quality_status"',
            '"evidence_complete"',
            '"verification_coverage"',
            '"claim_binding"',
            '"evidence_provenance"',
            '"exit_policy"',
            '"mode"',
            "--strict",
            "--strict-bundle-only",
            "--require-verified",
            '"sensitive_integrity"',
            '"declared_claim_binding"',
            '"removed_preexisting_paths"',
            '"evidence_files_preserved"',
            '"repository_base_preserved_during_verification"',
            '"sensitive_change_quarantine"',
            '"verification_sensitive_change_quarantine"',
            "invalidate_previous_summary",
            "validate_outside_repository_storage",
            "--max-patch-bytes",
            "--max-capture-seconds",
            "--max-git-seconds",
            "--max-sensitive-paths",
            '"capture_limits"',
            '"capture_duration_seconds"',
            '"reviewability_policy"',
            '"policy_provenance"',
            '"captured_files_provenance"',
            '"semantic_review"',
            "REVIEW_EVIDENCE_COMPLETE",
            "REVIEW_REQUIRED_WITH_REDACTIONS",
            "SEMANTIC_REVIEW_ASSERTED",
            "DANGEROUS_DELETE_EXIT",
            "REINTAKE_REQUIRED_EXIT",
            "reintake-required",
        ),
        MEMORY_SKILLS / "project-memory" / "SKILL.md": (
            ".project-memory/",
            "current source",
            "record-failure",
            "set-status",
            "--include-stale",
        ),
        MEMORY_SKILLS / "project-memory" / "scripts" / "project_memory.py": (
            "rootloom-project-context-v1",
            "deduplicated",
            "memory.lock",
            "project-memory directory must not be a symlink",
        ),
        MEMORY_PLUGIN / "lib" / "rootloom_memory.py": (
            "rootloom-project-memory-v1",
            "O_NOFOLLOW",
            "entries exceed",
        ),
        PLUGIN / "lib" / "rootloom_paths.py": (
            "REVIEWABLE_ENV_TEMPLATE_NAMES",
            "PUBLIC_CERTIFICATE_SUFFIXES",
            "AMBIGUOUS_SENSITIVE_MATERIAL_SUFFIXES",
            "AMBIGUOUS_STRONG_KEY_CONTEXTS",
            "STRONG_SENSITIVE_MATERIAL_SUFFIXES",
            "MAX_REVIEWABLE_PATHS",
            "privkey.pem",
            "privatekey.pem",
            "ed25519-key.pem",
            "service-account.json",
            "is_sensitive_material_path",
            "is_security_domain_path",
            "is_protected_deletion_path",
            "validate_reviewable_paths",
            "normalize_reviewable_paths",
            "PROTECTED_STATE_SUFFIXES",
            "sensitive_material_git_pathspecs",
        ),
        SKILLS / "setup-rootloom" / "scripts" / "setup_rootloom.py": (
            '"personal": FULL_CAPABILITIES',
            '"autonomy"',
            'CAPABILITY_ALIASES = {"command-safety": "autonomy"}',
            'PRESET_ALIASES = {"engineering": "personal"}',
            "simple_lock",
            "rootloom-simple-backup-v1",
            "TRANSACTION_PATH",
            "TRANSACTION_FORMAT",
            "rootloom-setup-transaction-v1",
            "recover_pending_transaction",
            "pending_transaction_payload",
            "refusing rollback because",
            "MANAGED_START_PREFIX",
            "merge_agents_bytes",
            "installed_target_hash",
            "malformed Rootloom managed markers",
            'operation="upgrade"',
            "drifted_paths",
            'selected.add("global-policy")',
        ),
        SKILLS / "setup-rootloom" / "agents" / "openai.yaml": (
            "plan, install, inspect, update, or roll back Rootloom",
            "allow_implicit_invocation: true",
        ),
        IMPACT_TESTS: (
            "GROUP_MODULES",
            "select_groups",
            "FULL_FALLBACK_PATHS",
            "shared test infrastructure",
            "unclassified changed path",
            "canonical_full",
            "full_matrix",
            "include_untracked",
            'choices=("primary", "python", "portable")',
        ),
        SYSTEM / "rules" / "rootloom.rules": (
            "never grants task authority",
            "persistent Standard",
            'pattern = ["git", "push"]',
            'pattern = ["gh", "pr", ["create", "merge"]]',
            'pattern = ["gh", "release", "create"]',
            'pattern = ["gh", "release", "delete"]',
        ),
        PORTABLE_SYNC: (
            "PORTABLE_SKILLS",
            "plugin.schema.json",
            "unexpected portable file",
            "refusing to overwrite output with unexpected files",
        ),
        HOST_ADAPTER_SYNC: (
            "rootloom-host-capabilities-v1",
            "static-and-synthetic-only",
            "unexpected host adapter file",
            "refusing to overwrite output with unexpected files",
        ),
        ROOT / "README.md": (
            "Rootloom 4 Core",
            "An inspectable personal engineering workflow for Codex.",
            "codex/enterprise-assurance",
            "Archived Assurance Edition",
            "Optional Autonomy",
            "Optional Evidence resources",
            "Rootloom Memory",
            "$project-guidance",
            "$project-memory",
            "analyze_change.py",
            "quality_status",
            "--write-baseline",
            "--strict",
            "seal_contract.py",
            "orchestrate_evidence.py",
            "core-reset-release-eval",
            "two consecutive bounded captures",
            "material metadata change",
            "newly discovered ignored addition",
            "Git common directory",
            "Installation is complete after those two commands",
            "Persistent across tasks",
            "Full is never inferred",
            "REVIEW_EVIDENCE_COMPLETE",
            "REVIEW_REQUIRED_WITH_REDACTIONS",
            "evidence_complete",
            "--max-capture-seconds",
            "is_sensitive_material_path",
            "--reviewable-path",
            "reviewability_policy",
            "policy_provenance",
            "reintake-required",
            "assume-unchanged",
            "not a content-aware secret scanner",
            "Website telemetry",
            "official VibeLoft browser runtime",
            "portable/rootloom/",
            "Agent Plugins 1.0.0",
            "duplicate-Skill precedence",
            "Runtime compatibility requires evidence of a real post-cutover consumer",
            "Artifact Context Lane",
            "make check-changed BASE=origin/main",
        ),
        ROOT / "README.zh-CN.md": (
            "Rootloom 4 Core",
            "面向 Codex 的可检查个人工程工作流。",
            "codex/enterprise-assurance",
            "Archived Assurance Edition",
            "Optional Autonomy",
            "Optional Evidence Resources",
            "Rootloom Memory",
            "$project-guidance",
            "$project-memory",
            "analyze_change.py",
            "quality_status",
            "--write-baseline",
            "--strict",
            "seal_contract.py",
            "orchestrate_evidence.py",
            "core-reset-release-eval",
            "连续两次有界采集",
            "材料元数据变化",
            "新发现的 Ignored 新增",
            "Git Common Directory",
            "两条命令完成后插件即安装完毕",
            "跨任务持久",
            "所有权限绝不会被自动推断",
            "REVIEW_EVIDENCE_COMPLETE",
            "REVIEW_REQUIRED_WITH_REDACTIONS",
            "evidence_complete",
            "--max-capture-seconds",
            "is_sensitive_material_path",
            "--reviewable-path",
            "reviewability_policy",
            "policy_provenance",
            "reintake-required",
            "assume-unchanged",
            "不是内容感知型 Secret Scanner",
            "网站遥测",
            "VibeLoft 官方浏览器运行时",
            "portable/rootloom/",
            "Agent Plugins 1.0.0",
            "同名 Skill 的优先级",
            "Artifact Context Lane",
            "make check-changed BASE=origin/main",
        ),
        ROOT / "index.html": (
            "Make code changes you can explain.",
            "data-language-toggle",
            "data-workflow-image",
            "rootloom-loom-en.webp",
            "rootloom-loom-zh.webp",
            "codex plugin marketplace add liyanqing90/rootloom",
            "codex plugin add rootloom@rootloom",
            "$operating-coding-change",
            "Completion should say what happened.",
            "https://vibeloft.ai/telemetry/v1.js",
            'data-vl-product-id="b34aed90-7b26-4ca0-b420-e31177be66e1"',
            "Agent Plugins preview",
            "portable/rootloom",
        ),
        ROOT / "site" / "styles.css": (
            "--canvas:",
            "--font-sans:",
            ".workflow-rail",
            ".evidence-section",
            ".copy-status",
            "@media (prefers-reduced-motion: reduce)",
        ),
        ROOT / "site" / "main.js": (
            'rootloom-language',
            "navigator.clipboard",
            "setLocalizedText",
            "让每一次代码修改",
            "data-workflow-image",
            "data-copy",
            "docAgentPlugins",
            "portable/rootloom",
        ),
        ROOT / ".github" / "workflows" / "pages.yml": (
            "actions/configure-pages@983d7736d9b0ae728b81ab479565c72886d7745b",
            "actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b",
            "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
            "pages: write",
            "id-token: write",
            "GitHub Pages artifact must not contain symlinks",
        ),
        ROOT / ".github" / "workflows" / "release-evidence.yml": (
            '      - "v*"',
            "make telemetry-check",
            "make validate",
            "tests.test_setup_rootloom",
            "tests.test_portable_plugin",
        ),
        ROOT / "PRODUCT.md": (
            "## Register",
            "brand",
            "Tactile, rigorous, candid",
            "## Accessibility & Inclusion",
        ),
        ROOT / "DESIGN.md": (
            "Creative North Star: \"The Working Loom\"",
            "## 1. Overview",
            "## 2. Colors",
            "## 3. Typography",
            "## 4. Elevation",
            "## 5. Components",
            "## 6. Do's and Don'ts",
        ),
        ROOT / "scripts" / "verify_vibeloft_runtime.py": (
            "EXPECTED_RUNTIME_SHA256",
            "0901374715934a0234cda527cd95fd4d3c66c989fddd672d06c9df3f43d05bf5",
            "VibeLoft-Telemetry",
            "VibeLoft AWS API",
            "governed zero-egress browser review",
        ),
        ROOT / "docs" / "decisions" / "2026-07-17-vibeloft-web-telemetry.md": (
            "Status: accepted",
            "official VibeLoft runtime",
            "registered production origin",
            "GPC/DNT",
            "Rootloom will not install a telemetry package",
            "Rollback is a Git revert",
        ),
        ROOT / "docs" / "setup.md": (
            "gh pr merge 123 --merge",
            "gh release create v1.0.0",
            "Standard persists across tasks",
            "catastrophic recursive-deletion hard deny",
            "transaction journal",
            "resumes the exact staged target set",
            "portable/rootloom/",
            "Agent Plugins portable preview",
        ),
        ROOT / "docs" / "setup.zh-CN.md": (
            "gh pr merge 123 --merge",
            "gh release create v1.0.0",
            "普通权限跨任务持久",
            "灾难性递归删除的硬拒绝",
            "事务日志",
            "恢复精确的暂存目标集合",
            "portable/rootloom/",
            "Agent Plugins 可移植预览",
        ),
        ROOT / "docs" / "maturity.md": (
            "Pull-request CI derives focused component tests",
            "fails closed to the full suite",
            "one canonical full Python 3.11",
            "full supported",
            "path-gated pinned Codex compatibility",
        ),
        ROOT / "docs" / "maturity.zh-CN.md": (
            "Pull Request CI 按变更路径选择组件测试",
            "失败关闭到全量套件",
            "一次规范性的 Python 3.11 全量",
            "完整支持 Python 矩阵",
            "按路径触发的固定版本 Codex 兼容任务",
        ),
        ROOT / "docs" / "agent-plugins.md": (
            "Agent Plugins 1.0.0 is currently a Working Draft",
            "portable/rootloom/",
            "One package, host-specific loaders",
            "chat.pluginLocations",
            "copilot --plugin-dir",
            "Import power from a folder",
            "Rootloom has no current cloud install channel",
            "Change, Review",
            "Evidence Mode",
            "duplicate-Skill precedence",
            "python3 scripts/sync_portable_plugin.py --write",
            "canonical, single-line Agent Skills",
            "~/.cursor/plugins/local/rootloom",
            "codex plugin remove rootloom@rootloom",
            "Plugin removal alone",
            "Artifact Context identity/cache/24 KiB receipt",
            "cache-miss fixture to run in a no-history worker",
        ),
        ROOT / "docs" / "agent-plugins.zh-CN.md": (
            "Agent Plugins 1.0.0 当前仍是 Working Draft",
            "portable/rootloom/",
            "一份通用包，不同加载入口",
            "chat.pluginLocations",
            "copilot --plugin-dir",
            "Import power from a folder",
            "Rootloom 当前没有 Cloud 安装渠道",
            "Change、Review",
            "Evidence Mode",
            "同名 Skill 的优先级",
            "python3 scripts/sync_portable_plugin.py --write",
            "规范单行子集",
            "~/.cursor/plugins/local/rootloom",
            "codex plugin remove rootloom@rootloom",
            "只删除",
            "Artifact Context 身份/缓存/24 KiB 回执",
            "缓存未命中 Fixture 在无历史 Worker 中运行",
        ),
        ROOT / "docs" / "decisions" / "2026-07-14-tiered-authorization-modes.md": (
            "Status: accepted",
            "Single action",
            "Standard",
            "Full",
            "persistent cross-task default",
            "catastrophic recursive deletion",
        ),
        ROOT / "docs" / "decisions" / "2026-07-15-evidence-honest-strict-review.md": (
            "Status: accepted",
            "REVIEW_EVIDENCE_COMPLETE",
            "REVIEW_REQUIRED_WITH_REDACTIONS",
            "SEMANTIC_REVIEW_ASSERTED",
            "--max-git-seconds",
            "--max-sensitive-paths",
            "--recover",
        ),
        ROOT / "docs" / "decisions" / "2026-07-15-sensitive-material-and-capture-bounds.md": (
            "Status: accepted",
            "is_sensitive_material_path",
            "is_security_domain_path",
            "CaptureDeadline",
            "rootloom-change-baseline-v3",
            "rootloom-change-baseline-v4",
            "Summary revision 5",
            "--reviewable-path",
            "ignored reviewable files",
            "assume-unchanged",
            "OpenSSL",
            "evidence_complete",
        ),
        ROOT / "docs" / "decisions" / "2026-07-16-personal-core-product-boundaries.md": (
            "Status: accepted",
            "Core — Change, Review, Guidance",
            "Optional Autonomy",
            "Optional Evidence",
            "Experimental Project Memory",
            "Archived Assurance Edition",
            "reintake-required",
            "verified-quality layer",
        ),
        ROOT / "docs" / "decisions" / "2026-07-29-rootloom-4-core-reset.md": (
            "Status: accepted",
            "exactly four public Skills",
            "rootloom-memory",
            "Baseline v2–v4",
            "Summary revision 5",
            "behavioral matrix",
        ),
        ROOT / "docs" / "decisions" / "2026-07-29-rootloom-4.1-efficiency-loop.md": (
            "Status: accepted",
            "three repetitions",
            "orchestrate_evidence.py",
            "Baseline v2–v4",
            "package-script",
        ),
        ROOT / "docs" / "decisions" / "2026-08-08-agent-plugins-portable-preview.md": (
            "Status: accepted",
            "portable/rootloom/",
            "Agent Plugins 1.0.0 preview",
            "Use that one package unchanged across Cursor, VS Code, GitHub Copilot, Kiro",
            "does not load plugin Hooks",
            "fails closed when explicit Evidence Mode is requested",
        ),
        ROOT / "docs" / "decisions" / "2026-08-08-agent-plugins-portable-preview.zh-CN.md": (
            "Status: accepted",
            "portable/rootloom/",
            "Agent Plugins 1.0.0 预览",
            "Cursor、VS Code、GitHub Copilot、Kiro",
            "不加载插件 Hook",
            "Evidence Mode",
        ),
        ROOT / "docs" / "decisions" / "2026-08-08-unified-host-capability-baseline.md": (
            "Status: accepted",
            "Supersedes:",
            "exactly three standard Skills",
            "adapters/rootloom/",
            "static and synthetic checks",
            "runtime smokes",
            "permission enforcement remains host-owned",
        ),
        ROOT / "docs" / "decisions" / "2026-08-08-unified-host-capability-baseline.zh-CN.md": (
            "Status: accepted",
            "Supersedes:",
            "精确暴露三个标准 Skills",
            "adapters/rootloom/",
            "静态与合成检查",
            "运行冒烟",
            "权限执行仍由 Host 拥有",
        ),
        ROOT / "docs" / "decisions" / "2026-08-13-artifact-context-lane.md": (
            "Status: accepted",
            "Artifact Context Lane",
            "no inherited conversation",
            "24 KiB",
            "Already-recorded attachments cannot be removed",
            "## Compatibility",
            "## Migration / Coexistence",
            "## Rollback / Replay",
            "## Residual Risk",
        ),
        ROOT / "docs" / "decisions" / "2026-08-13-artifact-context-lane.zh-CN.md": (
            "Status: accepted",
            "Artifact Context Lane",
            "不继承会话历史",
            "24 KiB",
            "已经记录的附件不能被删除",
            "## Compatibility",
            "## Migration / Coexistence",
            "## Rollback / Replay",
            "## Residual Risk",
        ),
        ROOT / "docs" / "decisions" / "2026-08-10-regenerable-contract-compatibility-boundary.md": (
            "Status: accepted",
            "Regenerable internal artifacts remain Scoped",
            "rollback restores the complete old release",
            "historical replay uses the matching old runtime",
            "real post-cutover consumer",
            "adds no Evidence format",
        ),
        ROOT / "docs" / "decisions" / "2026-08-10-regenerable-contract-compatibility-boundary.zh-CN.md": (
            "状态：accepted",
            "可再生内部产物默认保持 Scoped",
            "回滚恢复完整旧版本",
            "历史回放使用匹配的旧运行时",
            "真实旧消费者",
            "不新增 Evidence 格式",
        ),
        ROOT / "docs" / "decisions" / "2026-08-10-impact-scoped-verification.md": (
            "Status: accepted",
            "Impact-scoped verification is the default",
            "scripts/impact_tests.py",
            "fail closed to the full suite",
            "one canonical full suite",
            "No wire format",
        ),
        ROOT / "docs" / "decisions" / "2026-08-10-impact-scoped-verification.zh-CN.md": (
            "状态：accepted",
            "默认使用影响范围内的精准验证",
            "scripts/impact_tests.py",
            "失败关闭到全量套件",
            "一次规范性全量套件",
            "不改变",
        ),
        ROOT / "docs" / "migration-4.1.md": (
            "orchestrate_evidence.py",
            "core-reset-release-eval",
            "semantic-review-confirmed",
        ),
        ROOT / "docs" / "migration-4.1.zh-CN.md": (
            "orchestrate_evidence.py",
            "core-reset-release-eval",
            "semantic-review-confirmed",
        ),
        PLUGIN / "AGENTS.md": (
            "exact integer `version: 1`",
            "SessionStart project-context Hook is read-only",
        ),
        EVIDENCE / "AGENTS.md": (
            "wire formats are frozen",
            "reintake-required",
        ),
        SKILLS / "setup-rootloom" / "AGENTS.md": (
            "Public presets are only",
            "`autonomy` is the canonical",
        ),
        MEMORY_SKILLS / "project-memory" / "AGENTS.md": (
            "Project Memory is experimental",
        ),
        ROOT / "CONTRIBUTING.md": (
            "Versioning public contracts",
            "Patch:",
            "Minor:",
            "Major:",
            "evidence_complete",
            "Published tags and Releases are immutable",
            "portable/rootloom/",
            "sync_portable_plugin.py",
            "make check-changed BASE=origin/main",
            "Impact-scoped verification is the default",
        ),
        ROOT / "CONTRIBUTING.zh-CN.md": (
            "公共契约版本规则",
            "Patch：",
            "Minor：",
            "Major：",
            "evidence_complete",
            "Tag 与 Release 保持不可变",
            "portable/rootloom/",
            "sync_portable_plugin.py",
            "make check-changed BASE=origin/main",
            "默认使用影响范围内的精准验证",
        ),
        ROOT / "docs" / "diagram" / "architecture-en.svg": (
            "Authorization Modes",
            "Single Action",
            "Standard",
            "Full",
            "Four-entry Core",
            "Rootloom Memory",
            "Archived Assurance Edition",
            "Inspectable",
        ),
        ROOT / "docs" / "diagram" / "architecture-zh.svg": (
            "授权模式",
            "本条命令",
            "普通权限",
            "所有权限",
            "四入口核心",
            "根织记忆",
            "已归档保障版",
            "可检查",
        ),
    }
    for path, needles in contracts.items():
        if not path.is_file():
            errors.append(f"missing contract file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"missing contract {needle!r} in {path.relative_to(ROOT)}")
    rules_text = (SYSTEM / "rules" / "rootloom.rules").read_text(encoding="utf-8")
    if 'decision = "prompt"' in rules_text:
        errors.append("Rootloom Rules must not duplicate semantic authorization with prompt decisions")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for forbidden in ("macos-strict-runner", "high-assurance-coding-change"):
        if forbidden in ci:
            errors.append(f"CI retains Assurance-only surface: {forbidden}")
    for required in (
        "@openai/codex@0.147.0",
        "make compatibility-smoke",
        "make portable-compatibility-smoke",
        "Select impact scope",
        "scripts/impact_tests.py select",
        "scripts/impact_tests.py run",
        "needs.scope.outputs.python-edge",
        "needs.scope.outputs.full-matrix",
        "fetch-depth: 0",
        'cron: "43 2 * * 0"',
    ):
        if required not in ci:
            errors.append(f"CI is missing release compatibility gate: {required}")
    compatibility = (
        ROOT / ".github" / "workflows" / "codex-compatibility.yml"
    ).read_text(encoding="utf-8")
    for required in (
        "make validate",
        "make compatibility-smoke",
        "make portable-compatibility-smoke",
    ):
        if required not in compatibility:
            errors.append(
                f"scheduled Codex compatibility is missing release gate: {required}"
            )
    if "make check" in compatibility:
        errors.append("scheduled Codex compatibility must not repeat the full unit suite")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in (
        "check:",
        "check-changed:",
        "--include-untracked",
        "validate:",
        "test:",
        "test-setup:",
        "test-guidance:",
        "test-packaging:",
        "test-change:",
        "test-evidence:",
        "test-memory:",
        "test-web:",
        "compatibility-smoke:",
        "portable-compatibility-smoke:",
        "telemetry-check:",
        "core-reset-eval:",
    ):
        if target not in makefile:
            errors.append(f"Makefile is missing {target}")


def validate_python(errors: list[str]) -> None:
    for path in sorted(
        (PLUGIN, MEMORY_PLUGIN, ROOT / "tests", ROOT / "scripts", ROOT / "evals"),
        key=str,
    ):
        candidates = path.rglob("*.py") if path.is_dir() else ()
        for candidate in candidates:
            if "__pycache__" in candidate.parts:
                continue
            try:
                ast.parse(candidate.read_text(encoding="utf-8"), filename=str(candidate))
            except (OSError, SyntaxError, UnicodeDecodeError) as exc:
                errors.append(f"invalid Python: {candidate.relative_to(ROOT)}: {exc}")


def validate_links(errors: list[str]) -> None:
    documents = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "index.html"] + sorted(
        (ROOT / "docs").glob("*.md")
    )
    for path in documents:
        text = path.read_text(encoding="utf-8")
        references = (
            HTML_REF.findall(text)
            if path.suffix == ".html"
            else LOCAL_LINK.findall(text) + HTML_SRC.findall(text)
        )
        for raw in references:
            target = raw.strip().strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            target = target.replace("%20", " ")
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken local link in {path.relative_to(ROOT)}: {raw}")


def validate_web_telemetry(errors: list[str], files: list[Path]) -> None:
    index = ROOT / "index.html"
    index_text = index.read_text(encoding="utf-8")
    parser = WebDocumentParser()
    parser.feed(index_text)
    if f'<link rel="canonical" href="{VIBELOFT_PRODUCTION_URL}">' not in index_text:
        errors.append("website canonical URL differs from the registered VibeLoft production origin")
    if f'<meta property="og:url" content="{VIBELOFT_PRODUCTION_URL}">' not in index_text:
        errors.append("website Open Graph URL differs from the registered VibeLoft production origin")
    initializers = [script for script in parser.scripts if script.get("src") == VIBELOFT_SCRIPT_URL]
    if len(initializers) != 1:
        errors.append("website must contain exactly one official VibeLoft initializer")
    else:
        initializer = initializers[0]
        if "defer" not in initializer:
            errors.append("VibeLoft initializer must remain deferred")
        if initializer.get("data-vl-product-id") != VIBELOFT_PRODUCT_ID:
            errors.append("VibeLoft product ID differs from the registered website")
        auth_key = initializer.get("data-vl-auth-key") or ""
        if not VIBELOFT_AUTH_KEY.fullmatch(auth_key):
            errors.append("VibeLoft browser auth key has an invalid public credential format")
        elif hashlib.sha256(auth_key.encode()).hexdigest() != VIBELOFT_AUTH_KEY_SHA256:
            errors.append("VibeLoft browser auth key differs from the configured product credential")

    html_entries = [path for path in files if path.suffix.lower() == ".html"]
    if html_entries != [index]:
        errors.append("GitHub Pages must keep one global HTML entry with one telemetry initializer")

    credential_paths: list[Path] = []
    for path in files:
        if path.suffix.lower() not in {".css", ".html", ".js", ".json", ".md", ".py", ".yml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        credential_paths.extend(path for _ in VIBELOFT_AUTH_KEY.finditer(text))
    if credential_paths != [index]:
        rendered = ", ".join(str(path.relative_to(ROOT)) for path in credential_paths) or "none"
        errors.append(f"VibeLoft browser auth key must appear only in index.html; found: {rendered}")

    host_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (index, ROOT / "site" / "main.js", ROOT / "site" / "styles.css")
    )
    for forbidden in (
        "https://api.vibeloft.ai/api/v1/telemetry/events",
        "VibeLoftTelemetry",
        "trackPageView",
        "data-vl-endpoint",
        "supabase",
    ):
        if forbidden.casefold() in host_sources.casefold():
            errors.append(f"website host code must not own or bypass VibeLoft runtime behavior: {forbidden}")

    csp = next(
        (
            meta.get("content") or ""
            for meta in parser.meta
            if (meta.get("http-equiv") or "").casefold() == "content-security-policy"
        ),
        None,
    )
    if csp is not None:
        if "https://vibeloft.ai" not in csp:
            errors.append("website CSP script-src must allow https://vibeloft.ai")
        if "https://api.vibeloft.ai" not in csp:
            errors.append("website CSP connect-src must allow https://api.vibeloft.ai")


def validate_workflows(errors: list[str]) -> None:
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for reference in ACTION_USE.findall(text):
            if not re.fullmatch(r"[0-9a-f]{40}", reference):
                errors.append(f"workflow action is not pinned to a commit: {path.relative_to(ROOT)}: {reference}")


def validate_assets(errors: list[str]) -> None:
    svg_paths = (
        sorted(PLUGIN.rglob("*.svg"))
        + sorted((ROOT / "assets").glob("*.svg"))
        + sorted((ROOT / "docs" / "diagram").glob("*.svg"))
    )
    for path in svg_paths:
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            errors.append(f"invalid SVG: {path.relative_to(ROOT)}: {exc}")
    architecture_diagrams = {
        ROOT / "docs" / "diagram" / "architecture-en.svg": "en",
        ROOT / "docs" / "diagram" / "architecture-zh.svg": "zh",
    }
    version_label = re.compile(r"(?i)\bv?\d+\.\d+(?:\.\d+)?\b")
    for path, language in architecture_diagrams.items():
        try:
            root = ET.parse(path).getroot()
        except (FileNotFoundError, ET.ParseError):
            continue
        visible_text = " ".join(
            "".join(element.itertext())
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] in {"title", "desc", "text"}
        )
        if version_label.search(visible_text):
            errors.append(f"architecture diagram must not bind a version: {path.relative_to(ROOT)}")
        if language == "en" and re.search(r"[\u3400-\u9fff]", visible_text):
            errors.append(f"English architecture diagram contains Chinese text: {path.relative_to(ROOT)}")
        if language == "zh" and re.search(r"[A-Za-z]", visible_text):
            errors.append(f"Chinese architecture diagram contains English text: {path.relative_to(ROOT)}")
    required_images = {
        ROOT / "assets" / "rootloom-brand.webp": b"RIFF",
        ROOT / "site" / "assets" / "rootloom-loom.webp": b"RIFF",
        ROOT / "site" / "assets" / "rootloom-loom-en.webp": b"RIFF",
        ROOT / "site" / "assets" / "rootloom-loom-zh.webp": b"RIFF",
        ROOT / "docs" / "diagram" / "architecture-en.svg": b"<svg",
        ROOT / "docs" / "diagram" / "architecture-en@2x.png": b"\x89PNG\r\n\x1a\n",
        ROOT / "docs" / "diagram" / "architecture-zh.svg": b"<svg",
        ROOT / "docs" / "diagram" / "architecture-zh@2x.png": b"\x89PNG\r\n\x1a\n",
    }
    for path, signature in required_images.items():
        try:
            header = path.read_bytes()[: max(12, len(signature))]
        except FileNotFoundError:
            errors.append(f"missing public image: {path.relative_to(ROOT)}")
            continue
        if not header.startswith(signature):
            errors.append(f"invalid public image: {path.relative_to(ROOT)}")
        if path.suffix == ".webp" and header[8:12] != b"WEBP":
            errors.append(f"invalid WebP image: {path.relative_to(ROOT)}")


def validate_secrets(errors: list[str], files: list[Path]) -> None:
    suffixes = {
        ".css",
        ".html",
        ".js",
        ".json",
        ".md",
        ".py",
        ".rules",
        ".toml",
        ".yaml",
        ".yml",
    }
    for path in files:
        if "tests" in path.parts:
            continue
        if path.suffix.lower() not in suffixes and path.name not in {"Makefile", "AGENTS.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret in {path.relative_to(ROOT)}")
                break


def main() -> int:
    errors: list[str] = []
    validate_marketplace(errors)
    validate_manifest(errors)
    validate_portable_plugin(errors)
    validate_host_adapters(errors)
    validate_memory_manifest(errors)
    validate_skills(errors)
    validate_core_reset_eval(errors)
    validate_hooks(errors)
    validate_personal_contracts(errors)
    validate_python(errors)
    validate_links(errors)
    files = repository_files()
    validate_web_telemetry(errors, files)
    validate_workflows(errors)
    validate_assets(errors)
    validate_secrets(errors, files)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Rootloom Core repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
