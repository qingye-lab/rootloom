#!/usr/bin/env python3
"""Run the Rootloom Core Reset scenarios in isolated Codex homes and repositories."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import time
from typing import Any


EVAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVAL_ROOT.parents[1]
FIXTURE_ROOT = EVAL_ROOT / "fixture"
SCENARIOS_PATH = EVAL_ROOT / "scenarios.json"
VARIANTS = ("no-rootloom", "rootloom-3.4", "rootloom-4.1")
FIXED_GIT_DATE = "2026-07-29T00:00:00Z"


def load_scenarios() -> dict[str, dict[str, Any]]:
    payload = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload["scenarios"]}


def copy_contents(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def run_checked(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def file_manifest(root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.relative_to(root).parts:
            continue
        manifest[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return manifest


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            not path.is_file()
            or "__pycache__" in relative.parts
            or path.suffix == ".pyc"
        ):
            continue
        data = path.read_bytes()
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(data)
    return digest.hexdigest()


def git_status(root: Path) -> list[str]:
    completed = run_checked(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=root,
    )
    return completed.stdout.splitlines()


def prepare_seed(output_root: Path, scenario_id: str) -> Path:
    seed = output_root / "seeds" / scenario_id
    if seed.exists():
        raise FileExistsError(f"seed already exists: {seed}")
    seed.mkdir(parents=True)
    copy_contents(FIXTURE_ROOT / "common", seed)
    copy_contents(FIXTURE_ROOT / "scenarios" / scenario_id, seed)
    run_checked(["git", "init", "-q"], cwd=seed)
    run_checked(["git", "config", "user.name", "Rootloom Eval"], cwd=seed)
    run_checked(
        ["git", "config", "user.email", "rootloom-eval@example.invalid"],
        cwd=seed,
    )
    run_checked(["git", "add", "."], cwd=seed)
    git_env = dict(os.environ)
    git_env["GIT_AUTHOR_DATE"] = FIXED_GIT_DATE
    git_env["GIT_COMMITTER_DATE"] = FIXED_GIT_DATE
    run_checked(["git", "commit", "-qm", f"fixture: {scenario_id}"], cwd=seed, env=git_env)
    copy_contents(FIXTURE_ROOT / "dirty" / scenario_id, seed)
    seed_meta = {
        "scenario": scenario_id,
        "head": run_checked(["git", "rev-parse", "HEAD"], cwd=seed).stdout.strip(),
        "status": git_status(seed),
        "manifest": file_manifest(seed),
    }
    (seed / ".git" / "rootloom-eval-seed.json").write_text(
        json.dumps(seed_meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return seed


def stream_codex(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
) -> int:
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        returncode = process.returncode
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        returncode = 124
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return returncode


def execute_run(
    *,
    codex_binary: str,
    output_root: Path,
    seed: Path,
    scenario: dict[str, Any],
    variant: str,
    codex_home: Path,
    repetition: int,
    model: str,
    reasoning: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    repetition_name = f"repetition-{repetition:03d}"
    run_root = output_root / "runs" / scenario["id"] / variant / repetition_name
    repo = run_root / "repo"
    if run_root.exists():
        raise FileExistsError(f"run already exists: {run_root}")
    run_root.mkdir(parents=True)
    shutil.copytree(seed, repo, symlinks=True)
    runtime_home = (
        output_root
        / "runtime-homes"
        / scenario["id"]
        / variant
        / repetition_name
    )
    shutil.copytree(codex_home, runtime_home, symlinks=True)
    evidence_dir = (
        output_root
        / "evidence"
        / scenario["id"]
        / variant
        / repetition_name
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    setup_home = (
        output_root
        / "setup-homes"
        / scenario["id"]
        / variant
        / repetition_name
    )
    setup_home.mkdir(parents=True, exist_ok=True)
    setup_seed_manifest = file_manifest(setup_home)
    final_path = run_root / "final.txt"
    stdout_path = run_root / "events.jsonl"
    stderr_path = run_root / "stderr.txt"
    env = dict(os.environ)
    env["CODEX_HOME"] = str(runtime_home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["ROOTLOOM_EVAL_EVIDENCE_DIR"] = str(evidence_dir)
    env["ROOTLOOM_EVAL_SETUP_HOME"] = str(setup_home)
    argv = [
        codex_binary,
        "exec",
        "--ephemeral",
        "--json",
        "--color",
        "never",
        "--ignore-rules",
        "--model",
        model,
        "--sandbox",
        "workspace-write",
        "--config",
        f'model_reasoning_effort="{reasoning}"',
        "--config",
        'service_tier="default"',
        "--config",
        'approval_policy="never"',
        "--cd",
        str(repo),
        "--output-last-message",
        str(final_path),
    ]
    if scenario["id"] == "evidence-bundle":
        argv.extend(["--add-dir", str(evidence_dir)])
    if scenario["mode_group"] == "setup":
        argv.extend(["--add-dir", str(setup_home)])
    argv.append(scenario["prompt"])
    started_at = datetime.now(UTC)
    started = time.monotonic()
    returncode = stream_codex(
        argv,
        cwd=repo,
        env=env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_seconds=timeout_seconds,
    )
    elapsed = time.monotonic() - started
    seed_meta = json.loads(
        (repo / ".git" / "rootloom-eval-seed.json").read_text(encoding="utf-8")
    )
    meta = {
        "format": "rootloom-core-reset-raw-run-v2",
        "variant": variant,
        "scenario": scenario["id"],
        "repetition": repetition,
        "model": model,
        "reasoning": reasoning,
        "codex_cli": run_checked([codex_binary, "--version"], cwd=repo).stdout.strip(),
        "started_at": started_at.isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "returncode": returncode,
        "seed": seed_meta,
        "final_status": git_status(repo),
        "final_manifest": file_manifest(repo),
        "final_message_path": str(final_path),
        "events_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "evidence_dir": str(evidence_dir),
        "setup_home": str(setup_home),
        "setup_seed_manifest": setup_seed_manifest,
        "setup_final_manifest": file_manifest(setup_home),
        "runtime_codex_home": str(runtime_home),
    }
    (run_root / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta


def parse_mapping(values: list[str], required_variants: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for value in values:
        variant, separator, raw_path = value.partition("=")
        if not separator or variant not in VARIANTS:
            raise ValueError(f"expected VARIANT=/absolute/home, got {value!r}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Codex home does not exist: {path}")
        mapping[variant] = path
    missing = set(required_variants) - set(mapping)
    if missing:
        raise ValueError(f"missing Codex homes for {sorted(missing)}")
    return mapping


def matrix_tasks(
    scenario_ids: list[str],
    variants: list[str],
    repetitions: int,
    random_seed: int,
) -> list[tuple[str, str, int]]:
    tasks = [
        (scenario_id, variant, repetition)
        for scenario_id in scenario_ids
        for variant in variants
        for repetition in range(1, repetitions + 1)
    ]
    random.Random(random_seed).shuffle(tasks)
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--home", action="append", default=[])
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--variant", action="append", choices=VARIANTS)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning", default="xhigh")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--random-seed", type=int, default=20260729)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--codex", default=shutil.which("codex") or "codex")
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 10:
        raise SystemExit("--repetitions must be from 1 to 10")
    if not 1 <= args.workers <= 12:
        raise SystemExit("--workers must be from 1 to 12")

    output_root = args.output_root.expanduser().resolve()
    if output_root == REPO_ROOT or REPO_ROOT in output_root.parents:
        raise SystemExit("raw evaluation output must remain outside the repository")
    marker = output_root / ".rootloom-core-reset-eval"
    if output_root.exists() and any(output_root.iterdir()) and not marker.is_file():
        raise SystemExit(
            "non-empty output root lacks .rootloom-core-reset-eval ownership marker"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    marker.touch(exist_ok=True)
    selected_variants = args.variant or list(VARIANTS)
    homes = parse_mapping(args.home, selected_variants)
    scenarios = load_scenarios()
    selected_scenarios = args.scenario or list(scenarios)
    unknown = set(selected_scenarios) - set(scenarios)
    if unknown:
        raise SystemExit(f"unknown scenarios: {sorted(unknown)}")
    seeds = {
        scenario_id: prepare_seed(output_root, scenario_id)
        for scenario_id in selected_scenarios
    }
    tasks = matrix_tasks(
        selected_scenarios,
        selected_variants,
        args.repetitions,
        args.random_seed,
    )
    failures = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                execute_run,
                codex_binary=args.codex,
                output_root=output_root,
                seed=seeds[scenario_id],
                scenario=scenarios[scenario_id],
                variant=variant,
                codex_home=homes[variant],
                repetition=repetition,
                model=args.model,
                reasoning=args.reasoning,
                timeout_seconds=args.timeout_seconds,
            ): (scenario_id, variant, repetition)
            for scenario_id, variant, repetition in tasks
        }
        for future in as_completed(futures):
            scenario_id, variant, repetition = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                failures += 1
                print(
                    f"ERROR {scenario_id}/{variant}/r{repetition}: {exc}",
                    flush=True,
                )
                continue
            print(
                f"DONE {scenario_id}/{variant}/r{repetition} "
                f"rc={result['returncode']} elapsed={result['elapsed_seconds']}s",
                flush=True,
            )
            if result["returncode"] != 0:
                failures += 1
    summary = {
        "format": "rootloom-core-reset-raw-matrix-v2",
        "created_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "reasoning": args.reasoning,
        "repetitions": args.repetitions,
        "random_seed": args.random_seed,
        "candidate": {
            "root": "plugins/rootloom",
            "tree_sha256": tree_sha256(REPO_ROOT / "plugins" / "rootloom"),
        },
        "tasks": [
            {
                "scenario": scenario_id,
                "variant": variant,
                "repetition": repetition,
            }
            for scenario_id, variant, repetition in tasks
        ],
        "failures": failures,
    }
    (output_root / "matrix.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
