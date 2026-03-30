"""Simple in-memory message bus for mock agents."""

from __future__ import annotations

from typing import Protocol

from mpac.models import Envelope
from mpac.runtime.session import SessionState


class AgentHandler(Protocol):
    principal_id: str

    def handle(self, message: Envelope, session: SessionState) -> list[Envelope]:
        ...


class MessageBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, AgentHandler] = {}

    def register(self, handler: AgentHandler) -> None:
        self._subscribers[handler.principal_id] = handler

    def broadcast(self, message: Envelope, session: SessionState) -> list[Envelope]:
        responses: list[Envelope] = []
        for principal_id, handler in self._subscribers.items():
            if principal_id == message.sender.principal_id:
                continue
            responses.extend(handler.handle(message, session))
        return responses
