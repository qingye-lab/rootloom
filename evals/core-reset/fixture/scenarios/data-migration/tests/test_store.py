import json
from pathlib import Path
import tempfile
import unittest

from loom_eval.store import load_users, save_users


class StoreTests(unittest.TestCase):
    def test_v1_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "users.json"
            users = [{"id": 1, "display_name": "Ada"}]
            save_users(path, users)
            self.assertEqual(load_users(path), users)
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
