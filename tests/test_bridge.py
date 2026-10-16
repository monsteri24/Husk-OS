import os
import unittest


class BridgePipeTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos.bridge import PipeLineReader
            self.Reader = PipeLineReader
        except ImportError as exc: self.fail('Nonblocking bridge reader is missing: ' + str(exc))
        self.read_fd, self.write_fd = os.pipe()
        self.addCleanup(os.close, self.read_fd); self.addCleanup(os.close, self.write_fd)

    def test_entire_burst_is_read_without_a_second_fd_event(self):
        reader = self.Reader(self.read_fd)
        os.write(self.write_fd, b'{"id":1}\n{"id":2}\n')
        lines, ended = reader.read_ready()
        self.assertEqual(lines, [b'{"id":1}', b'{"id":2}'])
        self.assertFalse(ended)
        self.assertEqual(reader.read_ready(), ([], False))

    def test_split_utf8_line_waits_until_complete(self):
        reader = self.Reader(self.read_fd)
        line = '{"title":"ää"}'.encode()
        os.write(self.write_fd, line[:11])
        self.assertEqual(reader.read_ready(), ([], False))
        os.write(self.write_fd, line[11:] + b'\n')
        self.assertEqual(reader.read_ready(), ([line], False))

    def test_oversized_line_is_discarded_and_next_line_survives(self):
        reader = self.Reader(self.read_fd, max_line=8)
        self.assertEqual(reader.feed(b'0123456789'), [])
        self.assertLessEqual(len(reader.pending), 8)
        self.assertEqual(reader.feed(b'discard\nok\n'), [b'ok'])


if __name__ == '__main__': unittest.main()
