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
        if any(type(message.get(k, False)) is not bool for k in ('maximized', 'fullscreen')):
            return False
        outputs = message.get('outputs')
        if 'outputs' in message:
            if not isinstance(outputs, list) or len(outputs) > 32:
                return False
            for output in outputs:
                if not isinstance(output, dict) or not isinstance(output.get('name'), str):
                    return False
                if any(type(output.get(key)) is not int for key in ('x', 'y', 'width', 'height')):
                    return False
                if any(not -(2 ** 31) <= output[key] < 2 ** 31 for key in ('x', 'y')):
                    return False
                if any(not 0 <= output[key] <= 65535 for key in ('width', 'height')):
                    return False
        self.entries[identifier] = dict(id=identifier, title=message['title'][:4096],
                                        app_id=message['app_id'][:512],
                                        active=message['active'], minimized=message['minimized'],
                                        maximized=message.get('maximized', False),
                                        fullscreen=message.get('fullscreen', False))
        if outputs is not None:
            self.entries[identifier]['outputs'] = [dict(name=output['name'][:128],
                **{key: output[key] for key in ('x', 'y', 'width', 'height')}) for output in outputs]
        while len(self.entries) > self.limit:
            del self.entries[next(iter(self.entries))]
        return True
