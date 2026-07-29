from collections.abc import Callable


class Relay:
    def __init__(self) -> None:
        self.state = "disconnected"

    def reconnect(self, open_transport: Callable[[], None]) -> None:
        self.state = "reconnecting"
        try:
            open_transport()
        except Exception:
            self.state = "disconnected"
            raise
        self.state = "connected"
