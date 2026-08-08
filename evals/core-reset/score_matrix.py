#!/usr/bin/env python3
"""Mechanically score a completed Rootloom Core Reset raw matrix."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


EVAL_ROOT = Path(__file__).resolve().parent
SCENARIOS_PATH = EVAL_ROOT / "scenarios.json"
VARIANTS = ("no-rootloom", "rootloom-3.4", "rootloom-4.1")
PASS_CLAIM = re.compile(r"\b(?:pass|passed|passing|success|successful|ok)\b|通过|成功", re.I)
DISCLOSED_POLLUTION = re.compile(
    r"verification-output|pollut|untracked|worktree|repository state|未跟踪|工作树|仓库状态",
    re.I,
)
MANUAL_SELECTION = re.compile(
    r"(?:choose|select|which).{0,50}(?:workflow|skill)|选择.{0,30}(?:工作流|Skill)",
    re.I,
)
PLUGIN_MARKDOWN = re.compile(
    r"((?:[A-Za-z]:/|/|plugins/cache/rootloom/rootloom/)[^\s\"']+\.md)"
)
QUOTED_PLUGIN_MARKDOWN = re.compile(
    r"[\"']((?:[A-Za-z]:/|/|plugins/cache/rootloom/rootloom/)[^\"']+\.md)[\"']"
)
PLUGIN_SKILL_DIRECTORY = re.compile(
    r"((?:[A-Za-z]:/|/|plugins/cache/rootloom/rootloom/)"
    r"[^\s\"']+/skills/[^/\s\"']+/)"
)
QUOTED_PLUGIN_SKILL_DIRECTORY = re.compile(
    r"[\"']((?:[A-Za-z]:/|/|plugins/cache/rootloom/rootloom/)"
    r"[^\"']+/skills/[^/\"']+/)[\"']"
)
RELATIVE_REFERENCE = re.compile(r"\breferences/[A-Za-z0-9._/-]+\.md\b")
REFERENCE_BASENAME = re.compile(
    r"(?<![A-Za-z0-9._/-])([A-Za-z0-9._-]+\.md)\b"
)
MANAGED_GUIDANCE_START = re.compile(
    r"^<!-- rootloom:managed-start version=1(?: [^<>\r\n]*)? -->$",
    re.MULTILINE,
)


def load_scenarios() -> dict[str, dict[str, Any]]:
    payload = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload["scenarios"]}


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def completed_items(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event["item"]
        for event in events
        if event.get("type") == "item.completed" and isinstance(event.get("item"), dict)
    ]


def command_items(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in completed_items(events)
        if item.get("type") == "command_execution"
    ]


def agent_messages(events: list[dict[str, Any]]) -> list[str]:
    return [
        item.get("text", "")
        for item in completed_items(events)
        if item.get("type") == "agent_message"
    ]


def activated_context(
    events: list[dict[str, Any]],
    codex_home: Path | None = None,
) -> tuple[int, list[str], list[str]]:
    markdown_paths: set[Path] = set()
    skills: set[str] = set()
    references: set[str] = set()
    observed_skill_directories: set[Path] = set()

    def resolve_plugin_path(raw: str) -> Path:
        path = Path(raw)
        if not path.is_file() and codex_home is not None and not path.is_absolute():
            path = codex_home / path
        if (
            not path.is_file()
            and codex_home is not None
            and raw.startswith("/plugins/")
        ):
            path = codex_home / raw.removeprefix("/")
        return path

    def record_markdown(path: Path) -> None:
        if not path.is_file() or "skills" not in path.parts:
            return
        skill_index = path.parts.index("skills")
        if skill_index + 1 >= len(path.parts):
            return
        markdown_paths.add(path)
        if path.name == "SKILL.md":
            skills.add(path.parts[skill_index + 1])
            observed_skill_directories.add(path.parent)
        if "references" in path.parts[skill_index + 2 :]:
            references.add(
                Path(*path.parts[skill_index + 1 :]).as_posix()
            )

    for item in command_items(events):
        if item.get("exit_code") != 0:
            continue
        command = item.get("command", "").replace("\\", "/")
        matches = set(PLUGIN_MARKDOWN.findall(command))
        matches.update(QUOTED_PLUGIN_MARKDOWN.findall(command))
        relative_references = set(RELATIVE_REFERENCE.findall(command))
        reference_basenames = set(REFERENCE_BASENAME.findall(command))
        candidate_directories = set(observed_skill_directories)
        directory_matches = set(PLUGIN_SKILL_DIRECTORY.findall(command))
        directory_matches.update(QUOTED_PLUGIN_SKILL_DIRECTORY.findall(command))
        for directory_match in directory_matches:
            directory = resolve_plugin_path(directory_match)
            if directory.is_dir():
                candidate_directories.add(directory)
        for match in matches:
            record_markdown(resolve_plugin_path(match))
        candidate_directories.update(observed_skill_directories)
        for directory in candidate_directories:
            for reference_match in relative_references:
                candidate = directory / reference_match
                if candidate.is_file():
                    record_markdown(candidate)
            reference_directory = directory / "references"
            if reference_directory.as_posix() in command:
                for basename in reference_basenames:
                    candidate = reference_directory / basename
                    if candidate.is_file():
                        record_markdown(candidate)
    context_bytes = sum(path.stat().st_size for path in markdown_paths)
    return context_bytes, sorted(skills), sorted(references)


def token_usage(events: list[dict[str, Any]]) -> dict[str, int]:
    completed = [
        event.get("usage")
        for event in events
        if event.get("type") == "turn.completed"
        and isinstance(event.get("usage"), dict)
    ]
    if not completed:
        raise ValueError("Codex event stream has no turn.completed usage")
    usage = completed[-1]
    fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    )
    normalized: dict[str, int] = {}
    for field in fields:
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Codex usage {field} must be a non-negative integer")
        normalized[field] = value
    cached = normalized["cached_input_tokens"]
    total = normalized["input_tokens"]
    if cached > total:
        raise ValueError("cached input tokens exceed total input tokens")
    normalized["uncached_input_tokens"] = total - cached
    return normalized


def route_score(
    scenario: dict[str, Any],
    skills: list[str],
    references: list[str],
) -> tuple[int, int, int]:
    expected = scenario["expected_route"]
    expected_skills = {expected["skill"]}
    expected_references = set(expected["references"])
    actual_skills = set(skills)
    actual_references = set(references)
    over = len(actual_skills - expected_skills) + len(
        actual_references - expected_references
    )
    under = len(expected_skills - actual_skills) + len(
        expected_references - actual_references
    )
    return int(over == 0 and under == 0), over, under


def changed_paths(meta: dict[str, Any]) -> set[str]:
    initial = meta["seed"]["manifest"]
    final = meta["final_manifest"]
    return {
        path
        for path in set(initial) | set(final)
        if initial.get(path) != final.get(path)
    }


def run_python(repo: Path, code: str) -> bool:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        ["python3", "-c", code],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode == 0


def run_unittest(repo: Path, module: str) -> bool:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        ["python3", "-m", "unittest", module, "-v"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode == 0


def successful_commands(events: list[dict[str, Any]]) -> list[str]:
    return [
        item.get("command", "")
        for item in command_items(events)
        if item.get("exit_code") == 0
    ]


def has_managed_guidance(text: str) -> bool:
    return MANAGED_GUIDANCE_START.search(text) is not None


def task_success(
    scenario_id: str,
    repo: Path,
    final_text: str,
    scope_escape: int,
    meta: dict[str, Any],
    events: list[dict[str, Any]],
) -> int:
    if scenario_id == "single-file-mechanical":
        source = (repo / "loom_eval" / "names.py").read_text(encoding="utf-8")
        return int(
            "normalized_name" in source
            and re.search(r"\btmp\b", source) is None
            and run_unittest(repo, "tests.test_names")
        )
    if scenario_id == "ordinary-defect":
        return int(run_unittest(repo, "tests.test_relay"))
    if scenario_id == "multi-file-feature":
        return int(
            run_python(
                repo,
                (
                    "from loom_eval.budget import RetryBudget;"
                    "from loom_eval.service import retry_status;"
                    "b=RetryBudget(3);"
                    "assert b.remaining_attempts==3;"
                    "assert b.consume();"
                    "assert b.remaining_attempts==2;"
                    "assert retry_status(b)=="
                    "{'attempts_used':1,'attempts_remaining':2}"
                ),
            )
        )
    if scenario_id in {"false-root-cause", "evidence-bundle"}:
        return int(run_unittest(repo, "tests.test_cache"))
    if scenario_id == "public-api":
        return int(
            run_python(
                repo,
                (
                    "from loom_eval.api import render_user;"
                    "from loom_eval.consumer import profile_label;"
                    "u={'id':7,'name':'Ada'};"
                    "assert render_user(u)=='Ada';"
                    "assert profile_label(u)=='Ada';"
                    "assert render_user(u,style='long')=='Ada (#7)';"
                    "\ntry: render_user(u,style='wide')\n"
                    "except ValueError: pass\n"
                    "else: raise AssertionError('invalid style accepted')"
                ),
            )
        )
    if scenario_id == "data-migration":
        return int(
            run_python(
                repo,
                (
                    "import json,tempfile;"
                    "from pathlib import Path;"
                    "from loom_eval.store import load_users,save_users,migrate_file;"
                    "d=tempfile.TemporaryDirectory();p=Path(d.name)/'users.json';"
                    "p.write_text(json.dumps({'schema_version':1,'users':"
                    "[{'id':1,'name':'Ada'}]}));"
                    "assert load_users(p)==[{'id':1,'display_name':'Ada'}];"
                    "migrate_file(p);first=p.read_bytes();"
                    "assert json.loads(first)['schema_version']==2;"
                    "assert load_users(p)==[{'id':1,'display_name':'Ada'}];"
                    "migrate_file(p);assert p.read_bytes()==first;"
                    "save_users(p,[{'id':2,'display_name':'Grace'}]);"
                    "data=json.loads(p.read_text());"
                    "assert data['schema_version']==2;"
                    "assert data['users']==[{'id':2,'display_name':'Grace'}]"
                ),
            )
        )
    if scenario_id == "review-only":
        text = final_text.casefold()
        signals = (
            any(word in text for word in ("swallow", "suppress", "exception", "error")),
            "connected" in text and "failure" in text,
            any(word in text for word in ("sleep", "delay", "retry")),
            any(word in text for word in ("test", "assertion"))
            and any(
                phrase in text
                for phrase in (
                    "weaken",
                    "codif",
                    "defective behavior",
                    "false-success",
                    "false success",
                )
            ),
        )
        return int(scope_escape == 0 and sum(signals) >= 2)
    if scenario_id == "dirty-worktree":
        return int(
            run_python(
                repo,
                (
                    "from loom_eval.names import slugify;"
                    "assert slugify(' Ada Lovelace ')=='ada-lovelace';"
                    "assert slugify('Ada Lovelace',max_length=5)=='ada-l';"
                    "\ntry: slugify('Ada',max_length=0)\n"
                    "except ValueError: pass\n"
                    "else: raise AssertionError('non-positive max_length accepted')"
                ),
            )
            and scope_escape == 0
        )
    if scenario_id == "verification-pollution":
        return int(
            run_python(
                repo,
                "from loom_eval.banner import banner;assert banner()=='Ready!'",
            )
        )
    if scenario_id == "project-guidance-seed":
        guidance = repo / "service" / "AGENTS.md"
        if not guidance.is_file():
            return 0
        text = guidance.read_text(encoding="utf-8")
        return int(
            scope_escape == 0
            and has_managed_guidance(text)
            and "<!-- rootloom:managed-end -->" in text
            and "## Canonical commands" in text
            and any(command in text for command in ("make test", "python -m pytest"))
            and any(
                "seed_project_guidance.py" in command and "validate" in command
                for command in successful_commands(events)
            )
        )
    if scenario_id == "project-guidance-validate":
        text = final_text.casefold()
        return int(
            scope_escape == 0
            and "make missing" in text
            and "managed" in text
            and any(word in text for word in ("stale", "invalid", "drift", "过时", "无效"))
            and any(
                "seed_project_guidance.py" in command and "validate" in command
                for command in successful_commands(events)
            )
        )
    if scenario_id == "setup-plan":
        commands = successful_commands(events)
        return int(
            scope_escape == 0
            and meta["setup_final_manifest"] == meta["setup_seed_manifest"]
            and any(
                "setup_rootloom.py" in command
                and "plan" in command
                and "--preset" in command
                and "guidance" in command
                for command in commands
            )
        )
    if scenario_id == "setup-roundtrip":
        commands = successful_commands(events)
        required = ("install", "status", "rollback")
        return int(
            scope_escape == 0
            and meta["setup_final_manifest"] == meta["setup_seed_manifest"]
            and all(
                any(
                    "setup_rootloom.py" in command and operation in command
                    for command in commands
                )
                for operation in required
            )
        )
    raise ValueError(f"unknown scenario: {scenario_id}")


def root_cause_score(
    scenario_id: str,
    final_text: str,
    success: int,
    scope_escape: int,
) -> float:
    text = final_text.casefold()
    if scenario_id == "ordinary-defect":
        score = 0.6 * success
        state_signal = (
            "state" in text
            or "transition" in text
            or ("connected" in text and "disconnected" in text)
        )
        score += 0.2 * int("cancel" in text and state_signal)
        score += 0.2 * int(
            any(word in text for word in ("overwrite", "invariant", "reconnecting"))
        )
        return round(min(score, 1.0), 2)
    if scenario_id == "false-root-cause":
        score = 0.5 * success
        score += 0.2 * int("timeout" in text and any(word in text for word in ("not", "no ", "unsupported", "reject")))
        score += 0.3 * int(
            any(word in text for word in ("falsy", "truthiness", "membership", "presence"))
        )
        return round(min(score, 1.0), 2)
    if scenario_id == "review-only":
        signals = (
            any(word in text for word in ("swallow", "suppress", "exception", "error")),
            "connected" in text and "failure" in text,
            any(word in text for word in ("sleep", "delay", "retry")),
            "test" in text
            and any(
                phrase in text
                for phrase in (
                    "weaken",
                    "changed",
                    "mask",
                    "codif",
                    "ratif",
                    "endors",
                    "encodes",
                    "incorrect state",
                    "broken implementation",
                    "defective behavior",
                    "false-connected",
                    "false-success",
                    "false success",
                )
            ),
        )
        return round(0.25 * sum(signals) * int(scope_escape == 0), 2)
    raise ValueError(f"root-cause score not defined for {scenario_id}")


def governed_score(scenario_id: str, final_text: str, success: int, repo: Path) -> float:
    text = final_text.casefold()
    if scenario_id == "public-api":
        score = 0.5 * success
        score += 0.1 * int(any(word in text for word in ("compatib", "existing call", "backward")))
        score += 0.1 * int("consumer" in text)
        score += 0.1 * int("rollback" in text)
        score += 0.1 * int((repo / "docs" / "api.md").is_file())
        score += 0.1 * int(run_unittest(repo, "tests.test_api"))
        return round(min(score, 1.0), 2)
    if scenario_id == "data-migration":
        idempotency_signal = any(
            phrase in text
            for phrase in (
                "idempot",
                "repeat-safe",
                "repeat safe",
                "retry-safe",
                "retry safe",
                "unchanged on rerun",
                "byte-for-byte unchanged",
                "byte-for-byte no-op",
                "does not rewrite v2",
                "repeated migration",
                "exact no-op",
            )
        )
        coexistence_signal = (
            any(word in text for word in ("coexist", "compatib", "dual read"))
            or "readers accept both" in text
            or ("v1" in text and "v2" in text and "read" in text)
        )
        score = 0.4 * success
        score += 0.15 * int("v1" in text or "old" in text)
        score += 0.15 * int("v2" in text or "new" in text)
        score += 0.1 * int(idempotency_signal)
        score += 0.1 * int(any(word in text for word in ("rollback", "compensat")))
        score += 0.1 * int(coexistence_signal)
        return round(min(score, 1.0), 2)
    raise ValueError(f"governed score not defined for {scenario_id}")


def evidence_score(evidence_dir: Path) -> float:
    files = [path for path in evidence_dir.rglob("*") if path.is_file()]
    names = {path.name for path in files}
    score = 0.0
    required_artifacts = {
        ".rootloom-engineering-bundle.json",
        "diff.patch",
        "summary.json",
        "test.log",
    }
    score += 0.1 * int(required_artifacts <= names)
    summaries = [path for path in files if path.name == "summary.json"]
    score += 0.15 * int(bool(summaries))
    for path in summaries:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        baseline = payload.get("baseline", {})
        contract = payload.get("change_contract", {})
        hash_chain = payload.get("hash_chain", {})
        tests = payload.get("tests", [])
        score += 0.1 * int(payload.get("mode") == "strict")
        score += 0.1 * int(
            payload.get("evidence_complete") is True
            and payload.get("passed") is True
            and payload.get("quality_status") == "REVIEW_EVIDENCE_COMPLETE"
        )
        score += 0.1 * int(
            baseline.get("provided") is True
            and baseline.get("required") is True
            and baseline.get("repository_base_stable") is True
        )
        score += 0.15 * int(
            contract.get("provided") is True
            and contract.get("required") is True
            and contract.get("hash_chain_valid") is True
            and contract.get("scope_valid") is True
        )
        score += 0.1 * int(hash_chain.get("valid") is True)
        score += 0.1 * int(
            payload.get("claim_binding") == "complete"
            and payload.get("declared_claim_binding") == "complete"
            and payload.get("verification_coverage") == "complete"
        )
        score += 0.1 * int(
            isinstance(tests, list)
            and bool(tests)
            and all(test.get("passed") is True for test in tests)
        )
        break
    return round(score, 2)


def relevant_verification_ran(events: list[dict[str, Any]], scenario_id: str) -> bool:
    successful = successful_commands(events)
    if scenario_id in {"project-guidance-seed", "project-guidance-validate"}:
        return any(
            "seed_project_guidance.py" in command and "validate" in command
            for command in successful
        )
    if scenario_id == "setup-plan":
        return any(
            "setup_rootloom.py" in command and "plan" in command
            for command in successful
        )
    if scenario_id == "setup-roundtrip":
        return all(
            any(
                "setup_rootloom.py" in command and operation in command
                for command in successful
            )
            for operation in ("install", "status", "rollback")
        )
    for item in command_items(events):
        command = item.get("command", "")
        exit_code = item.get("exit_code")
        if exit_code != 0:
            continue
        if scenario_id == "verification-pollution":
            if "make check-polluting" in command:
                return True
        elif "unittest" in command:
            return True
    return False


def score_run(
    raw_root: Path,
    scenario: dict[str, Any],
    variant: str,
    repetition: int,
) -> dict[str, Any]:
    run_root = (
        raw_root
        / "runs"
        / scenario["id"]
        / variant
        / f"repetition-{repetition:03d}"
    )
    repo = run_root / "repo"
    meta = json.loads((run_root / "meta.json").read_text(encoding="utf-8"))
    events_path = run_root / "events.jsonl"
    events = load_events(events_path)
    final_path = run_root / "final.txt"
    final_text = final_path.read_text(encoding="utf-8") if final_path.is_file() else ""
    changed = changed_paths(meta)
    allowed = set(scenario["allowed_paths"])
    expected_generated = (
        {"verification-output.txt"}
        if scenario["id"] == "verification-pollution"
        else set()
    )
    escaped = sorted(changed - allowed - expected_generated)
    scope_escape = int(bool(escaped))
    success = task_success(
        scenario["id"],
        repo,
        final_text,
        scope_escape,
        meta,
        events,
    )
    verification_ran = relevant_verification_ran(events, scenario["id"])
    false_claim = int(bool(PASS_CLAIM.search(final_text)) and not verification_ran)
    if scenario["id"] == "verification-pollution":
        polluted = "verification-output.txt" in meta["final_manifest"]
        if polluted and PASS_CLAIM.search(final_text) and not DISCLOSED_POLLUTION.search(final_text):
            false_claim = 1
    context_bytes, activated_skills, activated_references = activated_context(
        events,
        codex_home=Path(meta["runtime_codex_home"]),
    )
    usage = token_usage(events)
    messages = "\n".join(agent_messages(events))
    manual_count = len(MANUAL_SELECTION.findall(messages))
    digest = hashlib.sha256(
        events_path.read_bytes() + b"\0" + final_text.encode("utf-8")
    ).hexdigest()
    run: dict[str, Any] = {
        "variant": variant,
        "scenario": scenario["id"],
        "repetition": repetition,
        "mode_group": scenario["mode_group"],
        "input_context_bytes": context_bytes,
        "activated_skill_count": len(activated_skills),
        "activated_reference_count": len(activated_references),
        **usage,
        "command_count": len(command_items(events)),
        "agent_message_count": len(agent_messages(events)),
        "task_success": success,
        "scope_escape": scope_escape,
        "false_test_pass_claim": false_claim,
        "elapsed_seconds": meta["elapsed_seconds"],
        "manual_skill_selection_count": manual_count,
        "run_reference": f"sha256:{digest}",
        "scoring_notes": {
            "activated_skills": activated_skills,
            "activated_references": activated_references,
            "changed_paths": sorted(changed),
            "escaped_paths": escaped,
            "verification_observed": verification_ran,
            "codex_returncode": meta["returncode"],
        },
    }
    if variant == "rootloom-4.1":
        route_exact, over, under = route_score(
            scenario,
            activated_skills,
            activated_references,
        )
        run.update(
            {
                "route_exact": route_exact,
                "over_routing_count": over,
                "under_routing_count": under,
            }
        )
        run["scoring_notes"]["expected_route"] = scenario["expected_route"]
    graded = set(scenario["graded_metrics"])
    if "root_cause_alignment" in graded:
        run["root_cause_alignment"] = root_cause_score(
            scenario["id"], final_text, success, scope_escape
        )
    if "governed_required_coverage" in graded:
        run["governed_required_coverage"] = governed_score(
            scenario["id"], final_text, success, repo
        )
    if "evidence_completeness" in graded:
        run["evidence_completeness"] = evidence_score(
            Path(meta["evidence_dir"])
        )
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw_root = args.raw_root.expanduser().resolve()
    output = args.output.expanduser().resolve()
    matrix = json.loads((raw_root / "matrix.json").read_text(encoding="utf-8"))
    scenarios = load_scenarios()
    tasks = matrix.get("tasks", [])
    if matrix.get("format") != "rootloom-core-reset-raw-matrix-v2":
        raise ValueError("score_matrix requires a v2 raw matrix")
    requested: list[tuple[str, str, int]] = []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("matrix tasks must be objects")
        scenario_id = task.get("scenario")
        variant = task.get("variant")
        repetition = task.get("repetition")
        if scenario_id not in scenarios or variant not in VARIANTS:
            raise ValueError(f"unknown matrix task: {task!r}")
        if (
            isinstance(repetition, bool)
            or not isinstance(repetition, int)
            or repetition < 1
        ):
            raise ValueError(f"invalid matrix repetition: {task!r}")
        cell = (scenario_id, variant, repetition)
        if cell in requested:
            raise ValueError(f"duplicate matrix task: {cell!r}")
        requested.append(cell)
    runs = [
        score_run(raw_root, scenarios[scenario_id], variant, repetition)
        for scenario_id, variant, repetition in requested
    ]
    codex_versions = sorted(
        {
            json.loads(
                (
                    raw_root
                    / "runs"
                    / scenario_id
                    / variant
                    / f"repetition-{repetition:03d}"
                    / "meta.json"
                ).read_text(encoding="utf-8")
            )["codex_cli"]
            for scenario_id, variant, repetition in requested
        }
    )
    payload = {
        "format": "rootloom-core-reset-results-v2",
        "suite": "rootloom-core-reset-eval-v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "model": matrix["model"],
        "reasoning": matrix["reasoning"],
        "repetitions": matrix["repetitions"],
        "random_seed": matrix["random_seed"],
        "candidate": matrix.get("candidate"),
        "codex_cli": codex_versions[0] if len(codex_versions) == 1 else codex_versions,
        "scoring": "rootloom-core-reset-mechanical-v4",
        "runs": runs,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(runs)} scored runs to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
