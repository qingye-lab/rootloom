from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_portable_plugin as syncer  # noqa: E402
import validate_repo as validator  # noqa: E402


PORTABLE_ROOT = ROOT / "portable" / "rootloom"
CODEX_MANIFEST = ROOT / "plugins" / "rootloom" / ".codex-plugin" / "plugin.json"
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
ARTIFACT_HELPER = (
    ROOT / "plugins" / "rootloom" / "skills" / "operating-coding-change"
    / "scripts" / "artifact_context.py"
)
ARTIFACT_SPEC = importlib.util.spec_from_file_location("artifact_context", ARTIFACT_HELPER)
assert ARTIFACT_SPEC is not None and ARTIFACT_SPEC.loader is not None
artifact_context = importlib.util.module_from_spec(ARTIFACT_SPEC)
ARTIFACT_SPEC.loader.exec_module(artifact_context)


class PortablePluginTests(unittest.TestCase):
    def manifest(self) -> dict[str, object]:
        return json.loads((PORTABLE_ROOT / "plugin.json").read_text(encoding="utf-8"))

    def codex_manifest(self) -> dict[str, object]:
        return json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))

    def test_checked_in_package_matches_deterministic_source(self) -> None:
        self.assertEqual(syncer.check(PORTABLE_ROOT), [])

    def test_skill_source_rejects_files_outside_the_publication_allowlist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-portable-source-") as temporary:
            skill_root = Path(temporary) / "sample-skill"
            skill_root.mkdir()
            (skill_root / "SKILL.md").write_text(
                "---\nname: sample-skill\n"
                "description: Portable test skill.\n---\n\n# Test\n",
                encoding="utf-8",
            )
            (skill_root / ".env").write_text(
                "ROOTLOOM_TEST_SECRET=do-not-package\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unapproved portable source file.*\\.env"):
                syncer.portable_skill_files(skill_root, (Path("SKILL.md"),))

    def test_generator_builds_an_isolated_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-portable-") as temporary:
            output = Path(temporary) / "rootloom"
            syncer.write(output)
            self.assertEqual(syncer.check(output), [])
            self.assertEqual(
                {path.name for path in (output / "skills").iterdir()},
                {
                    "operating-code-review",
                    "operating-coding-change",
                    "project-guidance",
                },
            )
            self.assertFalse((output / ".codex-plugin").exists())
            self.assertFalse((output / "hooks").exists())
            self.assertFalse((output / "skills" / "setup-rootloom").exists())
            helper = output / "skills" / "project-guidance" / "scripts"
            self.assertTrue((helper / "seed_project_guidance.py").is_file())
            self.assertEqual(
                (helper / "rootloom_lock.py").read_bytes(),
                (ROOT / "plugins" / "rootloom" / "lib" / "rootloom_lock.py").read_bytes(),
            )

            repository = Path(temporary) / "repository with spaces"
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(helper / "seed_project_guidance.py"),
                    "probe",
                    "--cwd",
                    str(repository),
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["status"], "ready")

            artifact_helper = (
                output
                / "skills"
                / "operating-coding-change"
                / "scripts"
                / "artifact_context.py"
            )
            self.assertTrue(artifact_helper.is_file())
            self.assertEqual(
                artifact_helper.read_bytes(),
                (
                    ROOT
                    / "plugins"
                    / "rootloom"
                    / "skills"
                    / "operating-coding-change"
                    / "scripts"
                    / "artifact_context.py"
                ).read_bytes(),
            )

    def test_artifact_context_receipt_cache_and_validation(self) -> None:
        helper = ARTIFACT_HELPER
        with tempfile.TemporaryDirectory(prefix="rootloom-artifact-") as temporary:
            root = Path(temporary)
            cache = root / "cache"
            artifact = root / "fixture.txt"
            artifact.write_text("alpha\nbeta\n", encoding="utf-8")

            def run(*arguments: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        sys.executable,
                        str(helper),
                        "--cache-root",
                        str(cache),
                        *arguments,
                    ],
                    cwd=ROOT,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True,
                    text=True,
                    check=False,
                )

            prepared = run(
                "prepare",
                "--intent",
                "summarize the fixture",
                "--path",
                str(artifact),
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            prepare_payload = json.loads(prepared.stdout)
            self.assertEqual(prepare_payload["status"], "needs-analysis")
            if os.name == "posix":
                self.assertEqual(cache.stat().st_mode & 0o777, 0o700)
                self.assertEqual(
                    Path(prepare_payload["manifest_path"]).stat().st_mode & 0o777,
                    0o600,
                )
            manifest = json.loads(
                Path(prepare_payload["manifest_path"]).read_text(encoding="utf-8")
            )
            draft = Path(prepare_payload["draft_path"])
            receipt = json.loads(draft.read_text(encoding="utf-8"))
            self.assertEqual(receipt["facts"], [{"claim": "", "evidence": []}])
            receipt["summary"] = "The fixture contains two short lines."
            receipt["artifact_notes"][0]["summary"] = "Text with alpha and beta."
            receipt["artifact_notes"][0]["locators"] = ["lines 1-2"]
            receipt["facts"] = [
                {"claim": "There are two entries.", "evidence": ["lines 1-2"]}
            ]
            draft.write_text(json.dumps(receipt), encoding="utf-8")

            finalized = run(
                "finalize",
                "--bundle-id",
                prepare_payload["bundle_id"],
                "--draft",
                str(draft),
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            shown = run("show", "--bundle-id", prepare_payload["bundle_id"])
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(shown.stdout)["format"], "rootloom-artifact-context-v1")

            renamed = root / "renamed.txt"
            renamed.write_bytes(artifact.read_bytes())
            cached = run(
                "prepare",
                "--intent",
                "summarize the fixture",
                "--path",
                str(renamed),
            )
            self.assertEqual(cached.returncode, 0, cached.stderr)
            cached_payload = json.loads(cached.stdout)
            self.assertEqual(cached_payload["bundle_id"], prepare_payload["bundle_id"])
            self.assertEqual(cached_payload["status"], "cached")
            self.assertNotIn("draft_path", cached_payload)
            self.assertEqual(manifest["artifacts"][0]["sha256"], receipt["artifact_notes"][0]["sha256"])

    def test_artifact_context_stops_reading_after_unique_total_exceeds_limit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-artifact-limit-") as temporary:
            root = Path(temporary)
            paths = [root / f"{name}.txt" for name in ("first", "second", "third")]
            for path, content in zip(paths, (b"a" * 8, b"b" * 8, b"c" * 8)):
                path.write_bytes(content)
            arguments = ["prepare", "--intent", "inspect"]
            for path in paths:
                arguments.extend(("--path", str(path)))
            args = artifact_context.parser().parse_args(arguments)
            cache = root / "cache"

            with (
                mock.patch.object(artifact_context, "MAX_TOTAL_BYTES", 10),
                mock.patch.object(
                    artifact_context, "inspect_artifact", wraps=artifact_context.inspect_artifact
                ) as inspect,
            ):
                with self.assertRaisesRegex(artifact_context.ArtifactContextError, "bundle exceeds 10 bytes"):
                    artifact_context.command_prepare(args, cache)

            self.assertEqual(inspect.call_args_list, [mock.call(str(path)) for path in paths[:2]])
            self.assertFalse(cache.exists())

    def test_artifact_context_total_limit_preserves_deduplication_and_media_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-artifact-dedup-") as temporary:
            root = Path(temporary)
            first, duplicate, last = [root / name for name in ("first.txt", "copy.txt", "last.txt")]
            first.write_bytes(b"abcdef")
            duplicate.write_bytes(first.read_bytes())
            last.write_bytes(b"ghij")
            args = artifact_context.parser().parse_args([
                "prepare", "--intent", "inspect", "--path", str(first),
                "--path", str(duplicate), "--path", str(last),
            ])

            with mock.patch.object(artifact_context, "MAX_TOTAL_BYTES", 10):
                prepared = artifact_context.command_prepare(args, root / "cache")
                self.assertEqual(prepared["total_bytes"], 10)
                self.assertEqual(prepared["artifact_count"], 2)
                self.assertTrue(Path(prepared["manifest_path"]).is_file())
                self.assertTrue(Path(prepared["draft_path"]).is_file())

                conflict = root / "copy.json"
                duplicate.rename(conflict)
                args.path = [str(first), str(conflict)]
                with self.assertRaisesRegex(artifact_context.ArtifactContextError, "conflicting inferred media types"):
                    artifact_context.command_prepare(args, root / "conflict-cache")
                self.assertFalse((root / "conflict-cache").exists())

    def test_artifact_context_rejects_raw_receipt_and_changed_source(self) -> None:
        helper = ARTIFACT_HELPER
        with tempfile.TemporaryDirectory(prefix="rootloom-artifact-negative-") as temporary:
            root = Path(temporary)
            cache = root / "cache"
            artifact = root / "fixture.bin"
            artifact.write_bytes(b"stable")

            def run(*arguments: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(helper), "--cache-root", str(cache), *arguments],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            first = run("prepare", "--intent", "inspect", "--path", str(artifact))
            self.assertEqual(first.returncode, 0, first.stderr)
            first_payload = json.loads(first.stdout)
            raw_draft = Path(first_payload["draft_path"])
            raw_receipt = json.loads(raw_draft.read_text(encoding="utf-8"))
            raw_receipt["summary"] = "data:image/png;base64,AAAA"
            raw_receipt["artifact_notes"][0]["summary"] = "binary"
            raw_receipt["facts"] = []
            raw_draft.write_text(json.dumps(raw_receipt), encoding="utf-8")
            rejected = run(
                "finalize",
                "--bundle-id",
                first_payload["bundle_id"],
                "--draft",
                str(raw_draft),
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("must not embed raw artifact data", rejected.stderr)

            second = run("prepare", "--intent", "inspect differently", "--path", str(artifact))
            self.assertEqual(second.returncode, 0, second.stderr)
            second_payload = json.loads(second.stdout)
            changed_draft = Path(second_payload["draft_path"])
            changed_receipt = json.loads(changed_draft.read_text(encoding="utf-8"))
            changed_receipt["summary"] = "A stable binary fixture."
            changed_receipt["artifact_notes"][0]["summary"] = "Binary fixture."
            changed_receipt["facts"] = []
            changed_draft.write_text(json.dumps(changed_receipt), encoding="utf-8")
            artifact.write_bytes(b"changed")
            changed = run(
                "finalize",
                "--bundle-id",
                second_payload["bundle_id"],
                "--draft",
                str(changed_draft),
            )
            self.assertEqual(changed.returncode, 2)
            self.assertIn("artifact changed after prepare", changed.stderr)

            third = run("prepare", "--intent", "inspect identity", "--path", str(artifact))
            self.assertEqual(third.returncode, 0, third.stderr)
            third_payload = json.loads(third.stdout)
            manifest_path = Path(third_payload["manifest_path"])
            tampered_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered_manifest["artifacts"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(tampered_manifest), encoding="utf-8")
            tampered = run("show", "--bundle-id", third_payload["bundle_id"])
            self.assertEqual(tampered.returncode, 2)
            self.assertIn("manifest content identity does not match", tampered.stderr)

    def test_common_package_has_no_host_specific_forks(self) -> None:
        forbidden = (
            ".cursor-plugin",
            ".vscode",
            ".github",
            "POWER.md",
            "dev.kiro",
            "hooks",
            "rules",
        )
        for relative in forbidden:
            with self.subTest(relative=relative):
                self.assertFalse((PORTABLE_ROOT / relative).exists())

    def test_generator_rejects_symlinked_output_and_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-portable-") as temporary:
            temporary_root = Path(temporary)
            output_target = temporary_root / "output-target"
            output_target.mkdir()
            output_link = temporary_root / "output-link"
            try:
                output_link.symlink_to(output_target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"filesystem cannot create directory symlink: {exc}")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "sync_portable_plugin.py"),
                    "--output",
                    str(output_link),
                    "--write",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must not be a symlink", completed.stderr)
            self.assertEqual(list(output_target.iterdir()), [])
            syncer.write(output_target)
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                syncer.check(output_link)

            source_plugin = temporary_root / "source-plugin"
            source_manifest = source_plugin / ".codex-plugin" / "plugin.json"
            source_manifest.parent.mkdir(parents=True)
            source_manifest.write_text(
                CODEX_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8"
            )
            for skill_name in syncer.PORTABLE_SKILLS:
                skill_root = source_plugin / "skills" / skill_name
                skill_root.mkdir(parents=True)
                (skill_root / "SKILL.md").write_text(
                    f"---\nname: {skill_name}\n"
                    "description: Portable test skill.\n---\n\n# Test\n",
                    encoding="utf-8",
                )
            outside = temporary_root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            linked_reference = (
                source_plugin
                / "skills"
                / "operating-code-review"
                / "references"
                / "outside.md"
            )
            linked_reference.parent.mkdir()
            linked_reference.symlink_to(outside)
            with (
                mock.patch.object(syncer, "SOURCE_BOUNDARY", temporary_root),
                mock.patch.object(syncer, "SOURCE_PLUGIN", source_plugin),
                mock.patch.object(syncer, "SOURCE_MANIFEST", source_manifest),
            ):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    syncer.expected_files()

            linked_source_plugin = temporary_root / "linked-source-plugin"
            linked_manifest = (
                linked_source_plugin / ".codex-plugin" / "plugin.json"
            )
            linked_manifest.parent.mkdir(parents=True)
            linked_manifest.write_text(
                CODEX_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8"
            )
            linked_skills = linked_source_plugin / "skills"
            linked_skills.mkdir()
            external_skill = temporary_root / "external-review"
            external_skill.mkdir()
            (external_skill / "SKILL.md").write_text(
                "---\nname: operating-code-review\n"
                "description: External test skill.\n---\n\n# Test\n",
                encoding="utf-8",
            )
            (linked_skills / "operating-code-review").symlink_to(
                external_skill, target_is_directory=True
            )
            change_skill = linked_skills / "operating-coding-change"
            change_skill.mkdir()
            (change_skill / "SKILL.md").write_text(
                "---\nname: operating-coding-change\n"
                "description: Internal test skill.\n---\n\n# Test\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(syncer, "SOURCE_BOUNDARY", temporary_root),
                mock.patch.object(syncer, "SOURCE_PLUGIN", linked_source_plugin),
                mock.patch.object(syncer, "SOURCE_MANIFEST", linked_manifest),
            ):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    syncer.expected_files()

            source_boundary = temporary_root / "source-boundary"
            source_boundary.mkdir()
            external_plugins = temporary_root / "external-plugins"
            external_plugins.mkdir()
            (source_boundary / "plugins").symlink_to(
                external_plugins, target_is_directory=True
            )
            external_rootloom = external_plugins / "rootloom"
            external_rootloom.mkdir()
            with (
                mock.patch.object(syncer, "SOURCE_BOUNDARY", source_boundary),
                mock.patch.object(
                    syncer,
                    "SOURCE_PLUGIN",
                    source_boundary / "plugins" / "rootloom",
                ),
            ):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    syncer.expected_files()

    def test_portable_manifest_satisfies_repository_contract(self) -> None:
        errors: list[str] = []
        validator.validate_agent_plugin_manifest_payload(
            self.manifest(), self.codex_manifest(), errors
        )
        self.assertEqual(errors, [])

    def test_native_manifest_isolation_rejects_agent_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-native-") as temporary:
            native_root = Path(temporary)
            errors: list[str] = []
            validator.validate_native_manifest_isolation(errors, native_root)
            self.assertEqual(errors, [])
            (native_root / "plugin.json").write_text("{}\n", encoding="utf-8")
            validator.validate_native_manifest_isolation(errors, native_root)
            self.assertTrue(any("suppress native Hook" in error for error in errors))

    def test_portable_manifest_rejects_schema_shape_and_identity_drift(self) -> None:
        base = self.manifest()
        cases = (
            ("schema", {**base, "$schema": "https://example.invalid/schema.json"}, "target"),
            ("unknown", {**base, "interface": {}}, "unknown fields"),
            ("name", {**base, "name": "Rootloom"}, "name violates"),
            ("version type", {**base, "version": 41}, "version must be a string"),
            ("author type", {**base, "author": {"name": 7}}, "author values"),
            ("keywords type", {**base, "keywords": "rootloom"}, "keywords"),
            ("shared drift", {**base, "repository": "https://example.invalid"}, "shared field"),
        )
        for label, payload, expected in cases:
            with self.subTest(label=label):
                errors: list[str] = []
                validator.validate_agent_plugin_manifest_payload(
                    payload, self.codex_manifest(), errors
                )
                self.assertTrue(
                    any(expected in error for error in errors),
                    f"{expected!r} not found in {errors!r}",
                )

    def test_portable_skills_have_only_resolvable_relative_links(self) -> None:
        skill_roots = sorted((PORTABLE_ROOT / "skills").iterdir())
        self.assertEqual(
            {path.name for path in skill_roots},
            {
                "operating-code-review",
                "operating-coding-change",
                "project-guidance",
            },
        )
        for skill_root in skill_roots:
            for markdown in skill_root.rglob("*.md"):
                text = markdown.read_text(encoding="utf-8")
                for raw_target in MARKDOWN_LINK.findall(text):
                    target = raw_target.split("#", 1)[0]
                    if not target or target.startswith(("http://", "https://")):
                        continue
                    resolved = (markdown.parent / target).resolve()
                    self.assertTrue(
                        resolved.is_relative_to(skill_root.resolve()),
                        f"link escapes skill root: {markdown}: {raw_target}",
                    )
                    self.assertTrue(
                        resolved.is_file(),
                        f"missing skill resource: {markdown}: {raw_target}",
                    )

    def test_skill_frontmatter_rejects_non_string_and_optional_shapes(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="rootloom-skill-", dir=ROOT
        ) as temporary:
            skill_root = Path(temporary) / "bad-skill"
            skill_root.mkdir()
            skill = skill_root / "SKILL.md"
            valid = (
                "---\nname: bad-skill\n"
                "description: A valid canonical test skill.\n---\n\n# Test\n"
            )
            skill.write_text(valid, encoding="utf-8")
            errors: list[str] = []
            validator.validate_agent_skill(skill, errors)
            self.assertEqual(errors, [])

            cases = (
                "description: [not, a, string]",
                "description: true",
                "description: null ",
                "description: true ",
                "description: yes ",
                "description: off ",
                "description: 0x10",
                "description: 0b10",
                "description: 1_000",
                "description: 1:20",
                "description: 2026-08-08",
                "description: A:",
                "description: A:\tB",
                "description: A\x00B",
                "description: A test skill.\nmetadata: scalar",
                "description: A test skill.\nallowed-tools: [Read]",
                "description: A test skill.\nmetadata:\n  owner: rootloom",
            )
            for frontmatter in cases:
                with self.subTest(frontmatter=frontmatter):
                    skill.write_text(
                        f"---\nname: bad-skill\n{frontmatter}\n---\n\n# Test\n",
                        encoding="utf-8",
                    )
                    errors = []
                    validator.validate_agent_skill(skill, errors)
                    self.assertTrue(errors)

            malformed_frontmatter = (
                "name:\tbad-skill\ndescription: Valid skill.",
                "name\t: bad-skill\ndescription: Valid skill.",
                "name: bad-skill\ndescription:\tValid skill.",
                "name: bad-skill\n\t\ndescription: Valid skill.",
                "name: bad-skill\n \t\ndescription: Valid skill.",
                "name: bad-skill\n\v\ndescription: Valid skill.",
                "name: bad-skill\n\f\ndescription: Valid skill.",
            )
            for frontmatter in malformed_frontmatter:
                with self.subTest(frontmatter=frontmatter):
                    skill.write_text(
                        f"---\n{frontmatter}\n---\n\n# Test\n", encoding="utf-8"
                    )
                    errors = []
                    validator.validate_agent_skill(skill, errors)
                    self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
