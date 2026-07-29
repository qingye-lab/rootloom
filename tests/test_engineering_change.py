from __future__ import annotations

import json
import hashlib
import inspect
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "rootloom"
    / "resources"
    / "evidence"
    / "finalize_change.py"
)
ANALYZE = SCRIPT.parent / "analyze_change.py"
BEGIN_REVIEW = SCRIPT.parent / "begin_review.py"
SEAL_CONTRACT = SCRIPT.parent / "seal_contract.py"
sys.path.insert(0, str(SCRIPT.parent))
import begin_review as begin_review_module
import finalize_change as finalize_change_module
from rootloom_paths import (
    MAX_REVIEWABLE_PATHS,
    is_protected_deletion_path,
    is_security_domain_path,
    is_sensitive_material_path,
    normalize_reviewable_paths,
)
from runner.baseline import payload_sha256, read_baseline_payload_with_hash
from runner.change_contract import load_change_contract, path_matches
from runner.evidence_paths import rename_directory_no_replace
from runner.intelligence import (
    MAX_COMMAND_DISCOVERY_BYTES,
    analyze_change as analyze_change_intelligence,
    read_bounded_repository_text,
)
from runner.contracts import VerificationResult
from runner.process import (
    _controlled_tree_active,
    _controlled_tree_inactive_after_grace,
)
from runner.review_run import CONTRACT_DRAFT_SENTINEL
from runner.state import (
    CaptureDeadline,
    _new_file_patch,
    canonical_reviewable_paths,
    discover_sensitive_paths,
    filter_untracked_patch,
    git_bounded,
    repository_snapshot,
    stable_repository_capture,
    tracked_patch,
)
from runner.strict_json import parse_json_object
from runner.verification import split_command, verify


