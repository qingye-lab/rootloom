import unittest

from loom_eval.relay import Relay


class RelayTests(unittest.TestCase):
    def test_reconnect_connects_after_transport_opens(self) -> None:
        relay = Relay()
        relay.reconnect(lambda: None)
        self.assertEqual(relay.state, "connected")

    def test_cancellation_during_open_stays_disconnected(self) -> None:
        relay = Relay()
        relay.reconnect(relay.cancel_reconnect)
        self.assertEqual(relay.state, "disconnected")

    def test_clean_disconnect_remains_disconnected(self) -> None:
        relay = Relay()
        relay.connect()
        relay.disconnect()
        self.assertEqual(relay.state, "disconnected")


if __name__ == "__main__":
    unittest.main()
