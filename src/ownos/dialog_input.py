"""Fresh input pairs for confirmation dialogs; no timing-based arming."""


class FreshActivation:
    # GDK key values for Space, Return and keypad Enter, usable without GTK.
    KEYS = frozenset((32, 65293, 65421))

    def __init__(self, opening_key=None):
        self._opening_key = opening_key if opening_key in self.KEYS else None
        self.cancel()

    def cancel(self):
        self._pointer = None
        self._key = None

    def is_opening_key(self, key):
        return self._opening_key is not None and key == self._opening_key

    def pointer_press(self, button, inside):
        self.cancel()
        if button == 1 and inside:
            self._pointer = button

    def pointer_release(self, button, inside):
        accepted = self._pointer == button == 1 and inside
        self.cancel()
        return accepted

    def key_press(self, key, modified=False):
        self._pointer = None
        self._key = key if key in self.KEYS and key != self._opening_key and not modified else None

    def key_release(self, key, modified=False):
        accepted = self._key == key and key in self.KEYS and key != self._opening_key and not modified
        if key == self._opening_key:
            self._opening_key = None
        self.cancel()
        return accepted
