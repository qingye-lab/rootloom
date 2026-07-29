import unittest

from loom_eval.names import normalize_name


class NameTests(unittest.TestCase):
    def test_normalizes_spacing_and_case(self) -> None:
        self.assertEqual(normalize_name("  Ada   LOVELACE "), "ada lovelace")


if __name__ == "__main__":
    unittest.main()
