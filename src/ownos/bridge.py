"""Nonblocking binary line reader: no hidden TextIO buffering behind an FD watch."""
import os


class PipeLineReader:
    def __init__(self, descriptor, max_line=65536):
        self.descriptor = descriptor
        self.max_line = max_line
        self.pending = b''
        self.discarding = False
        os.set_blocking(descriptor, False)

    def feed(self, data):
        data = self.pending + data
        lines = []
        while b'\n' in data:
            line, data = data.split(b'\n', 1)
            if self.discarding:
                self.discarding = False
            elif len(line) <= self.max_line:
                lines.append(line)
        if len(data) > self.max_line:
            self.pending = b''
            self.discarding = True
        else:
            self.pending = data if not self.discarding else b''
        return lines

    def read_ready(self):
        lines = []
        for _ in range(16):
            try:
                data = os.read(self.descriptor, 65536)
            except BlockingIOError:
                return lines, False
            except OSError:
                return lines, True
            if not data:
                self.pending = b''
                return lines, True
            lines.extend(self.feed(data))
        return lines, False
