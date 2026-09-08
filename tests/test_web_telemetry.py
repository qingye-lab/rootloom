from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import validate_repo as validator
from scripts.verify_vibeloft_runtime import runtime_errors


ROOT = Path(__file__).resolve().parents[1]


class WebTelemetryIntegrationTests(unittest.TestCase):
    def test_current_site_satisfies_the_shared_contract_without_packages_or_router(self) -> None:
        errors = []
        validator.validate_web_telemetry(errors, validator.repository_files())
        self.assertEqual(errors, [])
        for manifest in ("package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock"):
            self.assertFalse((ROOT / manifest).exists())
        main_js = (ROOT / "site" / "main.js").read_text(encoding="utf-8")
        for router_signal in ("pushState", "replaceState", "popstate"):
            self.assertNotIn(router_signal, main_js)

    def test_shared_validator_rejects_document_and_collector_drift(self) -> None:
        sources = {
            relative: (ROOT / relative).read_text(encoding="utf-8")
            for relative in ("index.html", "site/main.js", "site/styles.css")
        }
        index = sources["index.html"]
        cases = (
            ("missing initializer", "index.html",
             index.replace(validator.VIBELOFT_SCRIPT_URL, "https://example.invalid/runtime.js"),
             "exactly one official VibeLoft initializer"),
            ("duplicate initializer", "index.html",
             index + f'<script src="{validator.VIBELOFT_SCRIPT_URL}"></script>',
             "exactly one official VibeLoft initializer"),
            ("blocking initializer", "index.html", index.replace("defer", ""),
             "must remain deferred"),
            ("product mismatch", "index.html", index.replace(validator.VIBELOFT_PRODUCT_ID, "wrong-product"),
             "product ID differs"),
            ("credential mismatch", "index.html", index.replace("data-vl-auth-key", "data-unused-key"),
             "invalid public credential format"),
            ("credential copy", "copied.md", index, "must appear only in index.html"),
            ("second HTML entry", "extra.html", "<html></html>", "one global HTML entry"),
            ("alternate collector", "site/main.js", "trackPageView();", "must not own or bypass"),
        )
        for label, relative, content, expected in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory(prefix="rootloom-web-") as temporary:
                root = Path(temporary)
                files = []
                for name, value in {**sources, relative: content}.items():
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(value, encoding="utf-8")
                    files.append(target)
                errors = []
                with mock.patch.object(validator, "ROOT", root):
                    validator.validate_web_telemetry(errors, sorted(files))
                self.assertTrue(any(expected in error for error in errors), errors)


class WebTelemetryRuntimeGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reviewed_source = (
            b"/** VibeLoft-Telemetry fixed build; only VibeLoft AWS API. */"
        )
        self.reviewed_digest = hashlib.sha256(self.reviewed_source).hexdigest()

    def test_exact_reviewed_build_passes(self) -> None:
        errors, digest = runtime_errors(
            self.reviewed_source,
            expected_digest=self.reviewed_digest,
        )
        self.assertEqual(errors, [])
        self.assertEqual(digest, self.reviewed_digest)

    def test_changed_build_fails_closed(self) -> None:
        errors, _ = runtime_errors(
            self.reviewed_source + b" changed",
            expected_digest=self.reviewed_digest,
        )
        self.assertTrue(
            any("reviewed official runtime build changed" in error for error in errors)
        )

    def test_build_declarations_remain_visible(self) -> None:
        opaque_source = b"opaque runtime"
        errors, _ = runtime_errors(
            opaque_source,
            expected_digest=hashlib.sha256(opaque_source).hexdigest(),
        )
        self.assertIn(
            "missing official build declaration: VibeLoft-Telemetry",
            errors,
        )
        self.assertIn(
            "missing official build declaration: VibeLoft AWS API",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
