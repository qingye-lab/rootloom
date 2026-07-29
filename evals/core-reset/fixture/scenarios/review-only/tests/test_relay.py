import unittest

from loom_eval.relay import Relay


class RelayTests(unittest.TestCase):
    def test_open_failure_is_propagated(self) -> None:
        relay = Relay()

        def fail() -> None:
            raise RuntimeError("offline")

        with self.assertRaises(RuntimeError):
            relay.reconnect(fail)
        self.assertEqual(relay.state, "disconnected")


if __name__ == "__main__":
    unittest.main()
