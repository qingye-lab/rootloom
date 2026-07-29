#!/usr/bin/env python3
"""Evaluate structural and supplied behavioral Rootloom Core Reset evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "plugins" / "rootloom" / "skills"
EXPECTED_SKILLS = {
    "operating-coding-change",
    "operating-code-review",
    "project-guidance",
    "setup-rootloom",
}
V1_VARIANTS = {"no-rootloom", "rootloom-3.4", "rootloom-4.0"}
V2_VARIANTS = {"no-rootloom", "rootloom-3.4", "rootloom-4.1"}
V2_SCORING = "rootloom-core-reset-mechanical-v3"
TIER_0_1_SCENARIOS = {
    "single-file-mechanical",
    "ordinary-defect",
    "multi-file-feature",
}
BINARY_FIELDS = {"scope_escape", "false_test_pass_claim"}
SUCCESS_FIELDS = {"task_success"}
QUALITY_FIELDS = {
    "root_cause_alignment",
    "governed_required_coverage",
    "evidence_completeness",
}


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


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def structural_gate() -> dict[str, Any]:
    baseline = load_json(EVAL_ROOT / "baseline-v3.4.json")
    actual_skills = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
    current_path = SKILLS / "operating-coding-change" / "SKILL.md"
    current_bytes = len(current_path.read_bytes())
    baseline_bytes = baseline["ordinary_change_skill_bytes"]
    reduction = 1 - current_bytes / baseline_bytes
    errors: list[str] = []
    if actual_skills != EXPECTED_SKILLS:
        errors.append(
            "Core Skill catalog differs: "
            f"expected {sorted(EXPECTED_SKILLS)}, found {sorted(actual_skills)}"
        )
    if reduction < 0.30:
        errors.append(
            f"ordinary Change context reduction is {reduction:.1%}; expected >= 30%"
        )
    return {
        "passed": not errors,
        "errors": errors,
        "public_skill_count": len(actual_skills),
        "baseline_public_skill_count": baseline["public_skill_count"],
        "ordinary_change_skill_bytes": current_bytes,
        "baseline_ordinary_change_skill_bytes": baseline_bytes,
        "ordinary_change_context_reduction": round(reduction, 4),
    }


def behavioral_gate_v1(path: Path) -> dict[str, Any]:
    suite = load_json(EVAL_ROOT / "scenarios-v1.json")
    payload = load_json(path)
    if payload.get("format") != "rootloom-core-reset-results-v1":
        raise ValueError("unsupported behavioral results format")
    expected_scenarios = {item["id"]: item for item in suite["scenarios"]}
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("behavioral results must identify the evaluated candidate")
    if candidate.get("root") != "plugins/rootloom":
        raise ValueError("behavioral results candidate root must be plugins/rootloom")
    recorded_digest = candidate.get("tree_sha256")
    if not isinstance(recorded_digest, str) or len(recorded_digest) != 64:
        raise ValueError("behavioral results candidate tree_sha256 is invalid")
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise ValueError("behavioral results runs must be an array")
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[str] = []
    current_digest = tree_sha256(ROOT / candidate["root"])
    if recorded_digest != current_digest:
        errors.append("behavioral results do not match the current Rootloom Core tree")
    required_common = {
        "input_context_bytes",
        "activated_skill_count",
        "elapsed_seconds",
        "manual_skill_selection_count",
        "run_reference",
    }
    for run in runs:
        if not isinstance(run, dict):
            errors.append("every run must be an object")
            continue
        key = (run.get("variant"), run.get("scenario"))
        if key in indexed:
            errors.append(f"duplicate run: {key}")
            continue
        if key[0] not in V1_VARIANTS or key[1] not in expected_scenarios:
            errors.append(f"unknown variant/scenario: {key}")
            continue
        graded = set(expected_scenarios[key[1]].get("graded_metrics", []))
        required = required_common | graded
        missing = required - set(run)
        if missing:
            errors.append(f"run {key} is missing {sorted(missing)}")
            continue
        run_errors: list[str] = []
        for field in (BINARY_FIELDS | SUCCESS_FIELDS) & graded:
            if run[field] not in (0, 1, False, True):
                run_errors.append(f"{field} must be 0 or 1")
        for field in QUALITY_FIELDS & graded:
            value = run[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                run_errors.append(f"{field} must be a finite score from 0 to 1")
        for field in (
            "input_context_bytes",
            "activated_skill_count",
            "manual_skill_selection_count",
        ):
            value = run[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                run_errors.append(f"{field} must be a non-negative integer")
        elapsed = run["elapsed_seconds"]
        if (
            isinstance(elapsed, bool)
            or not isinstance(elapsed, (int, float))
            or not math.isfinite(elapsed)
            or elapsed <= 0
        ):
            run_errors.append("elapsed_seconds must be a finite positive number")
        reference = run["run_reference"]
        if not isinstance(reference, str) or not reference.strip():
            run_errors.append("run_reference must be a non-empty stable reference")
        if run_errors:
            errors.extend(f"run {key}: {message}" for message in run_errors)
            continue
        indexed[key] = run
    expected = {
        (variant, scenario)
        for variant in V1_VARIANTS
        for scenario in expected_scenarios
    }
    missing_cells = sorted(expected - set(indexed))
    if missing_cells:
        errors.append(f"missing {len(missing_cells)} variant/scenario cells")

    def values(
        variant: str,
        field: str,
        scenario_ids: set[str] | None = None,
    ) -> list[float]:
        if scenario_ids is not None:
            selected = scenario_ids
        elif field in BINARY_FIELDS | SUCCESS_FIELDS | QUALITY_FIELDS:
            selected = {
                scenario
                for scenario, definition in expected_scenarios.items()
                if field in definition.get("graded_metrics", [])
            }
        else:
            selected = set(expected_scenarios)
        return [float(indexed[(variant, scenario)][field]) for scenario in selected]

    if not errors:
        old = "rootloom-3.4"
        new = "rootloom-4.0"
        for field in ("scope_escape", "false_test_pass_claim"):
            if sum(values(new, field)) > sum(values(old, field)):
                errors.append(f"{field} regressed versus 3.4")
        for field in SUCCESS_FIELDS:
            if sum(values(new, field)) < sum(values(old, field)):
                errors.append(f"{field} regressed versus 3.4")
        for field in (
            "root_cause_alignment",
            "governed_required_coverage",
            "evidence_completeness",
        ):
            if mean(values(new, field)) < mean(values(old, field)):
                errors.append(f"{field} regressed versus 3.4")
        if mean(values(new, "elapsed_seconds")) >= mean(values(old, "elapsed_seconds")):
            errors.append("mean elapsed_seconds did not improve versus 3.4")
        old_manual = mean(values(old, "manual_skill_selection_count"))
        new_manual = mean(values(new, "manual_skill_selection_count"))
        if (old_manual > 0 and new_manual >= old_manual) or (
            old_manual == 0 and new_manual > 0
        ):
            errors.append("mean manual Skill selection count did not improve versus 3.4")
        if mean(values(new, "input_context_bytes", TIER_0_1_SCENARIOS)) > (
            0.70 * mean(values(old, "input_context_bytes", TIER_0_1_SCENARIOS))
        ):
            errors.append("Tier 0/1 input context did not improve by at least 30%")
        activated = values(new, "activated_skill_count")
        if any(value != 1 for value in activated):
            errors.append("Rootloom 4.0 must activate exactly one public Skill per task")
    return {"passed": not errors, "errors": errors, "run_count": len(indexed)}


V2_INTEGER_FIELDS = {
    "input_context_bytes",
    "activated_skill_count",
    "activated_reference_count",
    "input_tokens",
    "cached_input_tokens",
    "uncached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "command_count",
    "agent_message_count",
    "manual_skill_selection_count",
}
V2_ROUTE_FIELDS = {"route_exact", "over_routing_count", "under_routing_count"}


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(mean(math.log(value) for value in values))


def bootstrap_ratio_interval(
    ratios: list[float],
    *,
    samples: int = 4000,
) -> list[float]:
    if not ratios:
        return []
    generator = random.Random(20260729)
    estimates = sorted(
        mean(generator.choice(ratios) for _ in ratios)
        for _ in range(samples)
    )
    low = estimates[int(0.025 * (samples - 1))]
    high = estimates[int(0.975 * (samples - 1))]
    return [round(low, 4), round(high, 4)]


def mean_ratio(
    numerators: list[float],
    denominators: list[float],
) -> float | None:
    """Return a finite mean ratio only when the baseline can support one."""

    baseline = mean(denominators)
    if baseline <= 0:
        return None
    return mean(numerators) / baseline


def behavioral_gate_v2(
    path: Path,
    *,
    minimum_repetitions: int,
) -> dict[str, Any]:
    suite = load_json(EVAL_ROOT / "scenarios.json")
    if suite.get("format") != "rootloom-core-reset-eval-v2":
        raise ValueError("current scenario suite is not v2")
    payload = load_json(path)
    if payload.get("format") != "rootloom-core-reset-results-v2":
        raise ValueError("unsupported v2 behavioral results format")
    if payload.get("suite") != suite["format"]:
        raise ValueError("behavioral result suite does not match scenarios.json")
    if payload.get("scoring") != V2_SCORING:
        raise ValueError(
            f"behavioral results require scoring contract {V2_SCORING}"
        )
    repetitions = payload.get("repetitions")
    if (
        isinstance(repetitions, bool)
        or not isinstance(repetitions, int)
        or repetitions < 1
    ):
        raise ValueError("behavioral results repetitions must be a positive integer")
    expected_scenarios = {item["id"]: item for item in suite["scenarios"]}
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("behavioral results must identify the evaluated candidate")
    if candidate.get("root") != "plugins/rootloom":
        raise ValueError("behavioral results candidate root must be plugins/rootloom")
    recorded_digest = candidate.get("tree_sha256")
    if not isinstance(recorded_digest, str) or len(recorded_digest) != 64:
        raise ValueError("behavioral results candidate tree_sha256 is invalid")
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise ValueError("behavioral results runs must be an array")

    indexed: dict[tuple[str, str, int], dict[str, Any]] = {}
    errors: list[str] = []
    if repetitions < minimum_repetitions:
        errors.append(
            f"behavioral results have {repetitions} repetitions; "
            f"required >= {minimum_repetitions}"
        )
    current_digest = tree_sha256(ROOT / candidate["root"])
    if recorded_digest != current_digest:
        errors.append("behavioral results do not match the current Rootloom Core tree")
    required_common = V2_INTEGER_FIELDS | {
        "elapsed_seconds",
        "mode_group",
        "repetition",
        "run_reference",
    }
    for run in runs:
        if not isinstance(run, dict):
            errors.append("every run must be an object")
            continue
        repetition = run.get("repetition")
        key = (run.get("variant"), run.get("scenario"), repetition)
        if key in indexed:
            errors.append(f"duplicate run: {key}")
            continue
        if (
            key[0] not in V2_VARIANTS
            or key[1] not in expected_scenarios
            or isinstance(repetition, bool)
            or not isinstance(repetition, int)
            or not 1 <= repetition <= repetitions
        ):
            errors.append(f"unknown or invalid variant/scenario/repetition: {key}")
            continue
        scenario = expected_scenarios[key[1]]
        graded = set(scenario.get("graded_metrics", []))
        required = required_common | graded
        if key[0] == "rootloom-4.1":
            required |= V2_ROUTE_FIELDS
        missing = required - set(run)
        if missing:
            errors.append(f"run {key} is missing {sorted(missing)}")
            continue
        run_errors: list[str] = []
        if run["mode_group"] != scenario.get("mode_group"):
            run_errors.append("mode_group differs from scenario definition")
        for field in (BINARY_FIELDS | SUCCESS_FIELDS) & graded:
            if run[field] not in (0, 1, False, True):
                run_errors.append(f"{field} must be 0 or 1")
        for field in QUALITY_FIELDS & graded:
            value = run[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                run_errors.append(f"{field} must be a finite score from 0 to 1")
        for field in V2_INTEGER_FIELDS:
            value = run[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                run_errors.append(f"{field} must be a non-negative integer")
        if key[0] == "rootloom-4.1":
            for field in V2_ROUTE_FIELDS:
                value = run[field]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    run_errors.append(f"{field} must be a non-negative integer")
            if run["route_exact"] not in (0, 1):
                run_errors.append("route_exact must be 0 or 1")
        if run["cached_input_tokens"] > run["input_tokens"]:
            run_errors.append("cached_input_tokens exceeds input_tokens")
        if run["uncached_input_tokens"] != (
            run["input_tokens"] - run["cached_input_tokens"]
        ):
            run_errors.append("uncached_input_tokens does not match token totals")
        elapsed = run["elapsed_seconds"]
        if (
            isinstance(elapsed, bool)
            or not isinstance(elapsed, (int, float))
            or not math.isfinite(elapsed)
            or elapsed <= 0
        ):
            run_errors.append("elapsed_seconds must be a finite positive number")
        reference = run["run_reference"]
        if not isinstance(reference, str) or not reference.strip():
            run_errors.append("run_reference must be a non-empty stable reference")
        if run_errors:
            errors.extend(f"run {key}: {message}" for message in run_errors)
            continue
        indexed[key] = run

    expected = {
        (variant, scenario, repetition)
        for variant in V2_VARIANTS
        for scenario in expected_scenarios
        for repetition in range(1, repetitions + 1)
    }
    missing_cells = sorted(expected - set(indexed))
    if missing_cells:
        errors.append(f"missing {len(missing_cells)} variant/scenario/repetition cells")

    def scenario_ids_for_field(field: str) -> set[str]:
        if field in BINARY_FIELDS | SUCCESS_FIELDS | QUALITY_FIELDS:
            return {
                scenario
                for scenario, definition in expected_scenarios.items()
                if field in definition.get("graded_metrics", [])
            }
        return set(expected_scenarios)

    def values(
        variant: str,
        field: str,
        scenario_ids: set[str] | None = None,
    ) -> list[float]:
        selected = scenario_ids or scenario_ids_for_field(field)
        return [
            float(indexed[(variant, scenario, repetition)][field])
            for scenario in sorted(selected)
            for repetition in range(1, repetitions + 1)
        ]

    def paired_ratios(field: str, scenario_ids: set[str]) -> list[float]:
        return [
            float(indexed[("rootloom-4.1", scenario, repetition)][field])
            / float(indexed[("rootloom-3.4", scenario, repetition)][field])
            for scenario in sorted(scenario_ids)
            for repetition in range(1, repetitions + 1)
            if float(indexed[("rootloom-3.4", scenario, repetition)][field]) > 0
        ]

    comparisons: dict[str, Any] = {}
    if not errors:
        old = "rootloom-3.4"
        new = "rootloom-4.1"
        for field in ("scope_escape", "false_test_pass_claim"):
            if sum(values(new, field)) > sum(values(old, field)):
                errors.append(f"{field} regressed versus 3.4")
        for field in SUCCESS_FIELDS:
            if sum(values(new, field)) < sum(values(old, field)):
                errors.append(f"{field} regressed versus 3.4")
        for field in QUALITY_FIELDS:
            if mean(values(new, field)) < mean(values(old, field)):
                errors.append(f"{field} regressed versus 3.4")

        old_manual = mean(values(old, "manual_skill_selection_count"))
        new_manual = mean(values(new, "manual_skill_selection_count"))
        if (old_manual > 0 and new_manual >= old_manual) or (
            old_manual == 0 and new_manual > 0
        ):
            errors.append("mean manual Skill selection count did not improve versus 3.4")
        if mean(values(new, "input_context_bytes", TIER_0_1_SCENARIOS)) > (
            0.70 * mean(values(old, "input_context_bytes", TIER_0_1_SCENARIOS))
        ):
            errors.append("Tier 0/1 input context did not improve by at least 30%")

        candidate_runs = [
            run for key, run in indexed.items() if key[0] == "rootloom-4.1"
        ]
        if any(run["activated_skill_count"] != 1 for run in candidate_runs):
            errors.append("Rootloom 4.1 must activate exactly one public Skill per task")
        if any(
            run["route_exact"] != 1
            or run["over_routing_count"] != 0
            or run["under_routing_count"] != 0
            for run in candidate_runs
        ):
            errors.append("Rootloom 4.1 mode/reference routing must match every scenario")

        groups = {
            mode: {
                scenario_id
                for scenario_id, definition in expected_scenarios.items()
                if definition["mode_group"] == mode
            }
            for mode in {
                definition["mode_group"] for definition in expected_scenarios.values()
            }
        }
        routine = groups["direct"] | groups["scoped"] | groups["review"]
        routine_elapsed = paired_ratios("elapsed_seconds", routine)
        evidence_elapsed = paired_ratios("elapsed_seconds", groups["evidence"])
        governed_elapsed = paired_ratios("elapsed_seconds", groups["governed"])
        guidance_setup_elapsed = paired_ratios(
            "elapsed_seconds",
            groups["guidance"] | groups["setup"],
        )
        routine_uncached_input_ratio = mean_ratio(
            values(new, "uncached_input_tokens", routine),
            values(old, "uncached_input_tokens", routine),
        )
        evidence_input_token_ratio = mean_ratio(
            values(new, "input_tokens", groups["evidence"]),
            values(old, "input_tokens", groups["evidence"]),
        )
        old_direct_commands = mean(values(old, "command_count", groups["direct"]))
        new_direct_commands = mean(values(new, "command_count", groups["direct"]))
        direct_command_ratio = (
            new_direct_commands / old_direct_commands
            if old_direct_commands > 0
            else 1.0
            if new_direct_commands == 0
            else None
        )
        comparisons = {
            "routine_elapsed_geomean_ratio": round(
                geometric_mean(routine_elapsed), 4
            ),
            "routine_elapsed_mean_ratio_ci95": bootstrap_ratio_interval(
                routine_elapsed
            ),
            "evidence_elapsed_geomean_ratio": round(
                geometric_mean(evidence_elapsed), 4
            ),
            "governed_elapsed_geomean_ratio": round(
                geometric_mean(governed_elapsed), 4
            ),
            "guidance_setup_elapsed_geomean_ratio": round(
                geometric_mean(guidance_setup_elapsed), 4
            ),
            "routine_uncached_input_ratio": (
                round(routine_uncached_input_ratio, 4)
                if routine_uncached_input_ratio is not None
                else None
            ),
            "evidence_input_token_ratio": (
                round(evidence_input_token_ratio, 4)
                if evidence_input_token_ratio is not None
                else None
            ),
            "direct_command_ratio": (
                round(direct_command_ratio, 4)
                if direct_command_ratio is not None
                else None
            ),
        }
        if comparisons["routine_elapsed_geomean_ratio"] >= 1:
            errors.append("routine elapsed time did not improve versus 3.4")
        if comparisons["evidence_elapsed_geomean_ratio"] >= 1:
            errors.append("Evidence elapsed time did not improve versus 3.4")
        if comparisons["governed_elapsed_geomean_ratio"] > 1.10:
            errors.append("Governed elapsed time regressed by more than 10% versus 3.4")
        if comparisons["guidance_setup_elapsed_geomean_ratio"] > 1.10:
            errors.append(
                "Guidance/Setup elapsed time regressed by more than 10% versus 3.4"
            )
        if comparisons["routine_uncached_input_ratio"] is None:
            errors.append(
                "routine uncached input token improvement is unmeasurable from "
                "a zero 3.4 baseline"
            )
        elif comparisons["routine_uncached_input_ratio"] >= 1:
            errors.append("routine uncached input tokens did not improve versus 3.4")
        if comparisons["evidence_input_token_ratio"] is None:
            errors.append(
                "Evidence input token improvement is unmeasurable from a zero "
                "3.4 baseline"
            )
        elif comparisons["evidence_input_token_ratio"] >= 1:
            errors.append("Evidence input tokens did not improve versus 3.4")
        if comparisons["direct_command_ratio"] is None:
            errors.append("Direct mode command count regressed from a zero 3.4 baseline")
        elif comparisons["direct_command_ratio"] > 1:
            errors.append("Direct mode command count regressed versus 3.4")
    return {
        "passed": not errors,
        "errors": errors,
        "run_count": len(indexed),
        "repetitions": repetitions,
        "comparisons": comparisons,
    }


def behavioral_gate(
    path: Path,
    *,
    minimum_repetitions: int = 1,
) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("format") == "rootloom-core-reset-results-v1":
        return behavioral_gate_v1(path)
    if payload.get("format") == "rootloom-core-reset-results-v2":
        return behavioral_gate_v2(
            path,
            minimum_repetitions=minimum_repetitions,
        )
    raise ValueError("unsupported behavioral results format")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--require-behavioral", action="store_true")
    parser.add_argument("--minimum-repetitions", type=int)
    args = parser.parse_args()
    minimum_repetitions = (
        args.minimum_repetitions
        if args.minimum_repetitions is not None
        else 3
        if args.require_behavioral
        else 1
    )
    if minimum_repetitions < 1:
        raise SystemExit("--minimum-repetitions must be positive")

    report: dict[str, Any] = {"structural": structural_gate()}
    if args.results:
        report["behavioral"] = behavioral_gate(
            args.results,
            minimum_repetitions=minimum_repetitions,
        )
    elif args.require_behavioral:
        report["behavioral"] = {
            "passed": False,
            "errors": ["--require-behavioral needs --results"],
        }
    else:
        report["behavioral"] = {
            "passed": None,
            "status": "not-run; required before formal 4.1 release",
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["structural"]["passed"] and report["behavioral"]["passed"] is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
