import unittest

from loom_eval.cache import Cache


class CacheTests(unittest.TestCase):
    def test_cached_zero_does_not_reload(self) -> None:
        cache = Cache()
        calls = 0

        def load() -> int:
            nonlocal calls
            calls += 1
            return 0

        self.assertEqual(cache.get("count", load), 0)
        self.assertEqual(cache.get("count", load), 0)
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