class EngineeringChangeTests(unittest.TestCase):
    ALL_CLAIM_IDS = (
        "primary-behavior",
        "owning-invariant",
        "adjacent-path",
        "auth-boundaries",
        "data-compatibility",
        "financial-boundaries",
        "ordering-and-races",
        "deployment-contract",
        "consumer-compatibility",
        "destructive-effect",
        "historical-counterexample",
    )

    @staticmethod
    def contract_sha256(payload: dict[str, object]) -> str:
        normalized = dict(payload)
        normalized.pop("contract_sha256", None)
        encoded = json.dumps(
            normalized, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()
    def test_windows_command_split_preserves_backslash_paths_and_outer_quotes(self) -> None:
        raw = r"C:\hostedtoolcache\Python\python.exe -c 'assert 2 == 2'"
        self.assertEqual(
            split_command(raw, windows=True),
            [r"C:\hostedtoolcache\Python\python.exe", "-c", "assert 2 == 2"],
        )
        nested = r'''C:\hostedtoolcache\Python\python.exe -c '__import__("pathlib").Path(".env").unlink()' '''.strip()
        self.assertEqual(
            split_command(nested, windows=True),
            [
                r"C:\hostedtoolcache\Python\python.exe",
                "-c",
                '__import__("pathlib").Path(".env").unlink()',
            ],
        )

    def test_windows_process_fallback_does_not_treat_missing_job_support_as_a_leak(self) -> None:
        process = mock.Mock()
        process.poll.return_value = 0
        job = mock.Mock()
        job.supported = False
        with mock.patch("runner.process.os.name", "nt"):
            self.assertFalse(_controlled_tree_active(process, job))
        process.poll.return_value = None
        with mock.patch("runner.process.os.name", "nt"):
            self.assertTrue(_controlled_tree_active(process, job))

    def test_windows_job_accounting_gets_a_post_exit_convergence_grace(self) -> None:
        process = mock.Mock()
        job = mock.Mock()
        job.supported = True
        job.active.side_effect = [True, False]
        with mock.patch("runner.process.os.name", "nt"):
            self.assertTrue(
                _controlled_tree_inactive_after_grace(process, job, timeout=0.1)
            )

        job.active.side_effect = None
        job.active.return_value = True
        with mock.patch("runner.process.os.name", "nt"):
            self.assertFalse(
                _controlled_tree_inactive_after_grace(process, job, timeout=0)
            )

    def test_git_capture_uses_the_bounded_process_tree_and_translates_timeout(self) -> None:
        with mock.patch("runner.state.run_command") as controlled:
            for invalid in (float("nan"), float("inf")):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "finite and positive"):
                        git_bounded(
                            Path("/repository"),
                            "status",
                            max_bytes=128,
                            max_git_seconds=invalid,
                        )
            controlled.assert_not_called()

        timed_out = VerificationResult(
            command=["git", "--no-pager", "status"],
            exit_code=124,
            duration_seconds=0.25,
            passed=False,
            timed_out=True,
        )
        with mock.patch(
            "runner.state.run_command",
            return_value=(timed_out, b"Rootloom: command timed out\n"),
        ) as controlled:
            with self.assertRaisesRegex(
                ValueError,
                "Git command exceeded configured 0.25-second budget",
            ):
                git_bounded(
                    Path("/repository"),
                    "status",
                    max_bytes=128,
                    max_git_seconds=0.25,
                )
        self.assertEqual(controlled.call_args.kwargs["timeout"], 0.25)
        self.assertEqual(controlled.call_args.kwargs["max_output_bytes"], 128)

    def test_git_capture_uses_the_remaining_aggregate_deadline(self) -> None:
        passed = VerificationResult(
            command=["git", "--no-pager", "status"],
            exit_code=0,
            duration_seconds=1.0,
            passed=True,
        )
        with mock.patch("runner.state.time.monotonic", side_effect=[10.0, 12.0, 13.0]):
            deadline = CaptureDeadline(10.0)
            with mock.patch(
                "runner.state.run_command",
                return_value=(passed, b""),
            ) as controlled:
                git_bounded(
                    Path("/repository"),
                    "status",
                    max_bytes=128,
                    max_git_seconds=30.0,
                    capture_deadline=deadline,
                )
        self.assertEqual(controlled.call_args.kwargs["timeout"], 8.0)

    def test_stable_capture_deadline_is_shared_across_both_passes(self) -> None:
        clock = [0.0]

        def advance(deadline: CaptureDeadline) -> None:
            clock[0] += 20.0
            deadline.checkpoint()

        def fake_identity(_repo, *, capture_deadline, **_kwargs):
            advance(capture_deadline)
            return {"head": "a" * 40, "head_ref": "refs/heads/main", "index_sha256": "b" * 40}

        def fake_snapshot(_repo, *, capture_deadline, **_kwargs):
            advance(capture_deadline)
            return (
                {
                    "changes": [],
                    "untracked": [],
                    "sensitive_paths": [],
                    "bounds": {
                        "fingerprint_bytes_observed": 0,
                        "untracked_patch_bytes": 0,
                        "sensitive_change_quarantine": False,
                    },
                },
                b"",
            )

        def fake_patch(_repo, *, capture_deadline, **_kwargs):
            advance(capture_deadline)
            return b""

        with (
            mock.patch("runner.state.time.monotonic", side_effect=lambda: clock[0]),
            mock.patch("runner.state.git_identity", side_effect=fake_identity),
            mock.patch("runner.state.repository_snapshot", side_effect=fake_snapshot),
            mock.patch("runner.state.tracked_patch", side_effect=fake_patch),
        ):
            with self.assertRaisesRegex(ValueError, "90-second aggregate budget"):
                stable_repository_capture(
                    Path("/repository"),
                    max_capture_seconds=90.0,
                )

    def test_sensitive_preflight_propagates_the_capture_deadline(self) -> None:
        deadline = CaptureDeadline(90.0)
        snapshot = {"sensitive_paths": []}
        metadata = {
            "path": "clientSecret.json",
            "exists": True,
            "sensitive": True,
            "content_read": False,
            "kind": "file",
            "size": 12,
        }
        with (
            mock.patch(
                "finalize_change.discover_sensitive_paths",
                return_value=["clientSecret.json"],
            ) as discover,
            mock.patch(
                "finalize_change.metadata_only",
                return_value=metadata,
            ) as metadata_only_mock,
        ):
            changes = finalize_change_module.sensitive_path_changes(
                Path("/repository"),
                snapshot,
                extra_sensitive=set(),
                capture_deadline=deadline,
            )
        self.assertEqual(changes["added"], ["clientSecret.json"])
        self.assertIs(discover.call_args.kwargs["capture_deadline"], deadline)
        self.assertIs(
            metadata_only_mock.call_args.kwargs["capture_deadline"],
            deadline,
        )

    def test_verification_output_budget_is_aggregate_and_strict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            first = f"{sys.executable} -c 'print(\"a\")'"
            second = f"{sys.executable} -c 'print(\"b\")'"
            first_chunk_size = len(f"$ {first}\n".encode("utf-8")) + 2
            budget = first_chunk_size + 6
            results, log = verify(
                [first, second],
                repo=repo,
                timeout=30,
                max_output_bytes=budget,
            )
            self.assertEqual(results[0].exit_code, 0)
            self.assertEqual(results[1].exit_code, 125)
            self.assertLessEqual(len(log), budget)

            noisy = f"{sys.executable} -c 'print(\"x\" * 1000)'"
            noisy_budget = len(f"$ {noisy}\n".encode("utf-8")) + 32
            noisy_results, noisy_log = verify(
                [noisy],
                repo=repo,
                timeout=30,
                max_output_bytes=noisy_budget,
            )
            self.assertEqual(noisy_results[0].exit_code, 125)
            self.assertTrue(noisy_results[0].output_limit_exceeded)
            self.assertGreater(
                noisy_results[0].output_bytes_observed,
                noisy_results[0].output_bytes_retained,
            )
            self.assertLessEqual(len(noisy_log), noisy_budget)

    def test_verification_parses_every_command_before_any_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            marker = repo / "must-not-exist"
            first = (
                f"{sys.executable} -c "
                "'__import__(\"pathlib\").Path(\"must-not-exist\").touch()'"
            )
            with self.assertRaises(ValueError):
                verify(
                    [first, "unterminated '"],
                    repo=repo,
                    timeout=30,
                    max_output_bytes=4096,
                )
            self.assertFalse(marker.exists())

    @unittest.skipIf(os.name == "nt", "POSIX process-group regression")
    def test_verification_terminates_a_leaked_descendant_process_group(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            command = (
                f"{sys.executable} -c 'import subprocess,sys; "
                "subprocess.Popen([sys.executable,\"-c\",\"import time; time.sleep(30)\"],"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)'"
            )
            started = time.monotonic()
            results, _log = verify(
                [command], repo=repo, timeout=10, max_output_bytes=4096
            )
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual(results[0].exit_code, 125)
            self.assertTrue(results[0].process_tree_converged)
            self.assertFalse(results[0].passed)

    def test_missing_verification_executable_is_a_bounded_failed_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = "rootloom-command-that-does-not-exist"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="missing-command"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads(
                (root / "run" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["tests"][0]["exit_code"], 126)
            self.assertFalse(summary["passed"])
            self.assertIn(
                "command could not run",
                (root / "run" / "test.log").read_text(encoding="utf-8"),
            )

    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
        return repo

    def analyze(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ANALYZE), "--repo", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def prepare_governed_change(
        self,
        root: Path,
        repo: Path,
        *,
        command: str,
        task: str = "change product behavior",
        allowed_paths: list[str] | None = None,
        claims: tuple[str, ...] | None = None,
        name: str = "change",
        allow_dirty_baseline: bool = False,
        reviewable_paths: list[str] | None = None,
    ) -> list[str]:
        review_dir = root / f"{name}-review"
        baseline = review_dir / "baseline.json"
        begun = subprocess.run(
            [
                sys.executable,
                str(BEGIN_REVIEW),
                "--repo",
                str(repo),
                "--task",
                task,
                "--output",
                str(review_dir),
                *[
                    part
                    for path in (allowed_paths or ["**"])
                    for part in ("--path", path)
                ],
                *[
                    part
                    for path in (reviewable_paths or [])
                    for part in ("--reviewable-path", path)
                ],
                *(["--allow-dirty-baseline"] if allow_dirty_baseline else []),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(begun.returncode, 0, begun.stderr)
        baseline_payload = json.loads(baseline.read_text(encoding="ascii"))
        baseline_sha256 = hashlib.sha256(baseline.read_bytes()).hexdigest()
        draft = review_dir / "change-contract.draft.json"
        payload = {
            "format": "rootloom-change-contract-v1",
            "run_id": baseline_payload["run_id"],
            "nonce": baseline_payload["nonce"],
            "baseline_sha256": baseline_sha256,
            "task_sha256": baseline_payload["task_sha256"],
            "allowed_paths": allowed_paths or ["**"],
            "forbidden_paths": [],
            "root_cause_alignment": "PASS",
            "verification_commands": {"verify-1": command},
            "verification_claims": {
                claim: [
                    {
                        "id": claim,
                        "command_ids": ["verify-1"],
                        "target": command.split()[0],
                        "expected_evidence": f"{claim} behavior is exercised",
                        "evidence_kind": "regression-test",
                    }
                ]
                for claim in (claims or self.ALL_CLAIM_IDS)
            },
        }
        draft.write_text(json.dumps(payload), encoding="utf-8")
        sealed = subprocess.run(
            [
                sys.executable,
                str(SEAL_CONTRACT),
                "--review-dir",
                str(review_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(sealed.returncode, 0, sealed.stderr)
        contract = review_dir / "change-contract.json"
        return [
            "--task",
            task,
            "--baseline",
            str(baseline),
            "--change-contract",
            str(contract),
            "--semantic-coverage",
            "reviewed",
        ]

    def test_analyzer_keeps_docs_auth_reference_low_risk(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            completed = self.analyze(
                repo,
                "--task",
                "Document the authentication flow",
                "--path",
                "docs/auth.md",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            assessment = json.loads(completed.stdout)
            self.assertEqual(assessment["detected_risk"], "low")
            self.assertEqual(assessment["minimum_tier"], 0)
            self.assertEqual(
                [item["id"] for item in assessment["signals"]],
                ["docs-or-tests-only"],
            )

    def test_capture_cli_budgets_must_be_finite_and_positive(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            invalid = (
                ("--max-capture-seconds", "0", "finite and positive"),
                ("--max-capture-seconds", "nan", "finite and positive"),
                ("--max-capture-seconds", "inf", "finite and positive"),
                ("--max-git-seconds", "0", "finite and positive"),
                ("--max-git-seconds", "nan", "finite and positive"),
                ("--max-git-seconds", "inf", "finite and positive"),
                ("--max-sensitive-paths", "0", "must be positive"),
            )
            for flag, value, message in invalid:
                with self.subTest(flag=flag, value=value):
                    completed = self.analyze(repo, flag, value)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn(message, completed.stderr)

            entry_points = (
                (
                    BEGIN_REVIEW,
                    [
                        "--repo",
                        str(repo),
                        "--task",
                        "bounded intake",
                        "--output",
                        str(Path(temporary) / "invalid-intake"),
                        "--allow-all-paths",
                    ],
                ),
                (
                    SCRIPT,
                    [
                        "--repo",
                        str(repo),
                        "--output",
                        str(Path(temporary) / "invalid-finalizer"),
                    ],
                ),
            )
            for script, arguments in entry_points:
                with self.subTest(script=script.name):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(script),
                            *arguments,
                            "--max-capture-seconds",
                            "nan",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("finite and positive", completed.stderr)

    def test_begin_review_creates_intake_sealed_v3_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            output = root / "review"
            created = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "change product behavior",
                    "--output",
                    str(output),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            manifest = json.loads((output / "review.json").read_text(encoding="ascii"))
            baseline = json.loads((output / "baseline.json").read_text(encoding="ascii"))
            self.assertEqual(baseline["format"], "rootloom-change-baseline-v3")
            self.assertNotIn("reviewable_paths", baseline)
            self.assertEqual(baseline["evidence_provenance"], "intake-sealed")
            draft_path = output / "change-contract.draft.json"
            contract = json.loads(draft_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_id"], baseline["run_id"])
            self.assertEqual(manifest["nonce"], baseline["nonce"])
            self.assertEqual(manifest["baseline"], "baseline.json")
            self.assertEqual(
                manifest["change_contract_draft"], "change-contract.draft.json"
            )
            self.assertFalse((output / "change-contract.json").exists())
            self.assertFalse((output / "contract.seal.json").exists())
            self.assertEqual(contract["run_id"], baseline["run_id"])
            self.assertEqual(contract["nonce"], baseline["nonce"])
            self.assertEqual(
                contract["baseline_sha256"],
                hashlib.sha256((output / "baseline.json").read_bytes()).hexdigest(),
            )
            self.assertEqual(manifest["baseline_sha256"], contract["baseline_sha256"])
            self.assertEqual(
                contract["verification_commands"]["verify-primary"],
                CONTRACT_DRAFT_SENTINEL,
            )
            todo_refused = subprocess.run(
                [sys.executable, str(SEAL_CONTRACT), "--review-dir", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(todo_refused.returncode, 0)
            self.assertIn("placeholder", todo_refused.stderr.lower())
            contract["verification_commands"]["verify-primary"] = "echo TODO"
            contract["verification_claims"]["primary-behavior"][0]["target"] = "TODO"
            contract["verification_claims"]["primary-behavior"][0][
                "expected_evidence"
            ] = "legacy target must be replaced"
            draft_path.write_text(json.dumps(contract), encoding="utf-8")
            legacy_target_refused = subprocess.run(
                [sys.executable, str(SEAL_CONTRACT), "--review-dir", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(legacy_target_refused.returncode, 0)
            self.assertIn("placeholder", legacy_target_refused.stderr.lower())
            command = f"{sys.executable} -c 'assert True'"
            contract["root_cause_alignment"] = "PASS"
            contract["verification_commands"] = {"verify-1": command}
            contract["verification_claims"] = {
                claim: [
                    {
                        "id": claim,
                        "command_ids": ["verify-1"],
                        "target": sys.executable,
                        "expected_evidence": f"{claim} is reviewed",
                        "evidence_kind": "regression-test",
                    }
                ]
                for claim in self.ALL_CLAIM_IDS
            }
            contract["verification_claims"]["primary-behavior"][0][
                "unexpected"
            ] = True
            draft_path.write_text(json.dumps(contract), encoding="utf-8")
            malformed = subprocess.run(
                [sys.executable, str(SEAL_CONTRACT), "--review-dir", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(malformed.returncode, 0)
            self.assertIn("unexpected or missing fields", malformed.stderr)
            del contract["verification_claims"]["primary-behavior"][0][
                "unexpected"
            ]
            contract["verification_claims"]["primary-behavior"][0][
                "expected_evidence"
            ] = "TodoService behavior is reviewed"
            draft_path.write_text(json.dumps(contract), encoding="utf-8")
            manifest_before = (output / "review.json").read_bytes()
            sealed = subprocess.run(
                [sys.executable, str(SEAL_CONTRACT), "--review-dir", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(sealed.returncode, 0, sealed.stderr)
            self.assertEqual((output / "review.json").read_bytes(), manifest_before)
            final_contract = json.loads(
                (output / "change-contract.json").read_text(encoding="ascii")
            )
            seal = json.loads((output / "contract.seal.json").read_text(encoding="ascii"))
            self.assertEqual(final_contract["contract_sha256"], seal["contract_sha256"])
            self.assertEqual(
                seal["contract_file_sha256"],
                hashlib.sha256((output / "change-contract.json").read_bytes()).hexdigest(),
            )
            self.assertEqual(
                seal["review_manifest_sha256"],
                hashlib.sha256(manifest_before).hexdigest(),
            )
            refused = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "change product behavior",
                    "--output",
                    str(output),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("already exists", refused.stderr)

    def test_begin_review_seals_exact_reviewable_path_in_opt_in_v4(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            public_pem = repo / "public-chain.pem"
            public_pem.write_text("PUBLIC CERTIFICATE V1\n", encoding="utf-8")
            env_template = repo / ".env.example"
            env_template.write_text("API_URL=https://example.invalid\n", encoding="utf-8")
            certs = repo / "certs"
            certs.mkdir()
            public_crt = certs / "public-root.crt"
            public_crt.write_text("PUBLIC ROOT CERTIFICATE\n", encoding="utf-8")
            public_der = certs / "public.der"
            public_der.write_text("PUBLIC DER CERTIFICATE\n", encoding="utf-8")
            subprocess.run(
                [
                    "git",
                    "add",
                    public_pem.name,
                    env_template.name,
                    "certs/public-root.crt",
                    "certs/public.der",
                ],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "commit", "-qm", "add public certificate"], cwd=repo, check=True)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=[public_pem.name],
                reviewable_paths=[
                    public_pem.name,
                    env_template.name,
                    "certs/public-root.crt",
                    "certs/public.der",
                ],
                name="reviewable-pem",
            )
            baseline_path = Path(governed[3])
            baseline = json.loads(baseline_path.read_text(encoding="ascii"))
            self.assertEqual(baseline["format"], "rootloom-change-baseline-v4")
            self.assertEqual(
                baseline["reviewable_paths"],
                [
                    env_template.name,
                    "certs/public-root.crt",
                    "certs/public.der",
                    public_pem.name,
                ],
            )
            self.assertNotIn(
                public_pem.name,
                {item["path"] for item in baseline["snapshot"]["sensitive_paths"]},
            )
            policy = {
                "extra_sensitive": baseline["sensitive_paths"],
                "reviewable_paths": baseline["reviewable_paths"],
                "snapshot_sensitive_paths": baseline["snapshot"]["sensitive_paths"],
            }
            self.assertEqual(
                baseline["sensitive_policy_sha256"], payload_sha256(policy)
            )

            public_pem.write_text("PUBLIC CERTIFICATE V2\n", encoding="utf-8")
            output = root / "reviewable-run"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="ascii"))
            self.assertEqual(summary["baseline"]["format"], "rootloom-change-baseline-v4")
            self.assertEqual(summary["risk"], "high")
            self.assertFalse(summary["sensitive_change_quarantine"])
            reviewability = summary["reviewability_policy"]
            self.assertEqual(
                set(reviewability),
                {
                    "captured_files",
                    "captured_files_provenance",
                    "enabled",
                    "paths",
                    "policy_provenance",
                    "policy_sha256",
                    "source",
                },
            )
            self.assertTrue(reviewability["enabled"])
            self.assertEqual(reviewability["paths"], baseline["reviewable_paths"])
            self.assertEqual(
                reviewability["policy_sha256"],
                baseline["sensitive_policy_sha256"],
            )
            self.assertEqual(reviewability["source"], "intake-sealed")
            self.assertEqual(
                reviewability["policy_provenance"], "intake-sealed"
            )
            self.assertEqual(
                reviewability["captured_files_provenance"],
                "final-capture-observed",
            )
            self.assertEqual(
                [
                    item["path"]
                    for item in reviewability["captured_files"]
                ],
                baseline["reviewable_paths"],
            )
            self.assertTrue(
                all(
                    item["link_count"] == 1
                    for item in reviewability["captured_files"]
                )
            )
            self.assertTrue(
                all(
                    set(item)
                    == {
                        "path",
                        "kind",
                        "exists",
                        "device",
                        "inode",
                        "link_count",
                        "size",
                        "mode",
                        "mtime_ns",
                        "ctime_ns",
                    }
                    for item in reviewability["captured_files"]
                )
            )
            self.assertNotIn(
                public_pem.name,
                {
                    item["path"]
                    for item in summary["repository_capture"]["sensitive_paths"]
                },
            )
            self.assertIn(
                "PUBLIC CERTIFICATE V2",
                (output / "diff.patch").read_text(encoding="utf-8"),
            )

            advisory_output = root / "reviewable-advisory-run"
            advisory = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(advisory_output),
                    "--task",
                    "change product behavior",
                    "--baseline",
                    str(baseline_path),
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(advisory.returncode, 0, advisory.stderr)
            advisory_summary = json.loads(
                (advisory_output / "summary.json").read_text(encoding="ascii")
            )
            self.assertEqual(
                advisory_summary["reviewability_policy"]["policy_provenance"],
                "self-declared",
            )
            self.assertEqual(
                advisory_summary["reviewability_policy"]["source"],
                "self-declared",
            )

            policy_tamper = json.loads(json.dumps(baseline))
            policy_tamper["reviewable_paths"] = ["other-public.pem"]
            policy_tamper_path = root / "policy-tampered-v4.json"
            policy_tamper_path.write_text(json.dumps(policy_tamper), encoding="ascii")
            with self.assertRaisesRegex(ValueError, "sensitive_policy_sha256"):
                read_baseline_payload_with_hash(policy_tamper_path)

            historical = json.loads(json.dumps(baseline))
            historical["reviewable_paths"] = ["server-key.pem"]
            historical["sensitive_policy_sha256"] = payload_sha256(
                {
                    "extra_sensitive": historical["sensitive_paths"],
                    "reviewable_paths": historical["reviewable_paths"],
                    "snapshot_sensitive_paths": historical["snapshot"]["sensitive_paths"],
                }
            )
            historical_path = root / "historical-v4.json"
            historical_path.write_text(json.dumps(historical), encoding="ascii")
            loaded_historical, _ = read_baseline_payload_with_hash(historical_path)
            self.assertEqual(loaded_historical["reviewable_paths"], ["server-key.pem"])

            reintake = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "historical-run"),
                    "--task",
                    "change product behavior",
                    "--baseline",
                    str(historical_path),
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(reintake.returncode, 11, reintake.stderr)
            self.assertEqual(json.loads(reintake.stdout)["status"], "reintake-required")
            self.assertFalse((root / "historical-run").exists())

    def test_begin_review_rejects_invalid_reviewable_path_overrides(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "public.pem").write_text("PUBLIC CERTIFICATE\n", encoding="utf-8")
            (repo / "private.key").write_text("synthetic-private-key\n", encoding="utf-8")
            (repo / "private-key.pem").write_text("synthetic-private-key\n", encoding="utf-8")
            for name in (
                "key.pem",
                "key.der",
                "server-key.pem",
                "server-key.der",
                "client-key.pem",
                "client-key.der",
                "host-key.pem",
                "host-key.der",
                "ssh-key.pem",
                "ssh-key.der",
                "identity-key.pem",
                "identity-key.der",
                "privkey.pem",
                "privatekey.pem",
                "rsa-key.pem",
                "ec-key.pem",
                "ecdsa-key.pem",
                "ed25519-key.pem",
                "encryption-key.pem",
                "decryption-key.pem",
            ):
                (repo / name).write_text("synthetic-private-key\n", encoding="utf-8")
            (repo / ".env").write_text("TOKEN=synthetic\n", encoding="utf-8")
            (repo / "public.crt").write_text("PUBLIC CERTIFICATE\n", encoding="utf-8")
            (repo / "material-dir").mkdir()
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add classification fixtures"], cwd=repo, check=True)

            cases = (
                ("glob", ["--reviewable-path", "*.pem"], "exact file path"),
                ("missing", ["--reviewable-path", "missing.pem"], "existing regular file"),
                ("directory", ["--reviewable-path", "material-dir"], "regular file"),
                ("strong-key", ["--reviewable-path", "private.key"], "strong sensitive material"),
                (
                    "strong-named-pem",
                    ["--reviewable-path", "private-key.pem"],
                    "strong sensitive material",
                ),
                *(
                    (
                        f"strong-{name}",
                        ["--reviewable-path", name],
                        "strong sensitive material",
                    )
                    for name in (
                        "key.pem",
                        "key.der",
                        "server-key.pem",
                        "server-key.der",
                        "client-key.pem",
                        "client-key.der",
                        "host-key.pem",
                        "host-key.der",
                        "ssh-key.pem",
                        "ssh-key.der",
                        "identity-key.pem",
                        "identity-key.der",
                        "privkey.pem",
                        "privatekey.pem",
                        "rsa-key.pem",
                        "ec-key.pem",
                        "ecdsa-key.pem",
                        "ed25519-key.pem",
                        "encryption-key.pem",
                        "decryption-key.pem",
                    )
                ),
                ("strong-env", ["--reviewable-path", ".env"], "strong sensitive material"),
                (
                    "overlap",
                    [
                        "--sensitive-path",
                        "public.pem",
                        "--reviewable-path",
                        "public.pem",
                    ],
                    "overlaps declared sensitive material",
                ),
                (
                    "duplicate",
                    [
                        "--reviewable-path",
                        "public.pem",
                        "--reviewable-path",
                        "PUBLIC.pem",
                    ],
                    "case-insensitive duplicates",
                ),
                (
                    "exact-duplicate",
                    [
                        "--reviewable-path",
                        "public.pem",
                        "--reviewable-path",
                        "public.pem",
                    ],
                    "case-insensitive duplicates",
                ),
            )
            for name, extra, message in cases:
                with self.subTest(name=name):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(BEGIN_REVIEW),
                            "--repo",
                            str(repo),
                            "--task",
                            "review exact public material",
                            "--output",
                            str(root / f"invalid-{name}"),
                            "--path",
                            "app.py",
                            *extra,
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn(message, completed.stderr)

    def test_begin_review_rejects_ignored_reviewable_paths_and_rechecks_visibility(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text("ignored-public.pem\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore public fixture"], cwd=repo, check=True)
            (repo / "ignored-public.pem").write_text(
                "PUBLIC CERTIFICATE\n",
                encoding="utf-8",
            )
            rejected = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "review ignored public material",
                    "--output",
                    str(root / "ignored-review"),
                    "--path",
                    "app.py",
                    "--reviewable-path",
                    "ignored-public.pem",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(
                "reviewable path is ignored and cannot be captured reliably",
                rejected.stderr,
            )
            self.assertFalse((root / "ignored-review").exists())

            visible = repo / "visible-public.pem"
            visible.write_text("PUBLIC CERTIFICATE V1\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=[".gitignore", visible.name],
                reviewable_paths=[visible.name],
                allow_dirty_baseline=True,
                name="visible-reviewable",
            )
            with (repo / ".gitignore").open("a", encoding="utf-8") as handle:
                handle.write(f"{visible.name}\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "ignored-after-intake"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(
                "reviewable path is ignored and cannot be captured reliably",
                completed.stderr,
            )
            self.assertFalse((root / "ignored-after-intake").exists())

    def test_begin_review_rejects_index_suppressed_reviewable_paths_and_rechecks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            public_pem = repo / "public.pem"
            public_pem.write_text("PUBLIC CERTIFICATE V1\n", encoding="utf-8")
            subprocess.run(["git", "add", public_pem.name], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add public certificate"], cwd=repo, check=True)

            flag_cases = (
                ("assume-unchanged", "--assume-unchanged", "--no-assume-unchanged", "h"),
                ("skip-worktree", "--skip-worktree", "--no-skip-worktree", "S"),
            )
            for name, set_flag, clear_flag, expected_tag in flag_cases:
                with self.subTest(name=name):
                    subprocess.run(
                        ["git", "update-index", set_flag, public_pem.name],
                        cwd=repo,
                        check=True,
                    )
                    index_state = subprocess.run(
                        ["git", "ls-files", "-v", "--", public_pem.name],
                        cwd=repo,
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout
                    self.assertTrue(index_state.startswith(expected_tag + " "))
                    rejected = subprocess.run(
                        [
                            sys.executable,
                            str(BEGIN_REVIEW),
                            "--repo",
                            str(repo),
                            "--task",
                            "review public certificate",
                            "--output",
                            str(root / f"index-{name}-review"),
                            "--path",
                            public_pem.name,
                            "--reviewable-path",
                            public_pem.name,
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn(
                        "reviewable path is hidden by Git index flags "
                        "and cannot be captured reliably",
                        rejected.stderr,
                    )
                    self.assertFalse((root / f"index-{name}-review").exists())
                subprocess.run(
                    ["git", "update-index", clear_flag, public_pem.name],
                    cwd=repo,
                    check=True,
                )

            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["app.py", public_pem.name],
                reviewable_paths=[public_pem.name],
                name="index-suppression-recheck",
            )
            subprocess.run(
                ["git", "update-index", "--assume-unchanged", public_pem.name],
                cwd=repo,
                check=True,
            )
            public_pem.write_text("SYNTHETIC PRIVATE MATERIAL V2\n", encoding="utf-8")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "index-suppression-run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(
                "reviewable path is hidden by Git index flags "
                "and cannot be captured reliably",
                completed.stderr,
            )
            self.assertFalse((root / "index-suppression-run").exists())

    def test_begin_review_seals_repository_actual_reviewable_path_spelling(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            certificate_dir = repo / "Certs"
            certificate_dir.mkdir()
            certificate = certificate_dir / "Public.pem"
            certificate.write_text("PUBLIC CERTIFICATE\n", encoding="utf-8")
            subprocess.run(["git", "add", "Certs/Public.pem"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add mixed-case certificate"], cwd=repo, check=True)
            output = root / "case-review"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "review public certificate",
                    "--output",
                    str(output),
                    "--path",
                    "Certs/Public.pem",
                    "--reviewable-path",
                    "certs/public.pem",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            baseline = json.loads((output / "baseline.json").read_text(encoding="ascii"))
            self.assertEqual(baseline["reviewable_paths"], ["Certs/Public.pem"])

    def test_begin_review_rejects_casefold_ambiguous_repository_spelling(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            upper = repo / "Certs"
            lower = repo / "certs"
            upper.mkdir()
            if lower.exists():
                self.skipTest("filesystem does not support case-distinct paths")
            lower.mkdir()
            (upper / "Public.pem").write_text("PUBLIC CERTIFICATE A\n", encoding="utf-8")
            (lower / "public.pem").write_text("PUBLIC CERTIFICATE B\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "Certs/Public.pem", "certs/public.pem"],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "commit", "-qm", "add case-distinct certificates"], cwd=repo, check=True)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "review public certificate",
                    "--output",
                    str(root / "ambiguous-case-review"),
                    "--path",
                    "Certs/Public.pem",
                    "--reviewable-path",
                    "CERTS/PUBLIC.PEM",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(
                "reviewable path has case-insensitive repository ambiguity",
                completed.stderr,
            )

    def test_reviewable_spelling_resolver_rejects_casefold_ambiguity(self) -> None:
        with (
            mock.patch(
                "runner.state.git_list_paths",
                side_effect=[
                    ["Certs/Public.pem", "certs/public.pem"],
                    [],
                ],
            ),
            mock.patch("runner.state.git_index_path_tags", return_value={}),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "case-insensitive repository ambiguity",
            ):
                canonical_reviewable_paths(
                    Path("/repository"),
                    ["CERTS/PUBLIC.PEM"],
                )

    def test_reviewable_paths_have_an_independent_small_budget(self) -> None:
        paths = [f"certs/public-{index}.pem" for index in range(MAX_REVIEWABLE_PATHS + 1)]
        with self.assertRaisesRegex(ValueError, "64-path budget"):
            normalize_reviewable_paths(paths, max_paths=MAX_REVIEWABLE_PATHS)

    def test_reviewable_spelling_resolver_requires_prior_fingerprint_for_missing(self) -> None:
        with (
            mock.patch("runner.state.git_list_paths", side_effect=[[], []]),
            mock.patch("runner.state.git_index_path_tags", return_value={}),
            mock.patch("runner.state._lstat_reviewable_entry", return_value=None),
        ):
            with self.assertRaisesRegex(ValueError, "existing regular file"):
                canonical_reviewable_paths(
                    Path("/repository"),
                    ["public.pem"],
                )
        with (
            mock.patch("runner.state.git_list_paths", side_effect=[[], []]),
            mock.patch("runner.state.git_index_path_tags", return_value={}),
            mock.patch("runner.state._lstat_reviewable_entry", return_value=None),
        ):
            self.assertEqual(
                canonical_reviewable_paths(
                    Path("/repository"),
                    ["public.pem"],
                    allowed_missing={"public.pem"},
                ),
                ["public.pem"],
            )

    def test_reviewable_paths_reject_hardlinks_at_intake_and_capture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            linked = repo / "linked-public.pem"
            original = repo / "original-public.pem"
            original.write_text("PUBLIC CERTIFICATE\n", encoding="utf-8")
            try:
                os.link(original, linked)
            except OSError as exc:
                self.skipTest(f"hardlinks are unavailable: {exc}")
            subprocess.run(["git", "add", original.name, linked.name], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add hardlinked certificates"], cwd=repo, check=True)
            rejected = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "review public certificate",
                    "--output",
                    str(root / "hardlink-review"),
                    "--path",
                    linked.name,
                    "--reviewable-path",
                    linked.name,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("reviewable path must have link count one", rejected.stderr)

            public_pem = repo / "public.pem"
            public_pem.write_text("PUBLIC CERTIFICATE V1\n", encoding="utf-8")
            subprocess.run(["git", "add", public_pem.name], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add standalone certificate"], cwd=repo, check=True)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=[public_pem.name],
                reviewable_paths=[public_pem.name],
                name="hardlink-replacement",
            )
            outside_key = root / "outside-private-key"
            outside_key.write_text("SYNTHETIC PRIVATE KEY\n", encoding="utf-8")
            public_pem.unlink()
            os.link(outside_key, public_pem)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "hardlink-run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("reviewable path must have link count one", completed.stderr)
            self.assertFalse((root / "hardlink-run").exists())

    def test_reviewable_path_option_exists_only_at_intake(self) -> None:
        begin_help = subprocess.run(
            [sys.executable, str(BEGIN_REVIEW), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        finalizer_help = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(begin_help.returncode, 0, begin_help.stderr)
        self.assertEqual(finalizer_help.returncode, 0, finalizer_help.stderr)
        self.assertIn("--reviewable-path", begin_help.stdout)
        self.assertNotIn("--reviewable-path", finalizer_help.stdout)

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_begin_review_rejects_reviewable_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "public.pem").write_text("PUBLIC CERTIFICATE\n", encoding="utf-8")
            (repo / "public-link.pem").symlink_to("public.pem")
            public_directory = repo / "public-directory"
            public_directory.mkdir()
            (public_directory / "public.pem").write_text(
                "PUBLIC CERTIFICATE\n",
                encoding="utf-8",
            )
            (repo / "public-directory-link").symlink_to(
                public_directory.name,
                target_is_directory=True,
            )
            subprocess.run(
                [
                    "git",
                    "add",
                    "public.pem",
                    "public-link.pem",
                    "public-directory/public.pem",
                    "public-directory-link",
                ],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "commit", "-qm", "add public certificate link"], cwd=repo, check=True)
            cases = (
                (
                    "target",
                    "public-link.pem",
                    "reviewable path target file must not be a symlink: public-link.pem",
                ),
                (
                    "parent",
                    "public-directory-link/public.pem",
                    "reviewable path parent component must not be a symlink: "
                    "public-directory-link",
                ),
            )
            for name, reviewable_path, message in cases:
                with self.subTest(name=name):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(BEGIN_REVIEW),
                            "--repo",
                            str(repo),
                            "--task",
                            "review linked public material",
                            "--output",
                            str(root / f"symlink-review-{name}"),
                            "--path",
                            "app.py",
                            "--reviewable-path",
                            reviewable_path,
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn(message, completed.stderr)

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_sealed_reviewable_file_cannot_be_replaced_by_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            public_pem = repo / "public.pem"
            public_pem.write_text("PUBLIC CERTIFICATE\n", encoding="utf-8")
            subprocess.run(["git", "add", public_pem.name], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add public pem"], cwd=repo, check=True)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=[public_pem.name],
                reviewable_paths=[public_pem.name],
                name="reviewable-type-change",
            )
            public_pem.unlink()
            public_pem.symlink_to("app.py")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "type-change-run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must remain a regular file or be deleted", completed.stderr)

    def test_sealed_reviewable_exception_does_not_follow_a_rename(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            public_pem = repo / "public.pem"
            public_pem.write_text("PUBLIC CERTIFICATE\n", encoding="utf-8")
            subprocess.run(["git", "add", public_pem.name], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add public pem"], cwd=repo, check=True)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["public.pem", "renamed-public.pem"],
                reviewable_paths=["public.pem"],
                name="reviewable-rename",
            )
            public_pem.rename(repo / "renamed-public.pem")
            output = root / "rename-run"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="ascii"))
            self.assertEqual(
                summary["quality_status"],
                "REVIEW_REQUIRED_WITH_REDACTIONS",
            )
            self.assertTrue(summary["sensitive_change_quarantine"])
            self.assertNotIn(
                "PUBLIC CERTIFICATE",
                (output / "diff.patch").read_text(encoding="utf-8"),
            )

    def test_contract_seal_recovery_is_exact_idempotent_and_non_overwriting(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"

            intake = root / "intake-only-review"
            created = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "prepare recovery boundary",
                    "--output",
                    str(intake),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            nothing_to_recover = subprocess.run(
                [
                    sys.executable,
                    str(SEAL_CONTRACT),
                    "--review-dir",
                    str(intake),
                    "--recover",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(nothing_to_recover.returncode, 0)
            self.assertIn(
                "no interrupted contract publication",
                nothing_to_recover.stderr,
            )
            self.assertFalse((intake / "change-contract.json").exists())
            self.assertFalse((intake / "contract.seal.json").exists())

            self.prepare_governed_change(
                root,
                repo,
                command=command,
                name="recoverable",
            )
            review_dir = root / "recoverable-review"
            seal_path = review_dir / "contract.seal.json"
            expected_seal = seal_path.read_bytes()
            seal_path.unlink()
            recovered = subprocess.run(
                [
                    sys.executable,
                    str(SEAL_CONTRACT),
                    "--review-dir",
                    str(review_dir),
                    "--recover",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(seal_path.read_bytes(), expected_seal)
            repeated = subprocess.run(
                [
                    sys.executable,
                    str(SEAL_CONTRACT),
                    "--review-dir",
                    str(review_dir),
                    "--recover",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(seal_path.read_bytes(), expected_seal)

            self.prepare_governed_change(
                root,
                repo,
                command=command,
                name="mismatched-recovery",
            )
            mismatched = root / "mismatched-recovery-review"
            mismatched_seal = mismatched / "contract.seal.json"
            mismatched_seal.unlink()
            contract_path = mismatched / "change-contract.json"
            contract_path.write_bytes(contract_path.read_bytes() + b"\n")
            existing = contract_path.read_bytes()
            refused = subprocess.run(
                [
                    sys.executable,
                    str(SEAL_CONTRACT),
                    "--review-dir",
                    str(mismatched),
                    "--recover",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("does not match", refused.stderr)
            self.assertEqual(contract_path.read_bytes(), existing)
            self.assertFalse(mismatched_seal.exists())

    def test_review_directory_publication_never_replaces_an_empty_destination(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            source_identity = source.stat().st_ino
            destination_identity = destination.stat().st_ino
            with self.assertRaises(OSError):
                rename_directory_no_replace(source, destination)
            self.assertTrue(source.is_dir())
            self.assertEqual(source.stat().st_ino, source_identity)
            self.assertTrue(destination.is_dir())
            self.assertEqual(destination.stat().st_ino, destination_identity)

    def test_begin_review_requires_scope_cleanliness_and_cleans_failed_transaction(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            missing_scope = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "change product behavior",
                    "--output",
                    str(root / "missing-scope"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(missing_scope.returncode, 0)
            self.assertIn("at least one --path", missing_scope.stderr)
            (repo / "preexisting.txt").write_text("mine\n", encoding="utf-8")
            dirty = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "change product behavior",
                    "--output",
                    str(root / "dirty"),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(dirty.returncode, 0)
            self.assertIn("clean worktree and index", dirty.stderr)
            (repo / "preexisting.txt").unlink()
            output = root / "transaction"
            with mock.patch.object(
                begin_review_module,
                "write_new_json",
                side_effect=OSError("synthetic write failure"),
            ):
                with self.assertRaisesRegex(OSError, "synthetic write failure"):
                    begin_review_module.main(
                        [
                            "--repo",
                            str(repo),
                            "--task",
                            "change product behavior",
                            "--output",
                            str(output),
                            "--path",
                            "app.py",
                        ]
                    )
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".transaction.tmp-*")), [])

    def test_sealed_contract_rejects_missing_hash_or_post_seal_content_change(self) -> None:
        for mutation in ("missing-hash", "changed-content"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
                prefix="rootloom-change-", dir=Path.home()
            ) as temporary:
                root = Path(temporary)
                repo = self.make_repo(root)
                command = f"{sys.executable} -c 'assert True'"
                governed = self.prepare_governed_change(
                    root, repo, command=command, name=mutation
                )
                contract_path = Path(governed[5])
                contract = json.loads(contract_path.read_text(encoding="ascii"))
                if mutation == "missing-hash":
                    contract.pop("contract_sha256")
                else:
                    contract["allowed_paths"].append("docs/**")
                    contract["contract_sha256"] = self.contract_sha256(contract)
                contract_path.write_text(json.dumps(contract), encoding="ascii")
                (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--repo",
                        str(repo),
                        "--output",
                        str(root / "run"),
                        *governed,
                        "--strict",
                        "--verify",
                        command,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 1, completed.stderr)
                summary = json.loads((root / "run" / "summary.json").read_text())
                self.assertEqual(summary["quality_status"], "FAILED")
                self.assertFalse(summary["review_manifest"]["valid"])
                self.assertFalse(summary["passed"])

    def test_dirty_baseline_overlap_is_conservatively_attributed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["app.py"],
                name="dirty-overlap",
                allow_dirty_baseline=True,
            )
            (repo / "app.py").write_text("value = 3\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["change_partition"], "conservative-overlap")
            self.assertEqual(summary["changed_files"], ["app.py"])
            self.assertEqual(summary["task_changes"][0]["path"], "app.py")
            self.assertEqual(summary["quality_status"], "REVIEW_EVIDENCE_COMPLETE")

    def test_unchanged_untracked_dirty_baseline_does_not_contaminate_task_scope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "user.bin").write_bytes(b"\x00pre-existing-user-state")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["new.py"],
                name="dirty-untracked-separated",
                allow_dirty_baseline=True,
            )
            (repo / "new.py").write_text("created = True\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["change_partition"], "exact")
            self.assertEqual(summary["changed_files"], ["new.py"])
            self.assertEqual(
                [item["path"] for item in summary["task_changes"]],
                ["new.py"],
            )
            self.assertEqual(
                [item["path"] for item in summary["preexisting_changes"]],
                ["user.bin"],
            )
            self.assertEqual(summary["quality_status"], "REVIEW_EVIDENCE_COMPLETE")

    def test_unchanged_untracked_text_is_excluded_from_analysis_and_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            marker = "PREEXISTING_USER_AUTH_NOTE"
            (repo / "auth.py").write_text(marker + "\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="add a new Python constant",
                allowed_paths=["new.py"],
                name="dirty-untracked-text-separated",
                allow_dirty_baseline=True,
            )
            (repo / "new.py").write_text("created = True\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["change_partition"], "exact")
            self.assertEqual(summary["changed_files"], ["new.py"])
            self.assertNotIn(
                "authentication",
                {item["id"] for item in summary["risk_assessment"]["signals"]},
            )
            patch = (root / "run" / "diff.patch").read_bytes()
            self.assertIn(b"diff --git a/new.py b/new.py", patch)
            self.assertNotIn(b"diff --git a/auth.py b/auth.py", patch)
            self.assertNotIn(marker.encode("ascii"), patch)

    def test_changed_untracked_dirty_baseline_remains_conservatively_attributed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "notes.txt").write_text("before\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["new.py"],
                name="dirty-untracked-text-overlap",
                allow_dirty_baseline=True,
            )
            (repo / "notes.txt").write_text("after\n", encoding="utf-8")
            (repo / "new.py").write_text("created = True\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["change_partition"], "conservative-overlap")
            self.assertIn(
                "notes.txt",
                summary["change_contract"]["scope_violations"][
                    "outside_allowed_paths"
                ],
            )
            patch = (root / "run" / "diff.patch").read_bytes()
            self.assertIn(b"diff --git a/new.py b/new.py", patch)
            self.assertIn(b"diff --git a/notes.txt b/notes.txt", patch)
            self.assertIn(b"+after", patch)

    def test_dirty_baseline_overlap_cannot_hide_behind_a_new_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["new.py"],
                name="dirty-hidden-overlap",
                allow_dirty_baseline=True,
            )
            (repo / "app.py").write_text("value = 3\n", encoding="utf-8")
            (repo / "new.py").write_text("created = True\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["change_partition"], "conservative-overlap")
            self.assertIn(
                "app.py",
                summary["change_contract"]["scope_violations"][
                    "outside_allowed_paths"
                ],
            )
            self.assertEqual(summary["quality_status"], "FAILED")

    def test_removed_preexisting_dirty_path_cannot_be_reported_as_no_change(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["app.py"],
                name="dirty-removed",
                allow_dirty_baseline=True,
            )
            (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--allow-no-change",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(
                summary["change_partition"], "preexisting-state-removed"
            )
            self.assertEqual(summary["removed_preexisting_paths"], ["app.py"])
            self.assertEqual(summary["quality_status"], "FAILED")

    def test_analyzer_promotes_auth_source_and_explains_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            completed = self.analyze(
                repo,
                "--task",
                "Change login token validation",
                "--path",
                "src/auth/token.py",
                "--declared-risk",
                "low",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            assessment = json.loads(completed.stdout)
            self.assertEqual(assessment["effective_risk"], "high")
            self.assertEqual(assessment["minimum_tier"], 2)
            self.assertTrue(assessment["risk_was_raised"])
            signal_ids = {item["id"] for item in assessment["signals"]}
            self.assertIn("authentication", signal_ids)
            behavior_ids = {
                item["id"]
                for item in assessment["verification_plan"]["required_behaviors"]
            }
            self.assertIn("auth-boundaries", behavior_ids)
            self.assertEqual(
                assessment["verification_plan"]["status"],
                "suggested-not-executed",
            )

    def test_analyzer_treats_dependency_manifests_and_split_stems_as_product_risk(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            dependency = self.analyze(
                repo,
                "--task",
                "upgrade cryptography and fix authentication dependency",
                "--path",
                "requirements.txt",
            )
            self.assertEqual(dependency.returncode, 0, dependency.stderr)
            payload = json.loads(dependency.stdout)
            self.assertEqual(payload["minimum_tier"], 2)
            self.assertIn(
                "dependency-supply-chain", {item["id"] for item in payload["signals"]}
            )
            stemmed = self.analyze(repo, "--path", "src/auth_service.py")
            self.assertEqual(stemmed.returncode, 0, stemmed.stderr)
            self.assertIn(
                "authentication",
                {item["id"] for item in json.loads(stemmed.stdout)["signals"]},
            )

    def test_analyzer_can_classify_a_high_risk_task_before_paths_are_known(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            completed = self.analyze(repo, "--task", "新增数据库迁移并回填历史数据")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            assessment = json.loads(completed.stdout)
            self.assertEqual(assessment["detected_risk"], "high")
            self.assertEqual(assessment["minimum_tier"], 2)
            self.assertEqual(assessment["confidence"], "medium")
            behavior_ids = {
                item["id"]
                for item in assessment["verification_plan"]["required_behaviors"]
            }
            self.assertIn("primary-behavior", behavior_ids)
            self.assertIn("data-compatibility", behavior_ids)
            self.assertNotIn("documentation-contract", behavior_ids)

    def test_analyzer_reads_bounded_untracked_code_for_risk_signals(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            (repo / "worker module.py").write_text(
                "import argparse\nparser = argparse.ArgumentParser()\n",
                encoding="utf-8",
            )
            completed = self.analyze(repo, "--task", "add worker behavior")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            assessment = json.loads(completed.stdout)
            self.assertEqual(assessment["detected_risk"], "high")
            self.assertIn(
                "public-contract",
                {item["id"] for item in assessment["signals"]},
            )

    def test_analyzer_ignores_unchanged_diff_context_and_detects_workflows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            service = repo / "service.py"
            service.write_text("AUTHENTICATION_ENABLED = True\nvalue = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "service.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "service"], cwd=repo, check=True)
            service.write_text("AUTHENTICATION_ENABLED = True\nvalue = 2\n", encoding="utf-8")
            completed = self.analyze(repo)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            assessment = json.loads(completed.stdout)
            self.assertEqual(assessment["detected_risk"], "medium")
            self.assertNotIn(
                "authentication",
                {item["id"] for item in assessment["signals"]},
            )

            subprocess.run(["git", "restore", "service.py"], cwd=repo, check=True)
            workflow = self.analyze(repo, "--path", ".github/workflows/ci.yml")
            self.assertEqual(workflow.returncode, 0, workflow.stderr)
            workflow_assessment = json.loads(workflow.stdout)
            self.assertEqual(workflow_assessment["detected_risk"], "high")
            self.assertIn(
                "infrastructure",
                {item["id"] for item in workflow_assessment["signals"]},
            )

    def test_analyzer_does_not_treat_rule_strings_as_domain_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            rules = repo / "rules.py"
            rules.write_text("SIGNALS = set()\nTOKEN = None\n", encoding="utf-8")
            subprocess.run(["git", "add", "rules.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "rules"], cwd=repo, check=True)
            rules.write_text(
                (
                    'SIGNALS = {"auth", "money", "database", "lock", "state-machine"}\n'
                    'TOKEN = compile_pattern()\n'
                ),
                encoding="utf-8",
            )
            completed = self.analyze(repo)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            assessment = json.loads(completed.stdout)
            self.assertEqual(assessment["detected_risk"], "medium")
            self.assertEqual(
                {item["id"] for item in assessment["signals"]},
                {"behavioral-code"},
            )



    def test_core_evidence_does_not_read_project_memory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            memory = repo / ".project-memory"
            memory.mkdir()
            sentinel = "must-not-enter-core-evidence"
            (memory / "known-risks.json").write_text(
                json.dumps(
                    {
                        "format": "rootloom-project-memory-v1",
                        "kind": "risks",
                        "entries": [
                            {
                                "summary": sentinel,
                                "mitigation": "query the optional plugin explicitly",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            completed = self.analyze(repo, "--path", "src/relay.py")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn(sentinel, completed.stdout)
            assessment = json.loads(completed.stdout)
            self.assertEqual(
                assessment["memory"],
                {"matches": [], "stale": [], "warnings": []},
            )

            removed_flag = self.analyze(
                repo,
                "--path",
                "src/relay.py",
                "--include-project-memory",
            )
            self.assertNotEqual(removed_flag.returncode, 0)
            self.assertIn("unrecognized arguments", removed_flag.stderr)

            self.assertNotIn(
                "include_project_memory",
                inspect.signature(analyze_change_intelligence).parameters,
            )

    def test_repository_command_discovery_is_bounded_and_no_follow(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            makefile = root / "Makefile"
            makefile.write_text("check:\n\t@true\n", encoding="utf-8")
            self.assertIn(
                "check:",
                read_bounded_repository_text(
                    makefile, max_bytes=MAX_COMMAND_DISCOVERY_BYTES
                ),
            )
            makefile.write_bytes(b"x" * (MAX_COMMAND_DISCOVERY_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "exceeds"):
                read_bounded_repository_text(
                    makefile, max_bytes=MAX_COMMAND_DISCOVERY_BYTES
                )
            if os.name != "nt":
                makefile.unlink()
                makefile.symlink_to(root / "outside")
                with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                    read_bounded_repository_text(
                        makefile, max_bytes=MAX_COMMAND_DISCOVERY_BYTES
                    )






    def test_writes_compact_summary_and_verification_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert 2 == 2'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="bundle"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            output = root / "run"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    "--risk",
                    "low",
                    *governed,
                    "--max-git-seconds",
                    "7",
                    "--max-sensitive-paths",
                    "17",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["schema_revision"], 5)
            self.assertEqual(summary["quality_status"], "REVIEW_EVIDENCE_COMPLETE")
            self.assertTrue(summary["evidence_complete"])
            self.assertEqual(summary["verification_coverage"], "complete")
            self.assertEqual(summary["claim_binding"], "complete")
            self.assertEqual(summary["semantic_coverage"], "reviewed")
            self.assertEqual(summary["semantic_review"], "operator-asserted")
            self.assertEqual(summary["evidence_provenance"]["baseline"], "intake-sealed")
            self.assertEqual(
                summary["evidence_provenance"]["change_contract"], "workflow-sealed"
            )
            self.assertEqual(
                summary["evidence_provenance"]["verification_claims"],
                "workflow-sealed",
            )
            self.assertEqual(summary["evidence_provenance"]["semantic_review"], "operator-asserted")
            self.assertEqual(summary["sensitive_integrity"], "metadata-observed")
            self.assertEqual(
                summary["reviewability_policy"],
                {
                    "captured_files": [],
                    "captured_files_provenance": None,
                    "enabled": False,
                    "paths": [],
                    "policy_provenance": None,
                    "policy_sha256": None,
                    "source": None,
                },
            )
            self.assertTrue(summary["hash_chain"]["valid"])
            self.assertEqual(summary["process_convergence"], "complete")
            self.assertTrue(summary["detached_descendant_possible"])
            self.assertEqual(summary["isolation"], "process-group-only")
            self.assertTrue(summary["review_manifest"]["valid"])
            self.assertEqual(summary["exit_policy"], "bundle")
            self.assertEqual(summary["process_exit_code"], 0)
            self.assertEqual(
                summary["capture_limits"],
                {
                    "max_capture_seconds": 90.0,
                    "max_git_seconds": 7.0,
                    "max_patch_bytes": 16 * 1024 * 1024,
                    "max_sensitive_paths": 17,
                },
            )
            self.assertGreaterEqual(summary["capture_duration_seconds"], 0.0)
            self.assertEqual(summary["changed_files"], ["app.py"])
            self.assertEqual(summary["risk"], "medium")
            self.assertTrue(summary["risk_assessment"]["risk_was_raised"])
            self.assertEqual(
                summary["verification_plan"]["status"],
                "suggested-not-executed",
            )
            self.assertIn(b"value = 2", (output / "diff.patch").read_bytes())
            self.assertIn("assert 2 == 2", (output / "test.log").read_text(encoding="utf-8"))

    def test_unrelated_passing_command_is_partial_not_verified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert 2 == 2'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                claims=("primary",),
                name="partial",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["commands_passed"])
            self.assertTrue(summary["capture_preserved"])
            self.assertEqual(summary["claim_binding"], "partial")
            self.assertEqual(summary["verification_coverage"], "partial")
            self.assertEqual(summary["quality_status"], "COMMANDS_PASSED")
            self.assertFalse(summary["passed"])

    def test_strict_bundle_only_is_explicitly_nonblocking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                claims=("primary",),
                name="strict-bundle",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--strict-bundle-only",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "COMMANDS_PASSED")
            self.assertEqual(summary["exit_policy"], "bundle")

    def test_semantic_unknown_caps_sealed_evidence_at_mechanical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="mechanical-cap"
            )
            governed = governed[:-2]
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["claim_binding"], "complete")
            self.assertEqual(summary["semantic_coverage"], "unknown")
            self.assertEqual(summary["quality_status"], "MECHANICALLY_VERIFIED")
            self.assertFalse(summary["passed"])

    def test_semantic_review_without_a_sealed_chain_is_assertion_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                name="semantic-assertion",
            )
            (root / "semantic-assertion-review" / "contract.seal.json").unlink()
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "SEMANTIC_REVIEW_ASSERTED")
            self.assertEqual(summary["semantic_review"], "operator-asserted")
            self.assertFalse(summary["passed"])
            self.assertFalse(summary["review_manifest"]["valid"])

    def test_cli_claims_cannot_promote_a_partial_sealed_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                claims=("primary",),
                name="cli-claims",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            cli_claims = [
                part
                for claim in self.ALL_CLAIM_IDS
                if claim != "primary-behavior"
                for part in ("--verify-claim", f"{claim}:{command}")
            ]
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                    *cli_claims,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["declared_claim_binding"], "complete")
            self.assertEqual(summary["claim_binding"], "partial")
            self.assertEqual(summary["quality_status"], "COMMANDS_PASSED")

    def test_advisory_finalizer_does_not_block_without_governed_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert 2 == 2'"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--task",
                    "change product behavior",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["mode"], "advisory")
            self.assertTrue(summary["commands_passed"])
            self.assertEqual(summary["verification_coverage"], "unverified")
            self.assertEqual(summary["quality_status"], "UNVERIFIED")
            self.assertEqual(summary["claim_binding"], "unverified")
            self.assertFalse(summary["baseline"]["required"])
            self.assertFalse(summary["baseline"]["provided"])
            self.assertFalse(summary["change_contract"]["required"])
            self.assertFalse(summary["passed"])

    def test_require_verified_returns_quality_exit_for_unverified_advisory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--task",
                    "change product behavior",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                    "--require-verified",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["exit_policy"], "quality")
            self.assertEqual(summary["process_exit_code"], 4)
            self.assertEqual(summary["quality_status"], "UNVERIFIED")

    def test_quality_exit_policy_distinguishes_no_change(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--allow-no-change",
                    "--exit-policy",
                    "quality",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 3, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "NO_CHANGE")
            self.assertEqual(summary["process_exit_code"], 3)

    def test_simple_string_claims_cannot_complete_strict_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            baseline = root / "baseline.json"
            analyzed = self.analyze(repo, "--task", "change product behavior", "--write-baseline", str(baseline))
            self.assertEqual(analyzed.returncode, 0, analyzed.stderr)
            contract = root / "contract.json"
            command = f"{sys.executable} -c 'assert True'"
            baseline_payload = json.loads(baseline.read_text(encoding="ascii"))
            payload = {
                "format": "rootloom-change-contract-v1",
                "run_id": baseline_payload["run_id"],
                "nonce": baseline_payload["nonce"],
                "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
                "task_sha256": baseline_payload["task_sha256"],
                "allowed_paths": ["**"],
                "forbidden_paths": [],
                "root_cause_alignment": "PASS",
                "verification_commands": {"verify-1": command},
                "verification_claims": {
                    claim: ["verify-1"] for claim in self.ALL_CLAIM_IDS
                },
            }
            payload["contract_sha256"] = self.contract_sha256(payload)
            contract.write_text(json.dumps(payload), encoding="utf-8")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--task",
                    "change product behavior",
                    "--baseline",
                    str(baseline),
                    "--change-contract",
                    str(contract),
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "UNVERIFIED")
            self.assertEqual(summary["declared_claim_binding"], "complete")
            self.assertEqual(summary["claim_binding"], "unverified")
            self.assertFalse(summary["passed"])
            self.assertEqual(summary["evidence_provenance"]["baseline"], "self-declared")
            self.assertEqual(summary["evidence_provenance"]["change_contract"], "self-declared")
            self.assertFalse(summary["review_manifest"]["valid"])

    def test_symlinked_baseline_is_rejected_before_hashing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            target = root / "target-baseline.json"
            target.write_text("{}", encoding="ascii")
            baseline = root / "baseline-link.json"
            try:
                baseline.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--task",
                    "change product behavior",
                    "--strict",
                    "--baseline",
                    str(baseline),
                    "--change-contract",
                    str(root / "missing-contract.json"),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("baseline path must not traverse a symlink", completed.stderr)
            self.assertFalse((root / "run" / "summary.json").exists())

    def test_structured_claim_binding_requires_target_in_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            baseline = root / "baseline.json"
            analyzed = self.analyze(repo, "--task", "change product behavior", "--write-baseline", str(baseline))
            self.assertEqual(analyzed.returncode, 0, analyzed.stderr)
            baseline_payload = json.loads(baseline.read_text(encoding="ascii"))
            payload = {
                "format": "rootloom-change-contract-v1",
                "run_id": baseline_payload["run_id"],
                "nonce": baseline_payload["nonce"],
                "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
                "task_sha256": baseline_payload["task_sha256"],
                "allowed_paths": ["**"],
                "forbidden_paths": [],
                "root_cause_alignment": "PASS",
                "verification_commands": {
                    "verify-1": f"{sys.executable} -m unittest tests.test_engineering_change"
                },
                "verification_claims": {
                    "primary": [
                        {
                            "id": "primary-behavior",
                            "command_ids": ["verify-1"],
                            "target": "tests/test_missing.py::test_missing",
                            "expected_evidence": "targeted regression executes",
                            "evidence_kind": "regression-test",
                        }
                    ]
                },
            }
            payload["contract_sha256"] = self.contract_sha256(payload)
            contract = root / "contract.json"
            contract.write_text(json.dumps(payload), encoding="utf-8")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--task",
                    "change product behavior",
                    "--baseline",
                    str(baseline),
                    "--change-contract",
                    str(contract),
                    "--verify",
                    payload["verification_commands"]["verify-1"],
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("target is not present", completed.stderr)

    def test_repository_globs_are_segment_aware(self) -> None:
        self.assertTrue(path_matches("src/auth/user.py", "src/auth/*"))
        self.assertFalse(path_matches("src/auth/internal/token.py", "src/auth/*"))
        self.assertTrue(path_matches("src/auth/internal/token.py", "src/auth/**"))
        self.assertFalse(path_matches("src/auth/internal/token.py", "src/auth/*.py"))
        self.assertTrue(
            path_matches("src/auth/internal/token.py", "src/auth/**/token.py")
        )
        self.assertTrue(path_matches("src/auth/token.py", "src/auth/**/token.py"))
        self.assertTrue(path_matches("src/a.py", "src/?.py"))
        self.assertFalse(path_matches("src/ab.py", "src/?.py"))
        self.assertTrue(path_matches("src/auth/[ab].py", "src/auth/[ab].py"))
        self.assertFalse(path_matches("src/auth/a.py", "src/auth/[ab].py"))
        self.assertTrue(path_matches("src/auth/token.py", "**/token.py"))
        self.assertTrue(path_matches("token.py", "**/token.py"))
        self.assertFalse(path_matches("src/auth/token.txt", "**/token.py"))

    def test_legacy_baseline_remains_readable_but_cannot_be_sealed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            review_dir = root / "legacy-review"
            begun = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "change product behavior",
                    "--output",
                    str(review_dir),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(begun.returncode, 0, begun.stderr)
            baseline_path = review_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="ascii"))
            baseline["format"] = "rootloom-change-baseline-v1"
            baseline_path.write_text(json.dumps(baseline), encoding="ascii")
            loaded, _digest = read_baseline_payload_with_hash(baseline_path)
            self.assertEqual(loaded["format"], "rootloom-change-baseline-v1")
            sealed = subprocess.run(
                [sys.executable, str(SEAL_CONTRACT), "--review-dir", str(review_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(sealed.returncode, 0)
            self.assertIn("intake-sealed baseline v3", sealed.stderr)
            self.assertFalse((review_dir / "change-contract.json").exists())
            self.assertFalse((review_dir / "contract.seal.json").exists())

    def test_legacy_sealed_v2_intake_remains_usable_and_normalizes_provenance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            review_dir = root / "legacy-v2-review"
            task = "change product behavior"
            begun = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    task,
                    "--output",
                    str(review_dir),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(begun.returncode, 0, begun.stderr)

            baseline_path = review_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="ascii"))
            baseline["format"] = "rootloom-change-baseline-v2"
            baseline["evidence_provenance"] = "operator-sealed"
            baseline_path.write_text(
                json.dumps(baseline, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
                encoding="ascii",
            )
            baseline_sha256 = hashlib.sha256(baseline_path.read_bytes()).hexdigest()

            manifest_path = review_dir / "review.json"
            manifest = json.loads(manifest_path.read_text(encoding="ascii"))
            manifest["baseline_sha256"] = baseline_sha256
            manifest_path.write_text(json.dumps(manifest), encoding="ascii")

            command = f"{sys.executable} -c 'assert True'"
            draft_path = review_dir / "change-contract.draft.json"
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            draft["baseline_sha256"] = baseline_sha256
            draft["root_cause_alignment"] = "PASS"
            draft["verification_commands"] = {"verify-1": command}
            draft["verification_claims"] = {
                claim: [
                    {
                        "id": claim,
                        "command_ids": ["verify-1"],
                        "target": sys.executable,
                        "expected_evidence": f"{claim} remains compatible",
                        "evidence_kind": "regression-test",
                    }
                ]
                for claim in self.ALL_CLAIM_IDS
            }
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            sealed = subprocess.run(
                [sys.executable, str(SEAL_CONTRACT), "--review-dir", str(review_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(sealed.returncode, 0, sealed.stderr)

            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            output = root / "legacy-v2-run"
            finalized = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    "--task",
                    task,
                    "--baseline",
                    str(baseline_path),
                    "--change-contract",
                    str(review_dir / "change-contract.json"),
                    "--strict",
                    "--semantic-coverage",
                    "reviewed",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="ascii"))
            self.assertTrue(summary["evidence_complete"])
            self.assertEqual(summary["evidence_provenance"]["baseline"], "intake-sealed")
            self.assertEqual(
                summary["evidence_provenance"]["change_contract"],
                "workflow-sealed",
            )

    def test_contract_rejects_duplicate_claim_aliases(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            contract = Path(temporary) / "contract.json"
            command = f"{sys.executable} -c 'assert True'"
            payload = {
                "format": "rootloom-change-contract-v1",
                "allowed_paths": ["**"],
                "forbidden_paths": [],
                "root_cause_alignment": "PASS",
                "verification_commands": {"verify-1": command},
                "verification_claims": {
                    "primary": ["verify-1"],
                    "primary-behavior": ["verify-1"],
                },
            }
            payload["contract_sha256"] = self.contract_sha256(payload)
            contract.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate alias"):
                load_change_contract(contract)

    def test_strict_finalizer_requires_governed_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--task",
                    "change product behavior",
                    "--strict",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("requires --baseline", completed.stderr)
            self.assertFalse((root / "run" / "summary.json").exists())

    def test_strict_finalizer_binds_baseline_head_ref_and_index(self) -> None:
        for movement in ("index", "head", "head_ref"):
            with self.subTest(movement=movement), tempfile.TemporaryDirectory(
                prefix="rootloom-change-", dir=Path.home()
            ) as temporary:
                root = Path(temporary)
                repo = self.make_repo(root)
                command = f"{sys.executable} -c 'assert True'"
                governed = self.prepare_governed_change(
                    root, repo, command=command, name=f"base-{movement}"
                )
                if movement == "head":
                    (repo / "base.txt").write_text("new base\n", encoding="utf-8")
                    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
                    subprocess.run(["git", "commit", "-qm", "move base"], cwd=repo, check=True)
                elif movement == "head_ref":
                    subprocess.run(
                        ["git", "checkout", "-qb", "alternate"], cwd=repo, check=True
                    )
                (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
                if movement == "index":
                    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--repo",
                        str(repo),
                        "--output",
                        str(root / "run"),
                        *governed,
                        "--strict",
                        "--verify",
                        command,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 1, completed.stderr)
                summary = json.loads((root / "run" / "summary.json").read_text())
                self.assertEqual(summary["quality_status"], "FAILED")
                self.assertFalse(summary["baseline"]["repository_base_stable"])
                errors = summary["hash_chain"]["errors"]
                expected = "head ref" if movement == "head_ref" else movement
                self.assertTrue(
                    any(f"repository {expected} changed" in item.lower() for item in errors),
                    errors,
                )

    def test_verification_cannot_move_head_with_an_identical_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = "git commit --allow-empty -qm verification-base-drift"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="verification-base-drift"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["capture_preserved"])
            self.assertFalse(
                summary["repository_base_preserved_during_verification"]
            )
            self.assertEqual(summary["quality_status"], "FAILED")
            self.assertIn(
                "repository HEAD changed during verification",
                summary["post_execution_errors"],
            )

    def test_verification_cannot_mutate_sealed_evidence_after_preflight(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            seal_path = root / "evidence-drift-review" / "contract.seal.json"
            seal_path_hex = str(seal_path).encode("utf-8").hex()
            command = (
                f"{sys.executable} -c "
                "'p=__import__(\"pathlib\").Path("
                f"bytes.fromhex(\"{seal_path_hex}\").decode());"
                "p.write_bytes(p.read_bytes()+b\" \")'"
            )
            governed = self.prepare_governed_change(
                root, repo, command=command, name="evidence-drift"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["capture_preserved"])
            self.assertFalse(summary["evidence_files_preserved"])
            self.assertEqual(summary["quality_status"], "FAILED")
            self.assertIn(
                "contract seal bytes changed during verification",
                summary["evidence_preservation_errors"],
            )

    def test_operator_evidence_must_remain_outside_the_repository(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="inside-evidence"
            )
            review_dir = Path(governed[3]).parent
            inside_review = repo / "review"
            review_dir.rename(inside_review)
            governed[3] = str(inside_review / "baseline.json")
            governed[5] = str(inside_review / "change-contract.json")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must be outside the repository", completed.stderr)
            self.assertFalse((root / "run").exists())

    def test_invalid_evidence_beats_no_change_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="no-change-invalid"
            )
            contract_path = Path(governed[5])
            contract = json.loads(contract_path.read_text(encoding="ascii"))
            contract.pop("contract_sha256")
            contract_path.write_text(json.dumps(contract), encoding="ascii")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--allow-no-change",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "FAILED")

    def test_review_manifest_requires_exact_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="manifest-schema"
            )
            review_dir = Path(governed[3]).parent
            manifest_path = review_dir / "review.json"
            manifest = json.loads(manifest_path.read_text(encoding="ascii"))
            manifest["unexpected"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="ascii")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "FAILED")
            self.assertIn("unexpected or missing fields", summary["review_manifest"]["errors"][0])

    def test_review_manifest_byte_drift_invalidates_contract_seal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="manifest-byte-drift"
            )
            review_dir = Path(governed[3]).parent
            manifest_path = review_dir / "review.json"
            manifest = json.loads(manifest_path.read_text(encoding="ascii"))
            manifest["next_step"] = "A different but still schema-valid instruction."
            manifest_path.write_text(json.dumps(manifest), encoding="ascii")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "FAILED")
            self.assertIn(
                "review_manifest_sha256 does not match",
                summary["review_manifest"]["errors"][0],
            )

    def test_contract_seal_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="duplicate-seal-key"
            )
            review_dir = Path(governed[3]).parent
            seal_path = review_dir / "contract.seal.json"
            seal_raw = seal_path.read_text(encoding="ascii")
            seal_path.write_text(
                seal_raw.replace(
                    "{\n",
                    '{\n  "format": "rootloom-contract-seal-v1",\n',
                    1,
                ),
                encoding="ascii",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "FAILED")
            self.assertIn(
                "duplicate JSON key: format",
                summary["review_manifest"]["errors"][0],
            )

    def test_evidence_json_rejects_duplicate_object_keys(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            baseline_path = root / "baseline.json"
            analyzed = self.analyze(repo, "--write-baseline", str(baseline_path))
            self.assertEqual(analyzed.returncode, 0, analyzed.stderr)
            baseline_raw = baseline_path.read_text(encoding="ascii")
            baseline_path.write_text(
                baseline_raw.replace(
                    "{\n",
                    '{\n  "format": "rootloom-change-baseline-v2",\n',
                    1,
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key: format"):
                read_baseline_payload_with_hash(baseline_path)

            contract_path = root / "contract.json"
            contract_path.write_text(
                '{"format":"rootloom-change-contract-v1",'
                '"format":"rootloom-change-contract-v1"}',
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key: format"):
                load_change_contract(contract_path)
            with self.assertRaisesRegex(ValueError, "out-of-range JSON number"):
                parse_json_object(
                    b'{"value": 1e999}',
                    label="evidence",
                    encoding="ascii",
                )

    def test_baseline_schema_rejects_future_and_malformed_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            source = root / "baseline.json"
            analyzed = self.analyze(repo, "--write-baseline", str(source))
            self.assertEqual(analyzed.returncode, 0, analyzed.stderr)
            original = json.loads(source.read_text(encoding="ascii"))
            mutations = {
                "run_id": "not-a-uuid",
                "nonce": "ABC",
                "task_sha256": "0" * 63,
                "created_at": (
                    datetime.now(UTC) + timedelta(hours=1)
                ).isoformat().replace("+00:00", "Z"),
            }
            for field, value in mutations.items():
                with self.subTest(field=field):
                    target = root / f"baseline-{field}.json"
                    payload = dict(original)
                    payload[field] = value
                    target.write_text(json.dumps(payload), encoding="ascii")
                    with self.assertRaises(ValueError):
                        read_baseline_payload_with_hash(target)
            nested_mutations = []
            unexpected_snapshot = json.loads(json.dumps(original))
            unexpected_snapshot["snapshot"]["unexpected"] = True
            nested_mutations.append(("snapshot-fields", unexpected_snapshot))
            unsafe_path = json.loads(json.dumps(original))
            unsafe_path["snapshot"]["changes"] = [
                {"status": " M", "path": "../escape.py", "original_path": ""}
            ]
            unsafe_path["preexisting_changes"] = list(
                unsafe_path["snapshot"]["changes"]
            )
            unsafe_path["allow_dirty_baseline"] = True
            nested_mutations.append(("unsafe-path", unsafe_path))
            bad_policy = json.loads(json.dumps(original))
            bad_policy["sensitive_policy_sha256"] = "0" * 64
            nested_mutations.append(("sensitive-policy", bad_policy))
            clean_with_patch = json.loads(json.dumps(original))
            clean_with_patch["tracked_patch_sha256"] = "1" * 64
            nested_mutations.append(("clean-with-patch", clean_with_patch))
            missing_ref = json.loads(json.dumps(original))
            missing_ref["git"].pop("head_ref")
            nested_mutations.append(("missing-head-ref", missing_ref))
            empty_index = json.loads(json.dumps(original))
            empty_index["git"]["index_sha256"] = ""
            nested_mutations.append(("empty-index", empty_index))
            for name, payload in nested_mutations:
                with self.subTest(name=name):
                    target = root / f"baseline-{name}.json"
                    target.write_text(json.dumps(payload), encoding="ascii")
                    with self.assertRaises(ValueError):
                        read_baseline_payload_with_hash(target)
            negative_age = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "negative-age"),
                    "--max-baseline-age-seconds",
                    "-1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(negative_age.returncode, 0)
            self.assertIn("must be nonnegative", negative_age.stderr)

    def test_untracked_content_rewrite_changes_capture_and_patch_contains_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = (
                f"{sys.executable} -c "
                "'__import__(\"pathlib\").Path(\"new_service.py\").write_text(\"value = \\\"B\\\"\\n\")'"
            )
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["new_service.py"],
                name="untracked-rewrite",
            )
            (repo / "new_service.py").write_text('value = "A"\n', encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertFalse(summary["capture_preserved"])
            self.assertEqual(summary["quality_status"], "FAILED")
            fingerprint = summary["repository_capture"]["untracked"][0]
            self.assertEqual(fingerprint["kind"], "file")
            self.assertEqual(len(fingerprint["sha256"]), 64)
            self.assertIn(b'value = "B"', (root / "run" / "diff.patch").read_bytes())

    def test_sensitive_discovery_targets_policy_matches_before_applying_path_budget(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            ordinary = repo / "ordinary"
            ordinary.mkdir()
            for index in range(12):
                (ordinary / f"file-{index}.txt").write_text(
                    "ordinary\n", encoding="utf-8"
                )
            (repo / ".ENV").write_text("TOKEN=synthetic\n", encoding="utf-8")
            (repo / "tokenizer-one.py").write_text("ordinary\n", encoding="utf-8")
            (repo / "tokenizer-two.py").write_text("ordinary\n", encoding="utf-8")
            (repo / ".gitignore").write_text("cache/\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "policy discovery"], cwd=repo, check=True)
            cache = repo / "cache"
            cache.mkdir()
            for index in range(12):
                (cache / f"ordinary-{index}.txt").write_text(
                    "ignored ordinary\n", encoding="utf-8"
                )

            self.assertEqual(
                discover_sensitive_paths(
                    repo,
                    set(),
                    max_sensitive_paths=1,
                ),
                [".ENV"],
            )

            with self.assertRaisesRegex(ValueError, "1-path budget"):
                discover_sensitive_paths(
                    repo,
                    set(),
                    max_sensitive_paths=10,
                    max_candidate_paths=1,
                )

            nested = repo / "nested"
            nested.mkdir()
            (nested / "secret.txt").write_text("synthetic\n", encoding="utf-8")
            subprocess.run(["git", "add", "nested/secret.txt"], cwd=repo, check=True)
            with self.assertRaisesRegex(ValueError, "1-path budget"):
                discover_sensitive_paths(
                    repo,
                    set(),
                    max_sensitive_paths=1,
                )

    def test_ignored_sensitive_baseline_is_metadata_only_and_guards_deletion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            secret = repo / ".env"
            secret.write_text("SECRET_VALUE=never-read\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="ignored-secret"
            )
            baseline_path = root / "ignored-secret-review" / "baseline.json"
            baseline = json.loads(baseline_path.read_text())
            metadata = next(
                item
                for item in baseline["snapshot"]["sensitive_paths"]
                if item["path"] == ".env"
            )
            self.assertFalse(metadata["content_read"])
            self.assertNotIn("sha256", metadata)
            self.assertNotIn("never-read", baseline_path.read_text())
            secret.unlink()
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 10, completed.stderr)
            self.assertIn(".env", completed.stdout)

    def test_ignored_file_below_secret_like_directory_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text("private-secrets/\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore secrets"], cwd=repo, check=True)
            secrets = repo / "private-secrets"
            secrets.mkdir()
            (secrets / "runtime.json").write_text(
                '{"value":"never-read-nested-secret"}\n', encoding="utf-8"
            )
            baseline = root / "nested-secret-baseline.json"
            completed = self.analyze(repo, "--write-baseline", str(baseline))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(baseline.read_text())
            metadata = next(
                item
                for item in payload["snapshot"]["sensitive_paths"]
                if item["path"] == "private-secrets/runtime.json"
            )
            self.assertFalse(metadata["content_read"])
            self.assertNotIn("sha256", metadata)
            self.assertNotIn("never-read-nested-secret", baseline.read_text())

    def test_ignored_uppercase_secret_and_declared_directory_boundary_are_safe(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(
                ".ENV\nprivate-config/\nprivate-backup/\n", encoding="utf-8"
            )
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore private files"], cwd=repo, check=True)
            (repo / ".ENV").write_text("TOKEN=uppercase-secret\n", encoding="utf-8")
            private = repo / "private-config"
            private.mkdir()
            (private / "nested.txt").write_text("declared-secret\n", encoding="utf-8")
            backup = repo / "private-backup"
            backup.mkdir()
            (backup / "nested.txt").write_text("not-declared\n", encoding="utf-8")
            baseline = root / "case-sensitive-baseline.json"
            completed = self.analyze(
                repo,
                "--sensitive-path",
                "private-config",
                "--write-baseline",
                str(baseline),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(baseline.read_text())
            paths = {item["path"] for item in payload["snapshot"]["sensitive_paths"]}
            self.assertIn(".ENV", paths)
            self.assertIn("private-config/nested.txt", paths)
            self.assertNotIn("private-backup/nested.txt", paths)
            serialized = baseline.read_text()
            self.assertNotIn("uppercase-secret", serialized)
            self.assertNotIn("declared-secret", serialized)

    def test_new_ignored_sensitive_path_is_a_scoped_task_change(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["app.py"],
                name="new-ignored-sensitive",
            )
            synthetic = "ignored-addition-synthetic-value"
            (repo / ".env").write_text(f"TOKEN={synthetic}\n", encoding="utf-8")
            (repo / "leaked.txt").write_text(
                f"TOKEN={synthetic}\n", encoding="utf-8"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "FAILED")
            self.assertIn(".env", summary["baseline_sensitive_preservation"]["added"])
            self.assertIn(
                ".env",
                summary["change_contract"]["scope_violations"][
                    "outside_allowed_paths"
                ],
            )
            self.assertIn(".env", {item["path"] for item in summary["task_changes"]})
            self.assertTrue(summary["sensitive_change_quarantine"])
            patch = (root / "run" / "diff.patch").read_text()
            self.assertNotIn(synthetic, patch)
            leaked = next(
                item
                for item in summary["repository_capture"]["untracked"]
                if item["path"] == "leaked.txt"
            )
            self.assertTrue(leaked["sensitive"])
            self.assertFalse(leaked["content_read"])

    def test_unchanged_ignored_sensitive_reference_does_not_quarantine(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            (repo / ".env").write_text("TOKEN=unchanged-synthetic\n", encoding="utf-8")
            baseline, _patch = repository_snapshot(repo)

            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            current, _patch = repository_snapshot(
                repo,
                reference_sensitive_metadata=baseline["sensitive_paths"],
            )

            self.assertFalse(current["bounds"]["sensitive_change_quarantine"])
            metadata = next(
                item for item in current["sensitive_paths"] if item["path"] == ".env"
            )
            self.assertFalse(metadata["content_read"])

    def test_verification_new_ignored_sensitive_path_quarantines_before_recapture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            synthetic = "verification-ignored-addition-synthetic-value"
            command = (
                f"{sys.executable} -c "
                "'from pathlib import Path; "
                f'Path(".env").write_text("TOKEN={synthetic}\\n"); '
                f'Path("leaked.txt").write_text("TOKEN={synthetic}\\n")'
                "'"
            )
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["app.py", ".env", "leaked.txt"],
                name="verification-new-ignored-sensitive",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["verification_sensitive_change_quarantine"])
            self.assertFalse(summary["capture_preserved"])
            patch = (root / "run" / "diff.patch").read_text(encoding="utf-8")
            self.assertNotIn(synthetic, patch)
            leaked = next(
                item
                for item in summary["repository_capture"]["untracked"]
                if item["path"] == "leaked.txt"
            )
            self.assertTrue(leaked["sensitive"])
            self.assertFalse(leaked["content_read"])

    def test_strict_cannot_add_sensitive_policy_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="late-sensitive-policy"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--sensitive-path",
                    "app.py",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must be declared in the baseline intake", completed.stderr)
            self.assertFalse((root / "run").exists())

    def test_sensitive_directory_and_symlink_are_metadata_only_recursively(self) -> None:
        if os.name == "nt":
            self.skipTest("symlink creation is not portable on Windows CI")
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            private = repo / "private-config"
            private.mkdir()
            (private / "nested.txt").write_text("never capture this text", encoding="utf-8")
            (repo / "credential-link").symlink_to(
                "private-config", target_is_directory=True
            )
            subprocess.run(
                ["git", "add", "private-config/nested.txt", "credential-link"],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "commit", "-qm", "private inputs"], cwd=repo, check=True)
            baseline = root / "metadata-baseline.json"
            completed = self.analyze(
                repo,
                "--sensitive-path",
                "private-config",
                "--sensitive-path",
                "credential-link",
                "--write-baseline",
                str(baseline),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(baseline.read_text())
            metadata = {
                item["path"]: item for item in payload["snapshot"]["sensitive_paths"]
            }
            self.assertEqual(metadata["private-config"]["kind"], "directory")
            self.assertEqual(metadata["private-config/nested.txt"]["kind"], "file")
            self.assertFalse(metadata["private-config/nested.txt"]["content_read"])
            self.assertEqual(metadata["credential-link"]["kind"], "symlink")
            self.assertEqual(
                metadata["credential-link"]["target_sha256"],
                hashlib.sha256(b"private-config").hexdigest(),
            )
            self.assertEqual(metadata["credential-link"]["target_bytes"], 14)
            self.assertNotIn("target", metadata["credential-link"])
            self.assertNotIn("never capture this text", baseline.read_text())

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_sensitive_capture_never_traverses_a_symlink_parent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            outside = root / "outside"
            outside.mkdir()
            (outside / "value.txt").write_text("outside-value\n", encoding="utf-8")
            (repo / "redirect").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink parent"):
                repository_snapshot(
                    repo,
                    extra_sensitive=["redirect/value.txt"],
                )

    def test_builtin_sensitive_directory_names_protect_all_descendants(self) -> None:
        for path in (
            ".env/config",
            ".env.production/config",
            ".netrc/config",
            "certificates.key/config",
            "nested/id_rsa/config",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_sensitive_material_path(path))
        self.assertFalse(is_sensitive_material_path("environment/config"))
        self.assertTrue(is_protected_deletion_path("state.sqlite"))
        self.assertTrue(is_protected_deletion_path("state.sqlite3"))

    def test_environment_material_classifier_uses_exact_boundaries(self) -> None:
        material = (
            ".env",
            ".envrc",
            ".env.local",
            ".env.production",
            ".ENV.PRODUCTION",
            "config/.env.staging",
            ".env.production/config",
        )
        for path in material:
            with self.subTest(material=path):
                self.assertTrue(is_sensitive_material_path(path))
                self.assertTrue(is_security_domain_path(path))

        templates = (
            ".env.example",
            ".env.sample",
            ".env.template",
            ".env.dist",
            ".ENV.EXAMPLE",
            "config/.env.example",
        )
        for path in templates:
            with self.subTest(template=path):
                self.assertFalse(is_sensitive_material_path(path))
                self.assertTrue(is_security_domain_path(path))
                self.assertFalse(is_protected_deletion_path(path))

        ordinary = (".environment", ".ENVIRONMENT", ".envelope", ".envoy")
        for path in ordinary:
            with self.subTest(ordinary=path):
                self.assertFalse(is_sensitive_material_path(path))
                self.assertFalse(is_security_domain_path(path))
                self.assertFalse(is_protected_deletion_path(path))

    def test_public_certificates_are_reviewable_but_strong_key_formats_are_not(self) -> None:
        public_certificates = (
            "certs/public-root.crt",
            "certificates/public-chain.cer",
            "trust/chain.p7b",
            "trust/chain.p7c",
            "trust/PUBLIC-ROOT.CRT",
        )
        for path in public_certificates:
            with self.subTest(public=path):
                self.assertFalse(is_sensitive_material_path(path))
                self.assertTrue(is_security_domain_path(path))
                self.assertFalse(is_protected_deletion_path(path))

        strong_material = (
            "keys/private.key",
            "keys/identity.p12",
            "keys/identity.pfx",
            "deploy/app.jks",
            "deploy/app.keystore",
            "ssh/identity.ppk",
            ".env.production",
            "trust/client-secret.crt",
            "trust/clientSecret.crt",
            "trust/private-key.cer",
            "trust/privateKey.cer",
            "trust/bundle.der",
            "trust/key.der",
            "trust/server.der",
            "trust/identity.der",
            "keys/key.pem",
            "keys/server-key.pem",
            "keys/client-key.pem",
            "keys/host-key.pem",
            "keys/ssh-key.pem",
            "keys/identity-key.pem",
            "keys/privkey.pem",
            "keys/privatekey.pem",
            "keys/rsa-key.pem",
            "keys/ec-key.pem",
            "keys/ecdsa-key.pem",
            "keys/ed25519-key.pem",
            "keys/encryption-key.pem",
            "keys/decryption-key.pem",
        )
        for path in strong_material:
            with self.subTest(strong=path):
                self.assertTrue(is_sensitive_material_path(path))
                self.assertTrue(is_security_domain_path(path))
                self.assertTrue(is_protected_deletion_path(path))

        self.assertTrue(is_sensitive_material_path("certs/public-chain.pem"))
        self.assertTrue(is_security_domain_path("certs/public-chain.pem"))
        for reviewable_ambiguous in (
            "certs/public.pem",
            "certs/certificate.pem",
            "certs/ca-chain.pem",
            "certs/trust-bundle.pem",
            "certs/public.der",
        ):
            with self.subTest(reviewable_ambiguous=reviewable_ambiguous):
                self.assertTrue(is_sensitive_material_path(reviewable_ambiguous))
                self.assertFalse(
                    is_sensitive_material_path(
                        reviewable_ambiguous,
                        reviewable_paths={reviewable_ambiguous},
                    )
                )

    def test_reviewable_security_artifacts_stay_in_patch_and_raise_risk(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            certs = repo / "certs"
            certs.mkdir()
            env_template = repo / ".env.example"
            certificate = certs / "public-root.crt"
            env_template.write_text("API_URL=https://example.invalid/v1\n", encoding="utf-8")
            certificate.write_text("PUBLIC CERTIFICATE V1\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", ".env.example", "certs/public-root.crt"],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "commit", "-qm", "add public security artifacts"], cwd=repo, check=True)
            env_template.write_text("API_URL=https://example.invalid/v2\n", encoding="utf-8")
            certificate.write_text("PUBLIC CERTIFICATE V2\n", encoding="utf-8")

            snapshot, _untracked_patch = repository_snapshot(repo)
            self.assertFalse(snapshot["bounds"]["sensitive_change_quarantine"])
            sensitive = {item["path"] for item in snapshot["sensitive_paths"]}
            self.assertNotIn(".env.example", sensitive)
            self.assertNotIn("certs/public-root.crt", sensitive)
            patch = tracked_patch(repo, sensitive_paths=sorted(sensitive))
            self.assertIn(b"example.invalid/v2", patch)
            self.assertIn(b"PUBLIC CERTIFICATE V2", patch)
            assessment = analyze_change_intelligence(
                repo,
                task="update public security configuration",
                anticipated_paths=[],
                changes=snapshot["changes"],
                tracked_patch=patch,
                declared_risk=None,
            )
            self.assertEqual(assessment["effective_risk"], "high")
            self.assertIn("security", {item["id"] for item in assessment["signals"]})

    def test_sensitive_discovery_filters_reviewable_and_ordinary_candidates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            (repo / ".gitignore").write_text(
                ".env\n.env.example\n.environment\n.envelope\n.envoy\n"
                "public.crt\nprivate.key\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore local fixtures"], cwd=repo, check=True)
            for name in (
                ".env",
                ".env.example",
                ".environment",
                ".envelope",
                ".envoy",
                "public.crt",
                "private.key",
            ):
                (repo / name).write_text("synthetic-value\n", encoding="utf-8")

            discovered = set(discover_sensitive_paths(repo, set()))
            self.assertEqual(discovered, {".env", "private.key"})

    def test_secret_material_and_security_domain_classifiers_are_separate(self) -> None:
        source_paths = (
            "src/auth/token.py",
            "src/token_service.py",
            "src/credential_store.ts",
            "internal/secret_manager.go",
            "src/secrets/manager.py",
            "packages/account/credentials/store.go",
            "src/secrets/rotate.sh",
            "modules/token/validator.sql",
            "src/auth_service.ts",
            "src/permission.rs",
            "src/apiKey.ts",
            "src/auth/token_schema.json",
            "config/token_policy.yaml",
            "config/secret_manager.json",
            "config/credential_store.json",
            "config/clientSecretSchema.json",
            "config/apiTokenPolicy.yaml",
            "config/serviceAccountKeyProvider.json",
            "config/certificate_manager.json",
            "config/keystore_service.json",
            "src/serviceAccountService.ts",
            "certs/client.crt",
        )
        for path in source_paths:
            with self.subTest(source=path):
                self.assertFalse(is_sensitive_material_path(path))
                self.assertTrue(is_security_domain_path(path))
                self.assertFalse(is_protected_deletion_path(path))

        material_paths = (
            ".env.production",
            "config/clientSecret.json",
            "config/apiToken.json",
            "config/serviceAccountKey.json",
            "config/serviceAccount.json",
            "config/apiKey.json",
            "config/clientCertificate.json",
            "config/signingKey.json",
            "config/credentials-prod.json",
            "config/certificate.json",
            "config/keystore.json",
            "deploy/keystores/app.jks",
            "secrets/runtime.py",
            "credentials/provider.ts",
            "private-secrets/loader.py",
        )
        for path in material_paths:
            with self.subTest(material=path):
                self.assertTrue(is_sensitive_material_path(path))
                self.assertTrue(is_security_domain_path(path))
                self.assertTrue(is_protected_deletion_path(path))

        self.assertTrue(
            is_sensitive_material_path(
                "ordinary/location.txt",
                extra_sensitive={"ordinary"},
            )
        )

    def test_security_domain_source_stays_reviewable_and_raises_risk(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            source = repo / "src" / "auth"
            source.mkdir(parents=True)
            token = source / "token.py"
            token.write_text("TOKEN_VERSION = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/auth/token.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "add token source"], cwd=repo, check=True)
            token.write_text("TOKEN_VERSION = 2\n", encoding="utf-8")

            snapshot, _untracked_patch = repository_snapshot(repo)
            self.assertFalse(snapshot["bounds"]["sensitive_change_quarantine"])
            self.assertNotIn(
                "src/auth/token.py",
                {item["path"] for item in snapshot["sensitive_paths"]},
            )
            patch = tracked_patch(
                repo,
                sensitive_paths=[item["path"] for item in snapshot["sensitive_paths"]],
            )
            self.assertIn(b"TOKEN_VERSION = 2", patch)
            assessment = analyze_change_intelligence(
                repo,
                task="change token validation",
                anticipated_paths=[],
                changes=snapshot["changes"],
                tracked_patch=patch,
                declared_risk=None,
            )
            self.assertEqual(assessment["effective_risk"], "high")
            self.assertIn(
                "authentication",
                {item["id"] for item in assessment["signals"]},
            )

    def test_key_material_path_raises_security_risk(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            assessment = analyze_change_intelligence(
                repo,
                task="rotate service integration material",
                anticipated_paths=[],
                changes=[
                    {
                        "status": "??",
                        "path": "config/apiKey.json",
                        "original_path": "",
                    }
                ],
                tracked_patch=b"",
                declared_risk=None,
                allow_repository_reads=False,
            )
            self.assertEqual(assessment["effective_risk"], "high")
            self.assertIn(
                "security",
                {item["id"] for item in assessment["signals"]},
            )

    def test_camelcase_secret_material_is_discovered_without_content_reads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            names = (
                "clientSecret.json",
                "apiToken.json",
                "serviceAccountKey.json",
                "apiKey.json",
                "serviceAccount.json",
                "clientCertificate.json",
                "signingKey.json",
            )
            (repo / ".gitignore").write_text("*.json\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore local material"], cwd=repo, check=True)
            for index, name in enumerate(names):
                (repo / name).write_text(
                    f"synthetic-secret-{index}\n",
                    encoding="utf-8",
                )

            snapshot, untracked_patch = repository_snapshot(repo)
            metadata = {
                item["path"]: item for item in snapshot["sensitive_paths"]
            }
            self.assertEqual(set(metadata), set(names))
            for item in metadata.values():
                self.assertFalse(item["content_read"])
            serialized = json.dumps(snapshot, sort_keys=True)
            self.assertNotIn("synthetic-secret", serialized)
            self.assertNotIn(b"synthetic-secret", untracked_patch)

    def test_equal_length_ignored_sensitive_rewrite_breaks_capture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            (repo / ".env").write_text("TOKEN=AAAA\n", encoding="utf-8")
            command = (
                f"{sys.executable} -c "
                "'__import__(\"pathlib\").Path(\".env\").write_text(\"TOKEN=BBBB\\n\")'"
            )
            governed = self.prepare_governed_change(
                root, repo, command=command, name="same-size-sensitive"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertFalse(summary["capture_preserved"])
            self.assertEqual(summary["sensitive_integrity"], "metadata-observed")
            metadata = next(
                item
                for item in summary["repository_capture"]["sensitive_paths"]
                if item["path"] == ".env"
            )
            for field in ("device", "inode", "link_count", "mtime_ns", "ctime_ns"):
                self.assertIn(field, metadata)

    def test_sensitive_directory_rename_does_not_enter_patch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            private = repo / "private-config"
            private.mkdir()
            secret = private / "secret.txt"
            secret.write_text("never-enter-review-patch\n", encoding="utf-8")
            subprocess.run(["git", "add", "private-config/secret.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "private config"], cwd=repo, check=True)
            private.rename(repo / "public-config")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--sensitive-path",
                    "private-config",
                    "--confirm-dangerous-delete",
                    "private-config/secret.txt",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn(
                b"never-enter-review-patch", (root / "run" / "diff.patch").read_bytes()
            )

    def test_untracked_binary_is_hashed_without_entering_text_patch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert __import__(\"pathlib\").Path(\"asset.bin\").exists()'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["asset.bin"],
                name="binary",
            )
            (repo / "asset.bin").write_bytes(b"binary\x00payload")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            fingerprint = summary["repository_capture"]["untracked"][0]
            self.assertEqual(fingerprint["size"], len(b"binary\x00payload"))
            self.assertEqual(len(fingerprint["sha256"]), 64)
            self.assertEqual(fingerprint["text_patch"], "not-text-or-over-limit")
            self.assertNotIn(b"binary\x00payload", (root / "run" / "diff.patch").read_bytes())

    @unittest.skipIf(os.name == "nt", "non-UTF-8 paths are a POSIX filesystem contract")
    def test_non_utf8_git_path_is_serialized_with_ascii_escapes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="non-utf8"
            )
            raw_path = os.path.join(os.fsencode(repo), b"bad-\xff.py")
            try:
                descriptor = os.open(raw_path, os.O_CREAT | os.O_WRONLY, 0o600)
            except OSError as exc:
                self.skipTest(f"filesystem rejects non-UTF-8 names: {exc}")
            try:
                os.write(descriptor, b"value = 1\n")
            finally:
                os.close(descriptor)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            encoded = (root / "run" / "summary.json").read_bytes()
            self.assertIn(b"bad-\\udcff.py", encoded)
            json.loads(encoded.decode("ascii"))

    @unittest.skipIf(os.name == "nt", "POSIX file-name edge case")
    def test_git_paths_are_never_silently_trimmed_or_reinterpreted(self) -> None:
        for path in (" leading.py", "back\\slash.py"):
            with self.subTest(path=path), tempfile.TemporaryDirectory(
                prefix="rootloom-change-", dir=Path.home()
            ) as temporary:
                root = Path(temporary)
                repo = self.make_repo(root)
                (repo / path).write_text("value = 2\n", encoding="utf-8")
                completed = self.analyze(repo)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("without changing the path", completed.stderr)

    def test_change_contract_blocks_out_of_scope_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                allowed_paths=["src/**"],
                name="scope",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertFalse(summary["change_contract"]["scope_valid"])
            self.assertEqual(summary["tests"], [])
            self.assertEqual(summary["quality_status"], "FAILED")

    def test_output_directory_requires_ownership_and_no_change_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            occupied = root / "occupied"
            occupied.mkdir()
            (occupied / "personal.txt").write_text("mine", encoding="utf-8")
            refused = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(occupied),
                    "--allow-no-change",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("ownership marker", refused.stderr)
            self.assertEqual((occupied / "personal.txt").read_text(), "mine")

            allowed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "empty"),
                    "--allow-no-change",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            summary = json.loads((root / "empty" / "summary.json").read_text())
            self.assertEqual(summary["quality_status"], "NO_CHANGE")
            self.assertEqual(summary["process_exit_code"], 0)
            self.assertFalse(summary["passed"])
            self.assertTrue((root / "empty" / ".rootloom-engineering-bundle.json").is_file())

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_output_ownership_marker_must_be_bounded_regular_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            target = root / "external-marker.json"
            target.write_text(
                json.dumps(
                    {
                        "format": "rootloom-engineering-bundle-owner-v1",
                        "managed_by": "rootloom",
                    }
                ),
                encoding="ascii",
            )
            output = root / "linked-marker-output"
            output.mkdir()
            (output / ".rootloom-engineering-bundle.json").symlink_to(target)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    "--allow-no-change",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("ownership marker", completed.stderr)
            self.assertTrue((output / ".rootloom-engineering-bundle.json").is_symlink())
            self.assertIn("managed_by", target.read_text(encoding="ascii"))

    def test_finalizer_refuses_in_repository_output_and_oversized_patch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            inside = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(repo / "run"),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(inside.returncode, 0)
            self.assertIn("outside the repository", inside.stderr)
            self.assertFalse((repo / "run").exists())

            oversized = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--max-patch-bytes",
                    "1",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(oversized.returncode, 0)
            self.assertIn("exceeds configured 1-byte budget", oversized.stderr)
            self.assertFalse((root / "run").exists())

    def test_evidence_entry_points_reject_linked_worktree_git_common_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            main = self.make_repo(root)
            worktree = root / "linked-worktree"
            subprocess.run(
                ["git", "worktree", "add", "-q", "-b", "linked-review", str(worktree)],
                cwd=main,
                check=True,
            )
            raw_common = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=worktree,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            common = Path(raw_common)
            if not common.is_absolute():
                common = worktree / common
            common = common.resolve()

            intake_inside = common / "refs" / "heads" / "rootloom-review-intake"
            begun = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(worktree),
                    "--task",
                    "reject Git storage output",
                    "--output",
                    str(intake_inside),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(begun.returncode, 0)
            self.assertIn("Git common directory", begun.stderr)
            self.assertFalse(intake_inside.exists())

            baseline_inside = common / "rootloom-review-baseline.json"
            analyzed = self.analyze(
                worktree,
                "--task",
                "reject Git storage baseline",
                "--path",
                "app.py",
                "--write-baseline",
                str(baseline_inside),
            )
            self.assertNotEqual(analyzed.returncode, 0)
            self.assertIn("Git common directory", analyzed.stderr)
            self.assertFalse(baseline_inside.exists())

            review_outside = root / "review-outside"
            begun_outside = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(worktree),
                    "--task",
                    "reject Git storage seal",
                    "--output",
                    str(review_outside),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(begun_outside.returncode, 0, begun_outside.stderr)
            review_inside = common / "rootloom-review-seal"
            review_outside.rename(review_inside)
            sealed = subprocess.run(
                [
                    sys.executable,
                    str(SEAL_CONTRACT),
                    "--review-dir",
                    str(review_inside),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(sealed.returncode, 0)
            self.assertIn("Git common directory", sealed.stderr)

            (worktree / "app.py").write_text("value = 2\n", encoding="utf-8")
            evidence_inside = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(worktree),
                    "--output",
                    str(root / "evidence-run"),
                    "--baseline",
                    str(review_inside / "baseline.json"),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(evidence_inside.returncode, 0)
            self.assertIn("Git common directory", evidence_inside.stderr)
            self.assertFalse((root / "evidence-run").exists())

            bundle_inside = common / "rootloom-review-bundle"
            finalized = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(worktree),
                    "--output",
                    str(bundle_inside),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(finalized.returncode, 0)
            self.assertIn("Git common directory", finalized.stderr)
            self.assertFalse(bundle_inside.exists())

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_review_and_bundle_outputs_reject_symlinked_parent_components(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            target = root / "target"
            target.mkdir()
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(target, target_is_directory=True)
            begun = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "change product behavior",
                    "--output",
                    str(linked_parent / "review"),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(begun.returncode, 0)
            self.assertIn("must not traverse a symlink", begun.stderr)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            finalized = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(linked_parent / "bundle"),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(finalized.returncode, 0)
            self.assertIn("must not traverse a symlink", finalized.stderr)
            analyzed = self.analyze(
                repo,
                "--write-baseline",
                str(linked_parent / "baseline.json"),
            )
            self.assertNotEqual(analyzed.returncode, 0)
            self.assertIn("must not traverse a symlink", analyzed.stderr)
            self.assertFalse((target / "review").exists())
            self.assertFalse((target / "bundle").exists())
            self.assertFalse((target / "baseline.json").exists())

            traversing = subprocess.run(
                [
                    sys.executable,
                    str(BEGIN_REVIEW),
                    "--repo",
                    str(repo),
                    "--task",
                    "change product behavior",
                    "--output",
                    os.fspath(linked_parent / ".." / "traversed-review"),
                    "--path",
                    "app.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(traversing.returncode, 0)
            self.assertIn("parent traversal", traversing.stderr)
            self.assertFalse((root / "traversed-review").exists())

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_verification_cannot_redirect_bundle_output_after_preflight(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            output = root / "run"
            victim = root / "victim"
            victim.mkdir()
            command = (
                f"{sys.executable} -c "
                f"'__import__(\"pathlib\").Path(\"{output}\").symlink_to("
                f"\"{victim}\",target_is_directory=True)'"
            )
            governed = self.prepare_governed_change(
                root, repo, command=command, name="output-redirection"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("output path changed during verification", completed.stderr)
            self.assertTrue(output.is_symlink())
            self.assertEqual(list(victim.iterdir()), [])

    def test_analyzer_dirty_baseline_is_declared_and_readable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            baseline = root / "dirty-baseline.json"
            analyzed = self.analyze(repo, "--write-baseline", str(baseline))
            self.assertEqual(analyzed.returncode, 0, analyzed.stderr)
            payload, _digest = read_baseline_payload_with_hash(baseline)
            self.assertTrue(payload["allow_dirty_baseline"])
            self.assertEqual(
                payload["preexisting_changes"], payload["snapshot"]["changes"]
            )

    def test_finalizer_auto_risk_and_manual_high_risk_are_not_lowered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            readme = repo / "README.md"
            readme.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "docs"], cwd=repo, check=True)
            readme.write_text("after\n", encoding="utf-8")

            automatic = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "automatic"),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(automatic.returncode, 0, automatic.stderr)
            auto_summary = json.loads(
                (root / "automatic" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(auto_summary["risk"], "low")
            self.assertIsNone(auto_summary["risk_assessment"]["declared_risk"])

            manual = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "manual"),
                    "--risk",
                    "high",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(manual.returncode, 0, manual.stderr)
            manual_summary = json.loads(
                (root / "manual" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manual_summary["risk"], "high")
            self.assertFalse(manual_summary["risk_assessment"]["risk_was_raised"])

    def test_sensitive_deletion_requires_exact_confirmation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            secret = repo / ".env"
            secret.write_text("TOKEN=redacted\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "env"], cwd=repo, check=True)
            command = (
                f"{sys.executable} -c "
                "'assert not __import__(\"pathlib\").Path(\".env\").exists()'"
            )
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="remove obsolete secret file",
                name="delete-secret",
            )
            secret.unlink()
            base = [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(repo),
                "--output",
                str(root / "run"),
                "--risk",
                "high",
                *governed,
                "--verify",
                command,
            ]
            refused = subprocess.run(base, capture_output=True, text=True, check=False)
            self.assertEqual(refused.returncode, 10)
            self.assertIn(".env", refused.stdout)
            accepted = subprocess.run(
                [*base, "--confirm-dangerous-delete", ".env"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(
                summary["quality_status"], "REVIEW_REQUIRED_WITH_REDACTIONS"
            )
            self.assertFalse(summary["passed"])

    def test_dangerous_deletion_never_leaves_a_stale_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            secret = repo / ".env"
            secret.write_text("TOKEN=redacted\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "track env"], cwd=repo, check=True)
            output = root / "run"
            output.mkdir()
            (output / ".rootloom-engineering-bundle.json").write_text(
                json.dumps(
                    {
                        "format": "rootloom-engineering-bundle-owner-v1",
                        "managed_by": "rootloom",
                    }
                ),
                encoding="ascii",
            )
            (output / "summary.json").write_text(
                '{"quality_status":"REVIEW_EVIDENCE_COMPLETE","passed":true}',
                encoding="ascii",
            )
            secret.unlink()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 10, completed.stderr)
            self.assertFalse((output / "summary.json").exists())

    def test_confirmed_sensitive_rename_quarantines_all_changed_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            secret = repo / ".env"
            secret.write_text("TOKEN=never-enter-bundle\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="relocate obsolete secret configuration",
                allowed_paths=[".env", "app.py", "leaked.txt"],
                name="quarantined-sensitive-rename",
            )
            secret.rename(repo / "leaked.txt")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--confirm-dangerous-delete",
                    ".env",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["sensitive_deletion_quarantine"])
            self.assertEqual(
                summary["quality_status"], "REVIEW_REQUIRED_WITH_REDACTIONS"
            )
            self.assertFalse(summary["passed"])
            patch = (root / "run" / "diff.patch").read_text(encoding="utf-8")
            self.assertNotIn("never-enter-bundle", patch)
            metadata = next(
                item
                for item in summary["repository_capture"]["untracked"]
                if item["path"] == "leaked.txt"
            )
            self.assertFalse(metadata["content_read"])
            self.assertTrue(metadata["sensitive"])

    def test_ignored_sensitive_deletion_is_enforced_by_contract_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            secret = repo / ".env"
            secret.write_text("TOKEN=scope-protected\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="delete obsolete sensitive configuration",
                allowed_paths=["app.py"],
                name="sensitive-scope",
            )
            secret.unlink()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--confirm-dangerous-delete",
                    ".env",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertEqual(summary["changed_files"], [".env"])
            self.assertEqual(
                summary["change_contract"]["scope_violations"][
                    "outside_allowed_paths"
                ],
                [".env"],
            )
            self.assertEqual(summary["quality_status"], "FAILED")

    def test_sensitive_replacement_quarantines_content_before_baseline_comparison(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            secret = repo / ".env"
            secret.write_text("TOKEN=never-read-after-replacement\n", encoding="utf-8")
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="reject replaced sensitive state",
                allowed_paths=["app.py", "leaked.txt"],
                name="replaced-sensitive-state",
            )
            secret.rename(repo / "leaked.txt")
            secret.write_text("placeholder\n", encoding="utf-8")
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["sensitive_change_quarantine"])
            self.assertFalse(summary["sensitive_deletion_quarantine"])
            self.assertEqual(summary["quality_status"], "FAILED")
            patch = (root / "run" / "diff.patch").read_text(encoding="utf-8")
            self.assertNotIn("never-read-after-replacement", patch)
            metadata = next(
                item
                for item in summary["repository_capture"]["untracked"]
                if item["path"] == "leaked.txt"
            )
            self.assertFalse(metadata["content_read"])

    def test_snapshot_quarantines_all_changes_when_git_reports_sensitive_change(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            secret = repo / ".env"
            secret.write_text("TOKEN=never-read-from-relocated-file\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "track env"], cwd=repo, check=True)
            secret.rename(repo / "relocated.txt")
            snapshot, untracked_patch = repository_snapshot(repo)
            self.assertTrue(snapshot["bounds"]["sensitive_change_quarantine"])
            metadata = next(
                item
                for item in snapshot["untracked"]
                if item["path"] == "relocated.txt"
            )
            self.assertTrue(metadata["sensitive"])
            self.assertFalse(metadata["content_read"])
            self.assertNotIn(b"never-read-from-relocated-file", untracked_patch)

    def test_repository_capture_rejects_a_mixed_concurrent_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            repo = self.make_repo(Path(temporary))
            original_capture = repository_snapshot
            calls = 0

            def mutate_after_first_snapshot(*args, **kwargs):
                nonlocal calls
                captured = original_capture(*args, **kwargs)
                calls += 1
                if calls == 1:
                    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
                return captured

            with mock.patch(
                "runner.state.repository_snapshot",
                side_effect=mutate_after_first_snapshot,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "did not stabilize across bounded captures",
                ):
                    stable_repository_capture(repo)

    def test_verification_sensitive_rename_is_quarantined_before_recapture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            (repo / ".env").write_text(
                "TOKEN=verification-secret\n", encoding="utf-8"
            )
            command = (
                f"{sys.executable} -c "
                "'__import__(\"pathlib\").Path(\".env\").rename(\"leaked.txt\")'"
            )
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="verify secret relocation is rejected",
                allowed_paths=["app.py", "leaked.txt"],
                name="verification-sensitive-rename",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--confirm-dangerous-delete",
                    ".env",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["verification_sensitive_deletion_quarantine"])
            self.assertFalse(summary["capture_preserved"])
            self.assertEqual(summary["quality_status"], "FAILED")
            patch = (root / "run" / "diff.patch").read_text(encoding="utf-8")
            self.assertNotIn("verification-secret", patch)
            metadata = next(
                item
                for item in summary["repository_capture"]["untracked"]
                if item["path"] == "leaked.txt"
            )
            self.assertFalse(metadata["content_read"])

    def test_verification_sensitive_replacement_is_quarantined_before_recapture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore env"], cwd=repo, check=True)
            (repo / ".env").write_text(
                "TOKEN=verification-replacement-secret\n", encoding="utf-8"
            )
            command = (
                f"{sys.executable} -c "
                "'from pathlib import Path; "
                "Path(\".env\").rename(\"leaked.txt\"); "
                "Path(\".env\").write_text(\"placeholder\\n\")'"
            )
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="reject sensitive replacement during verification",
                allowed_paths=["app.py", "leaked.txt"],
                name="verification-sensitive-replacement",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--strict",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((root / "run" / "summary.json").read_text())
            self.assertTrue(summary["verification_sensitive_change_quarantine"])
            self.assertFalse(summary["verification_sensitive_deletion_quarantine"])
            self.assertFalse(summary["capture_preserved"])
            patch = (root / "run" / "diff.patch").read_text(encoding="utf-8")
            self.assertNotIn("verification-replacement-secret", patch)
            metadata = next(
                item
                for item in summary["repository_capture"]["untracked"]
                if item["path"] == "leaked.txt"
            )
            self.assertFalse(metadata["content_read"])

    def test_sensitive_rename_guards_the_original_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            secret = repo / ".env"
            secret.write_text("TOKEN=redacted\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "env"], cwd=repo, check=True)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="rename secret configuration",
                name="rename-secret",
            )
            secret.rename(repo / "config.txt")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--risk",
                    "high",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode, 10, f"stdout={completed.stdout}\nstderr={completed.stderr}"
            )
            self.assertIn(".env", completed.stdout)

    def test_verification_cannot_hide_a_sensitive_deletion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            secret = repo / ".env"
            secret.write_text("TOKEN=redacted\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "env"], cwd=repo, check=True)
            command = (
                f"{sys.executable} -c "
                "'__import__(\"pathlib\").Path(\".env\").unlink()'"
            )
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="change product behavior",
                name="verification-delete",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--risk",
                    "high",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 10)
            self.assertIn("verification introduced dangerous deletions", completed.stdout)
            self.assertFalse((root / "run" / "summary.json").exists())

    def test_untracked_patch_quotes_ambiguous_file_names(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            path = "safe.py +++ injected.py"
            candidate = repo / path
            candidate.write_text("value = 2\n", encoding="utf-8")
            candidate.chmod(0o755)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            patch = (root / "run" / "diff.patch").read_bytes()
            self.assertIn(b'"a/safe.py +++ injected.py"', patch)
            expected_mode = (
                b"100755" if candidate.stat().st_mode & 0o111 else b"100644"
            )
            self.assertIn(b"new file mode " + expected_mode, patch)
            self.assertNotIn(b"diff --git a/safe.py +++ injected.py", patch)

    def test_untracked_patch_filter_handles_quoted_paths_and_patch_like_content(
        self,
    ) -> None:
        kept = _new_file_patch(
            " leading name.txt",
            b"diff --git a/fake b/fake\n",
            mode=0o644,
        )
        removed = _new_file_patch("ordinary.txt", b"ordinary\n", mode=0o644)
        combined = kept + b"\n" + removed
        self.assertEqual(
            filter_untracked_patch(combined, {" leading name.txt"}),
            kept,
        )
        self.assertEqual(
            filter_untracked_patch(
                combined, {" leading name.txt", "ordinary.txt"}
            ),
            combined,
        )

    def test_untracked_text_patches_apply_for_empty_and_nonempty_files(self) -> None:
        for content in (
            b"",
            b"one line",
            b"one line\n",
            b"one\ntwo",
            b"one\r",
            b"one\r\ntwo\r\n",
            b"\r",
        ):
            with self.subTest(content=content), tempfile.TemporaryDirectory(
                prefix="rootloom-change-", dir=Path.home()
            ) as temporary:
                repo = Path(temporary)
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
                subprocess.run(
                    ["git", "config", "core.autocrlf", "false"],
                    cwd=repo,
                    check=True,
                )
                patch = _new_file_patch("new file.txt", content, mode=0o644)
                checked = subprocess.run(
                    ["git", "apply", "--check", "-"],
                    cwd=repo,
                    input=patch,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(checked.returncode, 0, checked.stderr.decode())
                applied = subprocess.run(
                    ["git", "apply", "-"],
                    cwd=repo,
                    input=patch,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(applied.returncode, 0, applied.stderr.decode())
                self.assertEqual((repo / "new file.txt").read_bytes(), content)

    def test_verification_cannot_delete_an_untracked_sensitive_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".env").write_text("TOKEN=redacted\n", encoding="utf-8")
            command = (
                f"{sys.executable} -c "
                "'__import__(\"pathlib\").Path(\".env\").unlink()'"
            )
            governed = self.prepare_governed_change(
                root,
                repo,
                command=command,
                task="change product behavior",
                name="untracked-secret",
                allow_dirty_baseline=True,
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    *governed,
                    "--risk",
                    "high",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode, 10, f"stdout={completed.stdout}\nstderr={completed.stderr}"
            )
            self.assertIn("verification introduced dangerous deletions", completed.stdout)

    def test_verification_worktree_mutation_marks_bundle_failed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            output = root / "run"
            command = (
                f"{sys.executable} -c "
                "'__import__(\"pathlib\").Path(\"app.py\").write_text(\"value = 3\\n\")'"
            )
            governed = self.prepare_governed_change(
                root, repo, command=command, name="verification-mutation"
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    *governed,
                    "--risk",
                    "medium",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["passed"])
            self.assertFalse(summary["verification_preserved_capture"])
            self.assertEqual(summary["changed_files"], ["app.py"])
            self.assertIn(b"value = 3", (output / "diff.patch").read_bytes())
            self.assertIn(
                "verification changed the tracked patch or captured path/content set",
                (output / "test.log").read_text(encoding="utf-8"),
            )

    def test_unborn_repository_writes_a_bundle_without_head(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            command = f"{sys.executable} -c 'assert True'"
            governed = self.prepare_governed_change(
                root, repo, command=command, name="unborn"
            )
            (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
            output = root / "run"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    *governed,
                    "--risk",
                    "low",
                    "--verify",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["passed"])
            self.assertTrue(summary["verification_preserved_capture"])
            self.assertEqual(summary["changed_files"], ["app.py"])
            self.assertIn(b"value = 1", (output / "diff.patch").read_bytes())

    def test_unborn_repository_git_capture_closes_inherited_stdin(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
            probe = "\n".join(
                [
                    "import sys",
                    f"sys.path.insert(0, {str(SCRIPT.parent)!r})",
                    "from runner.state import tracked_patch",
                    f"patch = tracked_patch({str(repo)!r}, max_git_seconds=0.2)",
                    "sys.stdout.buffer.write(patch)",
                ]
            )
            process = subprocess.Popen(
                [sys.executable, "-c", probe],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                try:
                    returncode = process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    self.fail("tracked_patch did not terminate with inherited stdin open")
            finally:
                assert process.stdin is not None
                process.stdin.close()
            assert process.stdout is not None
            assert process.stderr is not None
            stdout = process.stdout.read()
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            process.stdout.close()
            process.stderr.close()
            self.assertEqual(returncode, 0, stderr)
            self.assertIn(b"value = 1", stdout)

    def test_invalid_detached_head_is_not_treated_as_an_unborn_branch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / ".git" / "HEAD").write_text("0" * 40 + "\n", encoding="ascii")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(root / "run"),
                    "--risk",
                    "low",
                    "--verify",
                    f"{sys.executable} -c 'assert True'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("bad object HEAD", completed.stderr)
            self.assertFalse((root / "run" / "summary.json").exists())

    def test_no_verification_is_not_reported_as_passed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-change-", dir=Path.home()) as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            governed = self.prepare_governed_change(
                root,
                repo,
                command=f"{sys.executable} -c 'assert True'",
                name="no-verification",
            )
            (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
            output = root / "run"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--output",
                    str(output),
                    *governed,
                    "--risk",
                    "low",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["passed"])


if __name__ == "__main__":
    unittest.main()
