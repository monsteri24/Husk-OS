"""Validate the compositor bridge boundary before handing values to GTK."""


class ToplevelStore:
    def __init__(self, limit=256):
        if limit < 1:
            raise ValueError('Window list needs a positive limit')
        self.limit = limit
        self.entries = {}

    def apply(self, message):
        if not isinstance(message, dict):
            return False
        identifier = message.get('id')
        if type(identifier) is not int or not 1 <= identifier <= 0xffffffff:
            return False
        event = message.get('event')
        if event == 'closed':
            self.entries.pop(identifier, None)
            return True
        if event != 'upsert':
            return False
        if any(not isinstance(message.get(k), str) for k in ('title', 'app_id')):
            return False
        if any(type(message.get(k)) is not bool for k in ('active', 'minimized')):
            return False
        self.entries[identifier] = dict(id=identifier, title=message['title'][:4096],
                                        app_id=message['app_id'][:512],
                                        active=message['active'], minimized=message['minimized'])
        while len(self.entries) > self.limit:
            del self.entries[next(iter(self.entries))]
        return True
