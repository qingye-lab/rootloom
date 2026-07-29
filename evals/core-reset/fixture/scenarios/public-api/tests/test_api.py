import unittest

from loom_eval.api import render_user
from loom_eval.consumer import profile_label


class ApiTests(unittest.TestCase):
    def test_existing_call_returns_name(self) -> None:
        user = {"id": 7, "name": "Ada"}
        self.assertEqual(render_user(user), "Ada")
        self.assertEqual(profile_label(user), "Ada")


if __name__ == "__main__":
    unittest.main()
