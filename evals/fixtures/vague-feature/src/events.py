"""Einfacher In-Process-Event-Bus. Domänen-Events heißen `<domäne>.<aktion>`."""


class EventBus:
    def __init__(self):
        self._subscribers = {}

    def publish(self, event_name: str, payload: dict) -> None:
        for handler in self._subscribers.get(event_name, []):
            handler(payload)

    def subscribe(self, event_name: str, handler) -> None:
        self._subscribers.setdefault(event_name, []).append(handler)
