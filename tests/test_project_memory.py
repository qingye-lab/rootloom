from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "experiments"
    / "rootloom-memory"
    / "skills"
    / "project-memory"
    / "scripts"
    / "project_memory.py"
)
sys.path.insert(0, str(REPO_ROOT / "experiments" / "rootloom-memory" / "lib"))
import rootloom_memory


class ProjectMemoryTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        return repo

    def run_memory(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_context_does_not_initialize_missing_memory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            context = self.run_memory(repo, "context")
            self.assertEqual(context.returncode, 0, context.stderr)
            payload = json.loads(context.stdout)
            self.assertEqual(payload["format"], "rootloom-project-context-v1")
            self.assertEqual(payload["failures"], [])
            self.assertFalse((repo / ".project-memory").exists())

    def test_init_and_record_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            initialized = self.run_memory(repo, "init")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            recorded = self.run_memory(
                repo,
                "record-failure",
                "--summary",
                "reconnect failed",
                "--root-cause",
                "state race",
                "--fix",
                "serialize transitions",
                "--path",
                "src/relay.py",
                "--evidence",
                "tests/test_relay.py::test_reconnect",
                "--expires",
                "2099-12-31",
            )
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            output = json.loads(recorded.stdout)
            self.assertRegex(output["id"], r"^failure-[0-9a-f]{16}$")
            self.assertFalse(output["deduplicated"])
            payload = json.loads(
                (repo / ".project-memory" / "failures.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["entries"][0]["root_cause"], "state race")
            self.assertEqual(
                payload["entries"][0]["evidence"],
                ["tests/test_relay.py::test_reconnect"],
            )
            context = self.run_memory(repo, "context")
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertEqual(json.loads(context.stdout)["failures"][0]["fix"], "serialize transitions")

    def test_relevant_context_uses_paths_and_query_without_rewriting_memory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            for summary, path in (
                ("relay reconnect race", "src/relay.py"),
                ("invoice rounding", "src/billing.py"),
            ):
                recorded = self.run_memory(
                    repo,
                    "record-failure",
                    "--summary",
                    summary,
                    "--root-cause",
                    "state transition",
                    "--fix",
                    "enforce owner invariant",
                    "--path",
                    path,
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
            memory_file = repo / ".project-memory" / "failures.json"
            before = memory_file.read_bytes()
            context = self.run_memory(
                repo,
                "context",
                "--path",
                "src/relay/connection.py",
                "--query",
                "reconnect",
            )
            self.assertEqual(context.returncode, 0, context.stderr)
            payload = json.loads(context.stdout)
            self.assertEqual(
                [entry["summary"] for entry in payload["failures"]],
                ["relay reconnect race"],
            )
            self.assertEqual(memory_file.read_bytes(), before)

    def test_exact_duplicate_is_suppressed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            command = (
                "record-risk",
                "--summary",
                "relay reconnect can race",
                "--mitigation",
                "serialize transitions",
                "--path",
                "src/relay.py",
                "--evidence",
                "tests/test_relay.py",
            )
            first = self.run_memory(repo, *command)
            second = self.run_memory(repo, *command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse(json.loads(first.stdout)["deduplicated"])
            self.assertTrue(json.loads(second.stdout)["deduplicated"])
            payload = json.loads(
                (repo / ".project-memory" / "known-risks.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(payload["entries"]), 1)

    def test_concurrent_writers_reload_under_lock_without_lost_updates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            initialized = self.run_memory(repo, "init")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            processes = [
                subprocess.Popen(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--repo",
                        str(repo),
                        "record-risk",
                        "--summary",
                        f"risk {index}",
                        "--mitigation",
                        "serialize writer",
                        "--path",
                        f"src/module_{index}.py",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for index in range(12)
            ]
            results = [process.communicate(timeout=10) for process in processes]
            self.assertEqual(
                [process.returncode for process in processes],
                [0] * len(processes),
                results,
            )
            payload = json.loads(
                (repo / ".project-memory" / "known-risks.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(payload["entries"]), len(processes))

    def test_bounded_reader_detects_stat_to_read_size_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            path = Path(temporary) / "memory.json"
            path.write_bytes(b"x" * (70 * 1024))
            original_read = rootloom_memory.os.read
            mutated = False

            def racing_read(descriptor: int, size: int) -> bytes:
                nonlocal mutated
                chunk = original_read(descriptor, size)
                if chunk and not mutated:
                    mutated = True
                    with path.open("ab") as handle:
                        handle.write(b"drift")
                return chunk

            with mock.patch.object(rootloom_memory.os, "read", side_effect=racing_read):
                with self.assertRaisesRegex(ValueError, "changed during read"):
                    rootloom_memory.bounded_read(path, 128 * 1024)

    def test_stale_memory_is_warned_and_excluded_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            recorded = self.run_memory(
                repo,
                "record-risk",
                "--summary",
                "legacy token format",
                "--mitigation",
                "check parser compatibility",
                "--path",
                "src/auth/token.py",
            )
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            path = repo / ".project-memory" / "known-risks.json"
            collection = json.loads(path.read_text(encoding="utf-8"))
            collection["entries"][0]["expires"] = "2000-01-01"
            path.write_text(json.dumps(collection), encoding="utf-8")

            current = self.run_memory(repo, "context", "--path", "src/auth/token.py")
            self.assertEqual(current.returncode, 0, current.stderr)
            payload = json.loads(current.stdout)
            self.assertEqual(payload["risks"], [])
            self.assertEqual(payload["stale"]["risks"][0]["reason"], "expired:2000-01-01")

            history = self.run_memory(
                repo,
                "context",
                "--path",
                "src/auth/token.py",
                "--include-stale",
            )
            self.assertEqual(history.returncode, 0, history.stderr)
            self.assertEqual(len(json.loads(history.stdout)["risks"]), 1)

    def test_status_transition_supports_legacy_entry_ids(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            memory = repo / ".project-memory"
            memory.mkdir()
            legacy = {
                "format": "rootloom-project-memory-v1",
                "kind": "decisions",
                "entries": [
                    {
                        "date": "2026-01-01",
                        "summary": "use relay boundary",
                        "record": "docs/decisions/relay.md",
                        "paths": ["../legacy/relay.py"],
                    }
                ],
            }
            (memory / "decisions.json").write_text(json.dumps(legacy), encoding="utf-8")
            context = self.run_memory(repo, "context", "--query", "relay")
            self.assertEqual(context.returncode, 0, context.stderr)
            entry_id = json.loads(context.stdout)["decisions"][0]["id"]
            changed = self.run_memory(
                repo,
                "set-status",
                "--kind",
                "decisions",
                "--id",
                entry_id,
                "--status",
                "superseded",
                "--superseded-by",
                "decision-newer",
            )
            self.assertEqual(changed.returncode, 0, changed.stderr)
            stored = json.loads(
                (memory / "decisions.json").read_text(encoding="utf-8")
            )["entries"][0]
            self.assertEqual(stored["status"], "superseded")
            self.assertEqual(stored["superseded_by"], "decision-newer")

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_symlinked_memory_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            outside = root / "outside"
            outside.mkdir()
            (repo / ".project-memory").symlink_to(outside, target_is_directory=True)
            refused = self.run_memory(repo, "context")
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("must not be a symlink", refused.stderr)

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_symlinked_memory_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            memory = repo / ".project-memory"
            memory.mkdir()
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            (memory / "known-risks.json").symlink_to(outside)
            refused = self.run_memory(repo, "context")
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("files must not be symlinks", refused.stderr)

    def test_absolute_memory_path_is_rejected_without_initializing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-memory-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            rejected = self.run_memory(
                repo,
                "record-risk",
                "--summary",
                "unsafe path",
                "--mitigation",
                "reject it",
                "--path",
                "/tmp/outside",
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("repository-relative", rejected.stderr)
            self.assertFalse((repo / ".project-memory").exists())


if __name__ == "__main__":
    unittest.main()
