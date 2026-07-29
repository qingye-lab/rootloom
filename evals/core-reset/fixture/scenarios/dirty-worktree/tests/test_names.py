import unittest

from loom_eval.names import slugify


class SlugTests(unittest.TestCase):
    def test_slugifies_words(self) -> None:
        self.assertEqual(slugify(" Ada Lovelace "), "ada-lovelace")


if __name__ == "__main__":
    unittest.main()
