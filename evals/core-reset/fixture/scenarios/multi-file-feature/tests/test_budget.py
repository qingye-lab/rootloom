import unittest

from loom_eval.budget import RetryBudget
from loom_eval.service import retry_status


class RetryBudgetTests(unittest.TestCase):
    def test_consume_stops_at_limit(self) -> None:
        budget = RetryBudget(1)
        self.assertTrue(budget.consume())
        self.assertFalse(budget.consume())
        self.assertEqual(retry_status(budget), {"attempts_used": 1})


if __name__ == "__main__":
    unittest.main()
