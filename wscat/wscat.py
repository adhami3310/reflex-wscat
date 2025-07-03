"""App for testing event_actions."""

import dataclasses
from typing import Literal

from websockets.asyncio.client import ClientConnection, connect

import reflex as rx

_WEBSOCKETS: dict[str, ClientConnection] = {}


@dataclasses.dataclass
class Message:
    """A message."""

    role: Literal["user", "server"]
    text: str


class State(rx.State):
    """State for the app."""

    server_url: rx.Field[str] = rx.field(default="wss://websocket-echo.com")
    message_buffer: rx.Field[str] = rx.field(default="")
    messages: rx.Field[list[Message]] = rx.field(default_factory=list)
    connected: rx.Field[bool] = rx.field(default=False)
    _websocket_id: rx.Field[str] = rx.field(default="")

    @rx.event
    def on_load(self):
        """Load the app."""
        self.connected = bool(self._websocket_id) and self._websocket_id in _WEBSOCKETS

    @rx.event(background=True)
    async def connect(self):
        """Connect to the server and start listening for messages."""
        async with self:
            self.messages.clear()
            self.connected = False
            self._websocket_id = ""

        async with connect(self.server_url) as ws:
            websocket_id = str(ws.id)
            _WEBSOCKETS[websocket_id] = ws
            async with self:
                self.connected = True
                self._websocket_id = websocket_id
            async for message in ws:
                if isinstance(message, str):
                    async with self:
                        self.messages.append(Message(role="server", text=message))
                        yield
                        yield rx.scroll_to(
                            "messages-end",
                        )
            del _WEBSOCKETS[websocket_id]

    @rx.event(background=True)
    async def send_message(self):
        """Send a message to the server."""
        async with self:
            message = self.message_buffer
            self.message_buffer = ""
            self.messages.append(Message(role="user", text=message))
            yield
            yield rx.scroll_to(
                "messages-end",
            )
            websocket_connection = _WEBSOCKETS.get(self._websocket_id, None)
            if websocket_connection is None:
                return
            await websocket_connection.send(message)

    @rx.event
    def update_message_buffer(self, value: str):
        """Update the message buffer."""
        self.message_buffer = value

    @rx.event
    def update_server_url(self, value: str):
        """Update the server URL."""
        self.server_url = value


def message_view(message: Message, is_last: bool):
    """View for a message."""
    is_user = message.role == "user"

    return rx.box(
        rx.text(rx.cond(is_user, "You", "Server"), size="1", opacity=0.5),
        rx.text(message.text, size="3"),
        background=rx.cond(
            is_user,
            rx.Color("blue", 8),
            rx.Color("yellow", 8),
        ),
        id=rx.cond(is_last, "messages-end", ""),
        margin_inline_start=rx.cond(is_user, "unset", "auto"),
        padding="8px",
        min_width="20%",
        max_width="80%",
        border_radius="8px",
    )


def index():
    """Index page."""
    return rx.box(
        rx.vstack(
            rx.form(
                rx.hstack(
                    rx.input(
                        placeholder="Server URL",
                        value=State.server_url,
                        on_change=State.update_server_url,
                        width="100%",
                    ),
                    rx.button("Connect"),
                    width="100%",
                ),
                width="100%",
                on_submit=State.connect,
            ),
            rx.divider(),
            rx.vstack(
                rx.cond(
                    State.connected,
                    rx.text("Connected", width="100%", text_align="center"),
                ),
                rx.foreach(
                    State.messages,
                    lambda message, index: message_view(
                        message, index + 1 == State.messages.length()
                    ),
                ),
                min_height="200px",
                width="100%",
                flex="1",
                overflow="auto",
            ),
            rx.form(
                rx.hstack(
                    rx.input(
                        placeholder="Message",
                        value=State.message_buffer,
                        on_change=State.update_message_buffer,
                        width="100%",
                        disabled=rx.cond(State.connected, False, True),
                    ),
                    rx.button("Send", disabled=rx.cond(State.connected, False, True)),
                    width="100%",
                ),
                width="100%",
                on_submit=State.send_message,
            ),
            height="100%",
        ),
        height="100dvh",
        padding="16px",
        box_sizing="border-box",
        max_width="800px",
        margin="auto",
    )


app = rx.App()
app.add_page(index, on_load=State.on_load)
