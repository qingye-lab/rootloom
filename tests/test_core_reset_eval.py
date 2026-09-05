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
EVIDENCE_MODE_PATH = (
    ROOT
    / "plugins"
    / "rootloom"
    / "skills"
    / "operating-coding-change"
    / "references"
    / "evidence-mode.md"
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
            "scoring": "rootloom-core-reset-mechanical-v5",
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

    def test_structural_gate_reports_context_without_a_reduction_target(self) -> None:
        result = self.evaluator.structural_gate()
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["public_skill_count"], 4)
        self.assertIsInstance(result["ordinary_change_context_reduction"], float)

    def test_guidance_integrity_accepts_short_rules_and_rejects_corruption(self) -> None:
        validator = load_module("guidance_validator", ROOT / "scripts" / "validate_repo.py")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "AGENTS.md"
            path.write_text("# Rules\n\n- Preserve stored data.\n", encoding="utf-8")
            errors = []
            validator.validate_guidance_structure(path, errors)
            self.assertEqual(errors, [])
            for content in (
                "# Rules\n<!-- rootloom:managed-end -->\n",
                "# Rules\n<!-- rootloom:managed-start version=1 -->\n",
                "# Rules\n" + "x" * 4096,
            ):
                with self.subTest(content=content[:60]):
                    path.write_text(content, encoding="utf-8")
                    errors = []
                    validator.validate_guidance_structure(path, errors, maximum_bytes=4096)
                    self.assertTrue(errors)
            alias = Path(directory) / "alias.md"
            alias.symlink_to(path)
            errors = []
            validator.validate_guidance_structure(alias, errors)
            self.assertTrue(errors)

    def test_regenerable_versioned_artifact_is_scoped_and_current_only(self) -> None:
        scenario = next(
            item
            for item in self.scenarios
            if item["id"] == "regenerable-versioned-artifact"
        )
        self.assertEqual(scenario["mode_group"], "scoped")
        self.assertEqual(scenario["expected_route"]["references"], [])

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            package = repo / "loom_eval"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            implementation = package / "plan_record.py"
            implementation.write_text(
                "import json\n"
                "SCHEMA_VERSION = 2\n"
                "def save_plan(path, entries):\n"
                "    path.write_text(json.dumps({'schema_version': 2, 'entries': list(entries)}, sort_keys=True))\n"
                "def load_plan(path):\n"
                "    payload = json.loads(path.read_text())\n"
                "    if payload.get('schema_version') != 2:\n"
                "        raise ValueError('unsupported plan schema')\n"
                "    return list(payload['entries'])\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.scorer.task_success(
                    "regenerable-versioned-artifact",
                    repo,
                    "",
                    0,
                    {},
                    [],
                ),
                1,
            )
            implementation.write_text(
                implementation.read_text(encoding="utf-8")
                + "\n# legacy adapter retained for compatibility\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.scorer.task_success(
                    "regenerable-versioned-artifact",
                    repo,
                    "",
                    0,
                    {},
                    [],
                ),
                0,
            )
            implementation.write_text(
                implementation.read_text(encoding="utf-8")
                .replace("# legacy adapter retained for compatibility", "# feature flag")
                .replace("adapter", "current"),
                encoding="utf-8",
            )
            self.assertEqual(
                self.scorer.task_success(
                    "regenerable-versioned-artifact",
                    repo,
                    "",
                    0,
                    {},
                    [],
                ),
                0,
            )

    def test_generated_python_cache_is_not_a_scope_escape(self) -> None:
        self.assertTrue(
            self.scorer.is_generated_python_cache(
                "loom_eval/__pycache__/store.cpython-313.pyc"
            )
        )
        self.assertFalse(self.scorer.is_generated_python_cache("loom_eval/store.py"))
        self.assertFalse(self.scorer.is_generated_python_cache("outside/file.pyc"))

    def test_evidence_orchestrator_is_single_command_convenience_only(self) -> None:
        reference = EVIDENCE_MODE_PATH.read_text(encoding="utf-8")

        self.assertIn("single-command Evidence convenience path", reference)
        self.assertIn("heterogeneous governed evidence", reference)
        self.assertIn("multiple specialized commands or targets", reference)
        self.assertIn("build-plus-runtime", reference)

    def test_complete_behavioral_matrix_passes_release_comparisons(self) -> None:
        result = self.evaluate(
            self.valid_payload(),
            minimum_repetitions=3,
        )
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["run_count"], 135)

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

    def test_elapsed_comparisons_use_only_successful_variant_pairs(self) -> None:
        payload = self.valid_payload()
        runs = payload["runs"]
        self.assertIsInstance(runs, list)
        for run in runs:
            if (
                run["variant"] == "rootloom-3.4"
                and run["mode_group"] in {"guidance", "setup"}
                and run["repetition"] == 1
            ):
                run["task_success"] = 0
                run["elapsed_seconds"] = 1.0

        result = self.evaluate(payload, minimum_repetitions=3)

        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(
            result["comparisons"]["guidance_setup_elapsed_geomean_ratio"],
            0.8,
        )

    def test_elapsed_comparison_requires_a_successful_variant_pair(self) -> None:
        payload = self.valid_payload()
        runs = payload["runs"]
        self.assertIsInstance(runs, list)
        for run in runs:
            if run["mode_group"] == "evidence":
                run["task_success"] = 0

        result = self.evaluate(payload, minimum_repetitions=3)

        self.assertFalse(result["passed"])
        self.assertIn(
            "Evidence elapsed comparison has no task-successful variant pairs",
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

    def test_scoped_route_is_self_contained(self) -> None:
        scenario = next(
            item for item in self.scenarios if item["id"] == "dirty-worktree"
        )
        exact, over, under = self.scorer.route_score(
            scenario,
            ["operating-coding-change"],
            ["verification-contract.md"],
        )
        self.assertEqual((exact, over, under), (0, 1, 0))

        exact, over, under = self.scorer.route_score(
            scenario,
            ["operating-coding-change"],
            [],
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
                            "exit_code": 0,
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

    def test_activated_context_resolves_later_relative_reference_commands(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "plugins" / "cache" / "rootloom" / "rootloom"
            skill = (
                root
                / "4.1.0"
                / "skills"
                / "operating-coding-change"
                / "SKILL.md"
            )
            governed = skill.parent / "references" / "governed-change.md"
            verification = skill.parent / "references" / "verification-contract.md"
            governed.parent.mkdir(parents=True)
            skill.write_text("skill", encoding="utf-8")
            governed.write_text("governed", encoding="utf-8")
            verification.write_text("verification", encoding="utf-8")

            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": f"cat {skill}",
                            "exit_code": 0,
                        },
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "cat references/governed-change.md",
                            "exit_code": 0,
                        },
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "cat references/verification-contract.md",
                            "exit_code": 0,
                        },
                    },
                ]
            )

        self.assertEqual(
            context_bytes,
            len("skillgovernedverification"),
        )
        self.assertEqual(skills, ["operating-coding-change"])
        self.assertEqual(
            references,
            [
                "operating-coding-change/references/governed-change.md",
                "operating-coding-change/references/verification-contract.md",
            ],
        )

    def test_activated_context_resolves_quoted_paths_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom eval ") as directory:
            skill = (
                Path(directory)
                / "plugins"
                / "cache"
                / "rootloom"
                / "rootloom"
                / "4.1.0"
                / "skills"
                / "operating-coding-change"
                / "SKILL.md"
            )
            governed = skill.parent / "references" / "governed-change.md"
            governed.parent.mkdir(parents=True)
            skill.write_text("skill", encoding="utf-8")
            governed.write_text("governed", encoding="utf-8")

            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": f"sed -n '1,240p' '{skill}'",
                            "exit_code": 0,
                        },
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": f'sed -n "1,240p" "{governed}"',
                            "exit_code": 0,
                        },
                    },
                ]
            )

        self.assertEqual(context_bytes, len("skillgoverned"))
        self.assertEqual(skills, ["operating-coding-change"])
        self.assertEqual(
            references,
            ["operating-coding-change/references/governed-change.md"],
        )

    def test_activated_context_ignores_failed_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = (
                Path(directory)
                / "plugins"
                / "cache"
                / "rootloom"
                / "rootloom"
                / "4.1.0"
                / "skills"
                / "operating-coding-change"
                / "SKILL.md"
            )
            skill.parent.mkdir(parents=True)
            skill.write_text("skill", encoding="utf-8")

            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": f"cat '{skill}'",
                            "exit_code": 1,
                        },
                    }
                ]
            )

        self.assertEqual(context_bytes, 0)
        self.assertEqual(skills, [])
        self.assertEqual(references, [])

    def test_activated_context_resolves_loop_joined_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "plugins" / "cache" / "rootloom" / "rootloom"
            skill = (
                root
                / "4.1.0"
                / "skills"
                / "operating-coding-change"
                / "SKILL.md"
            )
            reference_names = (
                "evidence-mode.md",
                "evidence-contract.md",
                "verification-contract.md",
            )
            skill.parent.mkdir(parents=True)
            skill.write_text("skill", encoding="utf-8")
            for name in reference_names:
                path = skill.parent / "references" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name, encoding="utf-8")

            relative = " ".join(
                f"references/{name}" for name in reference_names
            )
            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": (
                                f"for rootloom_ref in {relative}; do "
                                f'sed -n "1,240p" "{skill.parent}/"'
                                "'$rootloom_ref; done"
                            ),
                            "exit_code": 0,
                        },
                    }
                ]
            )

        self.assertEqual(
            context_bytes,
            len("".join(reference_names)),
        )
        self.assertEqual(skills, [])
        self.assertEqual(
            references,
            sorted(
                f"operating-coding-change/references/{name}"
                for name in reference_names
            ),
        )

    def test_activated_context_resolves_reference_directory_loop_basenames(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = (
                Path(directory)
                / "plugins"
                / "cache"
                / "rootloom"
                / "rootloom"
                / "4.2.0"
                / "skills"
                / "operating-coding-change"
                / "SKILL.md"
            )
            names = (
                "evidence-mode.md",
                "evidence-contract.md",
                "verification-contract.md",
            )
            skill.parent.mkdir(parents=True)
            skill.write_text("skill", encoding="utf-8")
            for name in names:
                reference = skill.parent / "references" / name
                reference.parent.mkdir(parents=True, exist_ok=True)
                reference.write_text(name, encoding="utf-8")

            context_bytes, skills, references = self.scorer.activated_context(
                [
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": f"cat '{skill}'",
                            "exit_code": 0,
                        },
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": (
                                f"for f in {' '.join(names)}; do "
                                f"sed -n '1,240p' '{skill.parent}/references/'"
                                '"$f"; done'
                            ),
                            "exit_code": 0,
                        },
                    },
                ]
            )

        self.assertEqual(context_bytes, len("skill" + "".join(names)))
        self.assertEqual(skills, ["operating-coding-change"])
        self.assertEqual(
            references,
            sorted(
                f"operating-coding-change/references/{name}" for name in names
            ),
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
                            "exit_code": 0,
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
                            "exit_code": 0,
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
        equivalent_review = (
            "The open exception is suppressed, leaving connected after failure and "
            "without a retry after the delay. The test ratifies the defect and "
            "encodes the false-connected state."
        )
        self.assertEqual(
            self.scorer.root_cause_score(
                "review-only",
                equivalent_review,
                1,
                0,
            ),
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
            equivalent_migration = (
                "Readers accept both v1 and v2 during coexistence. Migration is "
                "repeat-safe and byte-preserves v2. Rollback restores v1."
            )
            self.assertEqual(
                self.scorer.governed_score(
                    "data-migration",
                    equivalent_migration,
                    1,
                    Path(directory),
                ),
                1.0,
            )
            unchanged_migration = (
                "Writers emit v2. Readers accept v1 name and v2 display_name. "
                "Migration leaves v2 byte-for-byte unchanged. Rollback restores v1."
            )
            self.assertEqual(
                self.scorer.governed_score(
                    "data-migration",
                    unchanged_migration,
                    1,
                    Path(directory),
                ),
                1.0,
            )
            no_op_migration = (
                "Readers accept both v1 and v2. Repeated migration and existing v2 "
                "files are exact no-ops. Rollback restores v1."
            )
            self.assertEqual(
                self.scorer.governed_score(
                    "data-migration",
                    no_op_migration,
                    1,
                    Path(directory),
                ),
                1.0,
            )
            byte_no_op_migration = (
                "Writers emit v2 and readers accept v1 and v2. Existing v2 files "
                "are a byte-for-byte no-op. Rollback restores v1."
            )
            self.assertEqual(
                self.scorer.governed_score(
                    "data-migration",
                    byte_no_op_migration,
                    1,
                    Path(directory),
                ),
                1.0,
            )
            no_rewrite_migration = (
                "Writers emit v2 and readers accept v1 and v2. Migration does not "
                "rewrite v2 files. Rollback restores v1."
            )
            self.assertEqual(
                self.scorer.governed_score(
                    "data-migration",
                    no_rewrite_migration,
                    1,
                    Path(directory),
                ),
                1.0,
            )


if __name__ == "__main__":
    unittest.main()
