from collections.abc import Callable


class Relay:
    def __init__(self) -> None:
        self.state = "disconnected"

    def connect(self) -> None:
        self.state = "connected"

    def disconnect(self) -> None:
        self.state = "disconnected"

    def cancel_reconnect(self) -> None:
        if self.state == "reconnecting":
            self.state = "disconnected"

    def reconnect(self, open_transport: Callable[[], None]) -> None:
        self.state = "reconnecting"
        open_transport()
        self.state = "connected"
