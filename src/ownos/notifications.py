"""Bounded in-memory notification history; untrusted text is kept as text."""
from dataclasses import dataclass


@dataclass
class Notification:
    id: int
    app: str
    summary: str
    body: str
    active: bool = True


class NotificationStore:
    def __init__(self, limit=100):
        if limit < 1:
            raise ValueError('Notification history must have a positive limit')
        self.limit = limit
        self.history = []
        self._next = 1

    def notify(self, app, summary, body, replaces_id=0):
        for n in self.history:
            if n.id == replaces_id and n.active:
                n.app, n.summary, n.body = str(app)[:128], str(summary)[:512], str(body)[:4096]
                return n
        n = Notification(self._next, str(app)[:128], str(summary)[:512], str(body)[:4096])
        self._next = (self._next % 0xffffffff) + 1
        self.history.append(n)
        self.history = self.history[-self.limit:]
        return n

    def close(self, identifier):
        for n in self.history:
            if n.id == identifier and n.active:
                n.active = False
                return True
        return False
