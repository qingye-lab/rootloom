from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = (
    ROOT
    / "plugins"
    / "rootloom"
    / "resources"
    / "evidence"
    / "orchestrate_evidence.py"
)


class EvidenceOrchestratorTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        (repo / "app.py").write_text(
            "def current_value():\n    return 1\n",
            encoding="utf-8",
        )
        (repo / "test_app.py").write_text(
            "import unittest\n"
            "from app import current_value\n\n"
            "class AppTests(unittest.TestCase):\n"
            "    def test_current_value(self):\n"
            "        self.assertEqual(current_value(), 2)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Rootloom Test"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "rootloom@example.invalid"],
            cwd=repo,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "fixture"],
            cwd=repo,
            check=True,
        )
        return repo

    def prepare_command(
        self,
        *,
        repo: Path,
        review_dir: Path,
        target: str = "test_app",
    ) -> list[str]:
        return [
            sys.executable,
            str(ORCHESTRATOR),
            "prepare",
            "--repo",
            str(repo),
            "--task",
            "Fix the application value defect at its owning function.",
            "--review-dir",
            str(review_dir),
            "--path",
            "app.py",
            "--path",
            "test_app.py",
            "--verify",
            shlex.join(
                [sys.executable, "-B", "-m", "unittest", "test_app", "-v"]
            ),
            "--target",
            target,
            "--primary-evidence",
            "The focused test observes the corrected caller-visible value.",
            "--invariant-evidence",
            "The same test exercises the function that owns the value.",
            "--adjacent-evidence",
            "The focused module imports and calls the public function normally.",
            "--root-cause-alignment",
            "PASS",
        ]

    def test_prepare_rejects_unbound_target_before_creating_review(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="rootloom-orchestrator-",
            dir=Path.home(),
        ) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            review_dir = root / "review"

            completed = subprocess.run(
                self.prepare_command(
                    repo=repo,
                    review_dir=review_dir,
                    target="not-in-command",
                ),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "--target must be a non-empty literal substring",
                completed.stderr,
            )
            self.assertFalse(review_dir.exists())

    def test_finish_requires_explicit_semantic_review_confirmation(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ORCHESTRATOR),
                "finish",
                "--repo",
                "/fixture/repo",
                "--task",
                "fixture",
                "--review-dir",
                "/fixture/review",
                "--output",
                "/fixture/output",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--semantic-review-confirmed", completed.stderr)

    def test_prepare_and_finish_strict_evidence_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="rootloom-orchestrator-",
            dir=Path.home(),
        ) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            review_dir = root / "review"
            output = root / "result"
            task = "Fix the application value defect at its owning function."

            prepared = subprocess.run(
                self.prepare_command(repo=repo, review_dir=review_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            prepared_payload = json.loads(prepared.stdout)
            self.assertEqual(prepared_payload["status"], "prepared-and-sealed")
            self.assertTrue((review_dir / "baseline.json").is_file())
            self.assertTrue((review_dir / "change-contract.json").is_file())
            self.assertTrue((review_dir / "contract.seal.json").is_file())

            (repo / "app.py").write_text(
                "def current_value():\n    return 2\n",
                encoding="utf-8",
            )
            finished = subprocess.run(
                [
                    sys.executable,
                    str(ORCHESTRATOR),
                    "finish",
                    "--repo",
                    str(repo),
                    "--task",
                    task,
                    "--review-dir",
                    str(review_dir),
                    "--output",
                    str(output),
                    "--semantic-review-confirmed",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(finished.returncode, 0, finished.stderr)
            finished_payload = json.loads(finished.stdout)
            self.assertEqual(
                finished_payload["status"],
                "REVIEW_EVIDENCE_COMPLETE",
            )
            self.assertTrue(finished_payload["evidence_complete"])
            summary = json.loads(
                (output / "summary.json").read_text(encoding="ascii")
            )
            self.assertEqual(summary["schema_revision"], 5)
            self.assertEqual(summary["verification_coverage"], "complete")
            self.assertTrue(summary["hash_chain"]["valid"])


if __name__ == "__main__":
    unittest.main()
