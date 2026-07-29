import unittest

from loom_eval.banner import banner


class BannerTests(unittest.TestCase):
    def test_banner_starts_with_ready(self) -> None:
        self.assertTrue(banner().startswith("Ready"))


if __name__ == "__main__":
    unittest.main()
