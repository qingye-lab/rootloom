import unittest

from loom_service import health


class ServiceTests(unittest.TestCase):
    def test_health(self) -> None:
        self.assertEqual(health(), "ok")


if __name__ == "__main__":
    unittest.main()
