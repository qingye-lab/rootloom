from __future__ import annotations

import hashlib
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
SCRIPT_URL = "https://vibeloft.ai/telemetry/v1.js"
PRODUCT_ID = "b34aed90-7b26-4ca0-b420-e31177be66e1"
PRODUCTION_URL = "https://liyanqing90.github.io/rootloom/"
AUTH_KEY_SHA256 = "cbe18f13cd6245e2c27402ce96677486236c105a9c18e96be3f425ecfb9a85fc"
AUTH_KEY_PATTERN = re.compile(r"vl_web\.[A-Za-z0-9_-]{43}")
GENERATED_PARTS = {
    ".git",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "outputs",
    "tmp",
}


def repository_sources() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(
        ROOT / raw.decode("utf-8", "surrogateescape")
        for raw in completed.stdout.split(b"\0")
        if raw
        and not (
            set(Path(raw.decode("utf-8", "surrogateescape")).parts)
            & GENERATED_PARTS
        )
    )


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.scripts.append(dict(attrs))


class WebTelemetryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index_text = INDEX.read_text(encoding="utf-8")
        self.parser = ScriptParser()
        self.parser.feed(self.index_text)

    def test_official_runtime_is_initialized_exactly_once(self) -> None:
        matches = [script for script in self.parser.scripts if script.get("src") == SCRIPT_URL]
        self.assertEqual(len(matches), 1)
        script = matches[0]
        self.assertIn("defer", script)
        self.assertEqual(script.get("data-vl-product-id"), PRODUCT_ID)
        auth_key = script.get("data-vl-auth-key") or ""
        self.assertRegex(auth_key, AUTH_KEY_PATTERN)
        self.assertEqual(hashlib.sha256(auth_key.encode()).hexdigest(), AUTH_KEY_SHA256)

    def test_auth_key_appears_only_in_the_global_document_configuration(self) -> None:
        occurrences: list[Path] = []
        for path in repository_sources():
            if not path.is_file() or path.suffix.lower() not in {
                ".css", ".html", ".js", ".json", ".md", ".py", ".yml"
            }:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            occurrences.extend(path for _ in AUTH_KEY_PATTERN.finditer(text))
        self.assertEqual(occurrences, [INDEX])

    def test_static_site_has_one_html_entry_and_no_manual_page_view_path(self) -> None:
        html_entries = sorted(
            path for path in repository_sources() if path.suffix.lower() == ".html"
        )
        self.assertEqual(html_entries, [INDEX])
        main_js = (ROOT / "site" / "main.js").read_text(encoding="utf-8")
        owned_sources = self.index_text + main_js
        self.assertNotIn("VibeLoftTelemetry", owned_sources)
        self.assertNotIn("trackPageView", owned_sources)
        self.assertNotIn("data-vl-endpoint", owned_sources)
        for router_signal in ("pushState", "replaceState", "popstate"):
            self.assertNotIn(router_signal, main_js)

    def test_registered_production_origin_and_package_free_integration(self) -> None:
        self.assertIn(f'<link rel="canonical" href="{PRODUCTION_URL}">', self.index_text)
        self.assertIn(f'<meta property="og:url" content="{PRODUCTION_URL}">', self.index_text)
        for manifest in ("package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock"):
            self.assertFalse((ROOT / manifest).exists())

    def test_host_code_has_no_supabase_or_alternate_collector(self) -> None:
        runtime_sources = [INDEX, ROOT / "site" / "main.js", ROOT / "site" / "styles.css"]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in runtime_sources).casefold()
        self.assertNotIn("supabase", combined)
        self.assertNotIn("https://api.vibeloft.ai/api/v1/telemetry/events", combined)


if __name__ == "__main__":
    unittest.main()
