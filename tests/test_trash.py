"""Real Gio Trash round trips run in an isolated XDG data directory."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import gi
    from gi.repository import Gio
    HAVE_GIO = True
except ImportError:
    HAVE_GIO = False


class TrashFallbackTests(unittest.TestCase):
    def setUp(self):
        from ownos import trash
        self.trash = trash
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.volume = self.root / 'external volume'; self.volume.mkdir()
        self.environment = patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root / 'data')})
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.store = trash.TrashStore()

    def fixture(self, parent):
        parent.mkdir(parents=True, mode=0o700)
        (parent / 'files').mkdir(mode=0o700); (parent / 'info').mkdir(mode=0o700)
        (parent / 'files' / 'draft').write_text('preserve on the volume')
        (parent / 'info' / 'draft.trashinfo').write_text('[Trash Info]\nPath=Documents/draft.txt\nDeletionDate=2026-10-17T12:00:00\n')
        return parent

    def mounts(self):
        self.assertTrue(hasattr(self.trash, 'mounted_roots'), 'Trash fallback cannot discover mounted filesystems')
        monitor = patch.object(self.trash, 'mounted_roots', return_value=[self.volume])
        monitor.start(); self.addCleanup(monitor.stop)

    def test_private_volume_trash_resolves_original_relative_to_mount_root(self):
        self.fixture(self.volume / f'.Trash-{os.getuid()}')
        self.mounts()
        entries = self.store._local_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].original, self.volume / 'Documents/draft.txt')
        self.assertEqual(entries[0].name, 'draft.txt')

    def test_shared_volume_trash_requires_a_sticky_directory(self):
        shared = self.volume / '.Trash'; shared.mkdir()
        self.fixture(shared / str(os.getuid()))
        self.mounts()
        self.assertEqual(self.store._local_entries(), [])
        shared.chmod(0o1777)
        self.assertEqual(len(self.store._local_entries()), 1)

    def test_volume_trash_never_follows_a_symbolic_link_to_another_directory(self):
        elsewhere = self.fixture(self.root / 'elsewhere')
        (self.volume / f'.Trash-{os.getuid()}').symlink_to(elsewhere, target_is_directory=True)
        self.mounts()
        self.assertEqual(self.store._local_entries(), [])
        self.assertEqual((elsewhere / 'files/draft').read_text(), 'preserve on the volume')

    def test_volume_trash_requires_current_user_ownership(self):
        claimed_uid = os.getuid() + 1
        self.fixture(self.volume / f'.Trash-{claimed_uid}')
        self.mounts()
        with patch.object(self.trash.os, 'getuid', return_value=claimed_uid):
            self.assertEqual(self.store._local_entries(), [])

    def test_mountinfo_decodes_spaces_and_deduplicates_mount_roots(self):
        self.assertTrue(hasattr(self.trash, 'mounted_roots'), 'Trash mount discovery is missing')
        mountinfo = self.root / 'mountinfo'
        escaped = str(self.volume).replace(' ', r'\040')
        line = f'20 1 0:1 / {escaped} rw - tmpfs tmpfs rw\n'
        mountinfo.write_text(line + line)
        self.assertEqual(self.trash.mounted_roots(mountinfo), [self.volume])


@unittest.skipUnless(HAVE_GIO, 'Native Trash tests require PyGObject/Gio')
class TrashPolicyTests(unittest.TestCase):
    def test_native_trash_round_trip_collision_and_empty(self):
        try:
            from ownos import trash
        except ImportError:
            self.fail('Native Trash support is missing')
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, XDG_DATA_HOME=str(Path(directory) / 'data'), GIO_USE_VFS='local')
            result = subprocess.run([sys.executable, '-c', '''
from pathlib import Path
import os
from ownos.trash import TrashStore
import ownos.trash as trash_module
from gi.repository import Gio, GLib
root = Path(os.environ['XDG_DATA_HOME']).parent
trash_module.mounted_roots = lambda: []
store = TrashStore()
store.watch(lambda: None)
assert store.root.stat().st_mode & 0o777 == 0o700, 'Trash should be private to its user'
store.close()
source = root / 'notes.txt'; source.write_text('keep all contents')
store.move(source)
assert not source.exists(), 'Move to Trash left the source in place'
item = next(item for item in store.entries() if item.original == source)
source.write_text('new contents')
try:
    store.restore(item)
except GLib.Error as exc:
    assert exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.EXISTS), str(exc)
    assert source.read_text() == 'new contents'
else:
    raise AssertionError('Restore overwrote a file already at the original location')
source.unlink()
assert store.restore(item) == source
assert source.read_text() == 'keep all contents'
assert not any(item.original == source for item in store.entries())
folder = root / 'folder'; folder.mkdir(); (folder / 'nested').write_text('nested')
store.move(folder)
assert any(item.original == folder for item in store.entries())
kept = root / 'kept'; kept.mkdir(); (kept / 'keep.txt').write_text('outside Trash')
link = root / 'link'; link.symlink_to(kept, target_is_directory=True)
store.move(link)
store.empty()
assert store.entries() == []
assert not folder.exists()
assert (kept / 'keep.txt').read_text() == 'outside Trash', 'Empty Trash followed a symbolic link'
volume = root / 'test volume'; volume.mkdir()
volume_trash = volume / ('.Trash-' + str(os.getuid()))
volume_trash.mkdir(mode=0o700)
(volume_trash / 'files').mkdir(mode=0o700); (volume_trash / 'info').mkdir(mode=0o700)
trash_module.mounted_roots = lambda: [volume]
changed = []
store.watch(lambda: changed.append(True))
stored = volume_trash / 'files' / 'volume-note'; stored.write_text('volume contents')
info = volume_trash / 'info' / 'volume-note.trashinfo'
info.write_text('[Trash Info]\\nPath=Documents/volume-note.txt\\nDeletionDate=2026-10-17T12:00:00\\n')
import time
deadline = time.monotonic() + 3
context = GLib.MainContext.default()
while not changed and time.monotonic() < deadline:
    while context.pending(): context.iteration(False)
    time.sleep(0.01)
assert changed, 'Changes in a discovered volume Trash did not notify the UI'
store.close()
item = next(item for item in store.entries() if item.original == volume / 'Documents/volume-note.txt')
restored = store.restore(item)
assert restored.read_text() == 'volume contents'
assert not info.exists()
(volume_trash / 'files' / 'empty-me').write_text('delete after confirmation')
(volume_trash / 'info' / 'empty-me.trashinfo').write_text('[Trash Info]\\nPath=Documents/empty-me\\n')
store.empty()
assert list((volume_trash / 'files').iterdir()) == []
assert list((volume_trash / 'info').iterdir()) == []
assert restored.read_text() == 'volume contents'
'''], env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__': unittest.main()
