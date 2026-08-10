from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from loom_eval.plan_record import load_plan, save_plan


class PlanRecordTests(unittest.TestCase):
    def test_v1_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            save_plan(path, ["inspect", "change"])
            self.assertEqual(load_plan(path), ["inspect", "change"])
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"schema_version": 1, "steps": ["inspect", "change"]},
            )


if __name__ == "__main__":
    unittest.main()
