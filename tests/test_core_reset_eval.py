from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PATH = ROOT / "evals" / "core-reset" / "evaluate.py"
SCORER_PATH = ROOT / "evals" / "core-reset" / "score_matrix.py"
SCENARIOS_PATH = ROOT / "evals" / "core-reset" / "scenarios.json"
CHANGE_SKILL_PATH = (
    ROOT
    / "plugins"
    / "rootloom"
    / "skills"
    / "operating-coding-change"
    / "SKILL.md"
)


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoreResetEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = load_module("rootloom_core_reset_eval", EVALUATOR_PATH)
        cls.scorer = load_module("rootloom_core_reset_scorer", SCORER_PATH)
        cls.scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]

    def valid_payload(self) -> dict[str, object]:
        runs: list[dict[str, object]] = []
        repetitions = 3
        for variant in ("no-rootloom", "rootloom-3.4", "rootloom-4.1"):
            for scenario in self.scenarios:
                for repetition in range(1, repetitions + 1):
                    if variant == "rootloom-3.4":
                        context_bytes, activated, elapsed, manual = 1000, 1, 100.0, 1
                        input_tokens, cached_tokens, commands = 1000, 800, 10
                    elif variant == "rootloom-4.1":
                        context_bytes, activated, elapsed, manual = 600, 1, 80.0, 0
                        input_tokens, cached_tokens, commands = 600, 500, 8
                    else:
                        context_bytes, activated, elapsed, manual = 500, 0, 70.0, 0
                        input_tokens, cached_tokens, commands = 500, 350, 6
                    expected_references = scenario["expected_route"]["references"]
                    run: dict[str, object] = {
                        "variant": variant,
                        "scenario": scenario["id"],
                        "repetition": repetition,
                        "mode_group": scenario["mode_group"],
                        "input_context_bytes": context_bytes,
                        "activated_skill_count": activated,
                        "activated_reference_count": (
                            len(expected_references)
                            if variant == "rootloom-4.1"
                            else 0
                        ),
                        "input_tokens": input_tokens,
                        "cached_input_tokens": cached_tokens,
                        "uncached_input_tokens": input_tokens - cached_tokens,
                        "output_tokens": 100,
                        "reasoning_output_tokens": 25,
                        "command_count": commands,
                        "agent_message_count": 3,
                        "elapsed_seconds": elapsed,
                        "manual_skill_selection_count": manual,
                        "run_reference": (
                            f"{variant}/{scenario['id']}/{repetition}"
                        ),
                    }
                    if variant == "rootloom-4.1":
                        run.update(
                            {
                                "route_exact": 1,
                                "over_routing_count": 0,
                                "under_routing_count": 0,
                            }
                        )
                    for metric in scenario["graded_metrics"]:
                        if metric in self.evaluator.BINARY_FIELDS:
                            run[metric] = 0
                        elif metric in self.evaluator.SUCCESS_FIELDS:
                            run[metric] = 1
                        else:
                            run[metric] = 0.9
                    runs.append(run)
        return {
            "format": "rootloom-core-reset-results-v2",
            "suite": "rootloom-core-reset-eval-v2",
            "model": "fixture",
            "reasoning": "fixture",
            "scoring": "rootloom-core-reset-mechanical-v3",
            "repetitions": repetitions,
            "random_seed": 20260729,
            "candidate": {
                "root": "plugins/rootloom",
                "tree_sha256": self.evaluator.tree_sha256(ROOT / "plugins" / "rootloom"),
            },
            "runs": runs,
        }

    def evaluate(
        self,
        payload: dict[str, object],
        *,
        minimum_repetitions: int = 1,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return self.evaluator.behavioral_gate(
                path,
                minimum_repetitions=minimum_repetitions,
            )

    def test_structural_gate_has_four_skills_and_reduces_context(self) -> None:
        result = self.evaluator.structural_gate()
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["public_skill_count"], 4)
        self.assertGreaterEqual(result["ordinary_change_context_reduction"], 0.30)

    def test_direct_route_is_a_bounded_fast_path(self) -> None:
        skill = CHANGE_SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("A dirty worktree is a preservation constraint", skill)
        self.assertIn("`direct`", skill)
        self.assertIn("Load no Reference.", skill)
        self.assertIn("skip broader inventory", skill)
        self.assertIn(
            "local callable/signature shape, file count, or dirty worktree alone",
            skill,
        )

    def test_complete_behavioral_matrix_passes_release_comparisons(self) -> None:
        result = self.evaluate(
            self.valid_payload(),
            minimum_repetitions=3,
        )
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["run_count"], 126)

    def test_release_gate_requires_three_repetitions(self) -> None:
        payload = self.valid_payload()
        payload["repetitions"] = 1
        runs = payload["runs"]
        self.assertIsInstance(runs, list)
        payload["runs"] = [run for run in runs if run["repetition"] == 1]

        result = self.evaluate(payload, minimum_repetitions=3)

        self.assertFalse(result["passed"])
        self.assertIn(
            "behavioral results have 1 repetitions; required >= 3",
            result["errors"],
        )

    def test_release_gate_rejects_stale_scoring_contract(self) -> None:
        payload = self.valid_payload()
        payload["scoring"] = "rootloom-core-reset-mechanical-v2"

        with self.assertRaisesRegex(ValueError, "scoring contract"):
            self.evaluate(payload)

    def test_invalid_metric_and_missing_cell_fail_closed(self) -> None:
        payload = self.valid_payload()
        runs = payload["runs"]
        self.assertIsInstance(runs, list)
        runs[0]["run_reference"] = ""
        result = self.evaluate(payload)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any("run_reference must be a non-empty" in error for error in result["errors"])
        )
        self.assertTrue(any("missing 1" in error for error in result["errors"]))

    def test_rootloom_four_must_activate_exactly_one_public_skill(self) -> None:
        payload = self.valid_payload()
        runs = payload["runs"]
        self.assertIsInstance(runs, list)
        next(run for run in runs if run["variant"] == "rootloom-4.1")[
            "activated_skill_count"
        ] = 0
        result = self.evaluate(payload)
        self.assertFalse(result["passed"])
        self.assertIn(
            "Rootloom 4.1 must activate exactly one public Skill per task",
            result["errors"],
        )

    def test_rootloom_four_route_must_match_expected_references(self) -> None:
        payload = self.valid_payload()
        runs = payload["runs"]
        self.assertIsInstance(runs, list)
        candidate = next(
            run
            for run in runs
            if run["variant"] == "rootloom-4.1"
            and run["scenario"] == "dirty-worktree"
        )
        candidate["route_exact"] = 0
        candidate["over_routing_count"] = 1

        result = self.evaluate(payload)

        self.assertFalse(result["passed"])
        self.assertIn(
            "Rootloom 4.1 mode/reference routing must match every scenario",
            result["errors"],
        )

    def test_zero_command_baseline_fails_without_a_division_error(self) -> None:
        payload = self.valid_payload()
        runs = payload["runs"]
        self.assertIsInstance(runs, list)
        for run in runs:
            if (
                run["variant"] == "rootloom-3.4"
                and run["mode_group"] == "direct"
            ):
                run["command_count"] = 0

        result = self.evaluate(payload)

        self.assertFalse(result["passed"])
        self.assertIn(
            "Direct mode command count regressed from a zero 3.4 baseline",
            result["errors"],
        )

    def test_behavioral_result_must_match_current_core_tree(self) -> None:
        payload = self.valid_payload()
        candidate = payload["candidate"]
        self.assertIsInstance(candidate, dict)
        candidate["tree_sha256"] = "0" * 64
        result = self.evaluate(payload)
        self.assertFalse(result["passed"])
        self.assertIn(
            "behavioral results do not match the current Rootloom Core tree",
            result["errors"],
        )

    def test_evidence_score_uses_validated_summary_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                ".rootloom-engineering-bundle.json",
                "diff.patch",
                "test.log",
            ):
                (root / name).write_text("fixture\n", encoding="utf-8")
            summary = {
                "mode": "strict",
                "evidence_complete": True,
                "passed": True,
                "quality_status": "REVIEW_EVIDENCE_COMPLETE",
                "baseline": {
                    "provided": True,
                    "required": True,
                    "repository_base_stable": True,
                },
                "change_contract": {
                    "provided": True,
                    "required": True,
                    "hash_chain_valid": True,
                    "scope_valid": True,
                },
                "hash_chain": {"valid": True},
                "claim_binding": "complete",
                "declared_claim_binding": "complete",
                "verification_coverage": "complete",
                "tests": [{"passed": True}],
            }
            (root / "summary.json").write_text(
                json.dumps(summary),
                encoding="utf-8",
            )
            self.assertEqual(self.scorer.evidence_score(root), 1.0)

    def test_token_usage_uses_completed_event_and_uncached_delta(self) -> None:
        usage = self.scorer.token_usage(
            [
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 120,
                        "cached_input_tokens": 100,
                        "output_tokens": 8,
                        "reasoning_output_tokens": 3,
                    },
                }
            ]
        )

        self.assertEqual(
            usage,
            {
                "input_tokens": 120,
                "cached_input_tokens": 100,
                "output_tokens": 8,
                "reasoning_output_tokens": 3,
                "uncached_input_tokens": 20,
            },
        )

    def test_route_score_requires_the_owning_reference_path(self) -> None:
        scenario = next(
            item for item in self.scenarios if item["id"] == "dirty-worktree"
        )
        exact, over, under = self.scorer.route_score(
            scenario,
            ["operating-coding-change"],
            ["verification-contract.md"],
        )
        self.assertEqual((exact, over, under), (0, 1, 1))

        exact, over, under = self.scorer.route_score(
            scenario,
            ["operating-coding-change"],
            [
                "operating-coding-change/references/"
                "verification-contract.md"
            ],
        )
        self.assertEqual((exact, over, under), (1, 0, 0))

    def test_activated_context_records_skill_relative_reference_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "plugins" / "cache" / "rootloom" / "rootloom"
            skill = (
                root
                / "4.1.0"
                / "skills"
                / "operating-coding-change"
                / "SKILL.md"
            )
            reference = skill.parent / "references" / "verification-contract.md"
            reference.parent.mkdir(parents=True)
            skill.write_text("skill", encoding="utf-8")
            reference.write_text("reference", encoding="utf-8")

            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": f"cat {skill} {reference}",
                        },
                    }
                ]
            )

        self.assertEqual(context_bytes, len("skillreference"))
        self.assertEqual(skills, ["operating-coding-change"])
        self.assertEqual(
            references,
            [
                "operating-coding-change/references/"
                "verification-contract.md"
            ],
        )

    def test_activated_context_resolves_codex_home_variable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory)
            skill = (
                codex_home
                / "plugins"
                / "cache"
                / "rootloom"
                / "rootloom"
                / "4.1.0"
                / "skills"
                / "setup-rootloom"
                / "SKILL.md"
            )
            skill.parent.mkdir(parents=True)
            skill.write_text("setup skill", encoding="utf-8")

            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": (
                                'cat "$CODEX_HOME/plugins/cache/rootloom/rootloom/'
                                '4.1.0/skills/setup-rootloom/SKILL.md"'
                            ),
                        },
                    }
                ],
                codex_home=codex_home,
            )

        self.assertEqual(context_bytes, len("setup skill"))
        self.assertEqual(skills, ["setup-rootloom"])
        self.assertEqual(references, [])

    def test_activated_context_resolves_codex_home_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory)
            skill = (
                codex_home
                / "plugins"
                / "cache"
                / "rootloom"
                / "rootloom"
                / "4.1.0"
                / "skills"
                / "setup-rootloom"
                / "SKILL.md"
            )
            skill.parent.mkdir(parents=True)
            skill.write_text("setup skill", encoding="utf-8")

            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": (
                                "sed -n '1,240p' plugins/cache/rootloom/rootloom/"
                                "4.1.0/skills/setup-rootloom/SKILL.md"
                            ),
                        },
                    }
                ],
                codex_home=codex_home,
            )

        self.assertEqual(context_bytes, len("setup skill"))
        self.assertEqual(skills, ["setup-rootloom"])
        self.assertEqual(references, [])

    def test_managed_guidance_marker_accepts_bounded_attributes(self) -> None:
        self.assertTrue(
            self.scorer.has_managed_guidance(
                "<!-- rootloom:managed-start version=1 "
                "fingerprint=abc scope=service -->\n"
            )
        )
        self.assertFalse(
            self.scorer.has_managed_guidance(
                "<!-- rootloom:managed-start version=10 -->\n"
            )
        )
        self.assertFalse(
            self.scorer.has_managed_guidance(
                "<!-- rootloom:managed-start version=1\nscope=service -->\n"
            )
        )

    def test_semantic_quality_scores_accept_equivalent_wording(self) -> None:
        ordinary = (
            "Cancellation leaves the relay disconnected. The reconnect callback "
            "no longer overwrites that transition with connected."
        )
        self.assertEqual(
            self.scorer.root_cause_score("ordinary-defect", ordinary, 1, 0),
            1.0,
        )
        review = (
            "The exception is suppressed and reports connected after failure. "
            "Retry sleeps, while the test codifies the false-success behavior."
        )
        self.assertEqual(
            self.scorer.root_cause_score("review-only", review, 1, 0),
            1.0,
        )
        migration = (
            "Readers accept both v1 and v2 during rollout. Migration is retry-safe "
            "and unchanged on rerun; rollback restores the prior file."
        )
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                self.scorer.governed_score(
                    "data-migration",
                    migration,
                    1,
                    Path(directory),
                ),
                1.0,
            )


if __name__ == "__main__":
    unittest.main()
