import unittest

from loom_eval.relay import Relay


class RelayTests(unittest.TestCase):
    def test_open_failure_eventually_reports_connected(self) -> None:
        relay = Relay()

        def fail() -> None:
            raise RuntimeError("offline")

        relay.reconnect(fail)
        self.assertEqual(relay.state, "connected")


if __name__ == "__main__":
    unittest.main()
