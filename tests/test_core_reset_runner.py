from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "evals" / "core-reset" / "run_matrix.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("rootloom_core_reset_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Core Reset runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoreResetRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def test_matrix_tasks_are_seeded_and_cover_every_cell(self) -> None:
        first = self.runner.matrix_tasks(
            ["one", "two"],
            ["no-rootloom", "rootloom-4.1"],
            2,
            42,
        )
        second = self.runner.matrix_tasks(
            ["one", "two"],
            ["no-rootloom", "rootloom-4.1"],
            2,
            42,
        )

        self.assertEqual(first, second)
        self.assertEqual(
            set(first),
            {
                (scenario, variant, repetition)
                for scenario in ("one", "two")
                for variant in ("no-rootloom", "rootloom-4.1")
                for repetition in (1, 2)
            },
        )

    def test_parse_mapping_requires_only_selected_variants(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-runner-", dir=Path.home()) as temporary:
            home = Path(temporary) / "no-rootloom"
            home.mkdir()

            mapping = self.runner.parse_mapping(
                [f"no-rootloom={home}"],
                ["no-rootloom"],
            )

            self.assertEqual(mapping, {"no-rootloom": home.resolve()})

    def test_execute_run_isolates_runtime_and_setup_homes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-runner-", dir=Path.home()) as temporary:
            root = Path(temporary)
            output = root / "output"
            output.mkdir()
            codex_home = root / "codex-home"
            codex_home.mkdir()
            fake_codex = root / "fake-codex.py"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import sys\n"
                "from pathlib import Path\n"
                "if '--version' in sys.argv:\n"
                "    print('fake-codex 1.0')\n"
                "    raise SystemExit(0)\n"
                "output = Path(sys.argv[sys.argv.index('--output-last-message') + 1])\n"
                "output.write_text('completed', encoding='utf-8')\n"
                "print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 5, 'cached_input_tokens': 2, 'output_tokens': 1, 'reasoning_output_tokens': 0}}))\n",
                encoding="utf-8",
            )
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)
            seed = self.runner.prepare_seed(output, "single-file-mechanical")
            scenario = self.runner.load_scenarios()["single-file-mechanical"]

            meta = self.runner.execute_run(
                codex_binary=str(fake_codex),
                output_root=output,
                seed=seed,
                scenario=scenario,
                variant="no-rootloom",
                codex_home=codex_home,
                repetition=1,
                model="fixture",
                reasoning="fixture",
                timeout_seconds=30,
            )

            self.assertEqual(meta["format"], "rootloom-core-reset-raw-run-v2")
            self.assertEqual(meta["repetition"], 1)
            self.assertEqual(meta["returncode"], 0)
            self.assertEqual(meta["setup_seed_manifest"], {})
            self.assertEqual(meta["setup_final_manifest"], {})
            runtime_home = Path(meta["runtime_codex_home"])
            setup_home = Path(meta["setup_home"])
            self.assertTrue(runtime_home.is_dir())
            self.assertTrue(setup_home.is_dir())
            self.assertNotEqual(runtime_home, codex_home)
            events = (output / "runs" / "single-file-mechanical" / "no-rootloom" / "repetition-001" / "events.jsonl").read_text(encoding="utf-8")
            self.assertEqual(json.loads(events)["type"], "turn.completed")


if __name__ == "__main__":
    unittest.main()
