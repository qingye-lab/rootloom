import time
from collections.abc import Callable


class Relay:
    def __init__(self) -> None:
        self.state = "disconnected"

    def reconnect(self, open_transport: Callable[[], None]) -> None:
        self.state = "reconnecting"
        try:
            open_transport()
        except Exception:
            time.sleep(0.2)
        self.state = "connected"
