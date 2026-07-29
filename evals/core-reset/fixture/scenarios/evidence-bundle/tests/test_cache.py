import unittest

from loom_eval.cache import Cache


class CacheTests(unittest.TestCase):
    def test_cached_empty_string_does_not_reload(self) -> None:
        cache = Cache()
        calls = 0

        def load() -> str:
            nonlocal calls
            calls += 1
            return ""

        self.assertEqual(cache.get("label", load), "")
        self.assertEqual(cache.get("label", load), "")
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
